"""do.py - the general-purpose agentic loop.

The loop that makes keanu an agent. It asks the oracle what to do,
the oracle picks an ability, the ability runs, the result feeds back.
Feel monitors every oracle response for ALIVE/GREY/BLACK.

The key difference from loop.py (convergence): do.py handles any task.
loop.py is specialized for duality exploration. do.py is the general tool.

in the world: feel -> think -> act -> feel -> repeat.
the oracle is the brain. abilities are the hands.
the loop keeps going until the task is done or paused.
"""

import json
from dataclasses import dataclass, field

from keanu.abilities import _REGISTRY, list_abilities, record_cast
from keanu.oracle import call_oracle, try_interpret
from keanu.hero.feel import Feel, FeelResult
from keanu.log import info, warn, debug


from keanu.hero.types import Step


# ============================================================
# DATA
# ============================================================

@dataclass
class LoopResult:
    """Everything that happened during a full run of the loop.
    Includes the final answer, all steps taken, and feel stats.

    in the world: the full story of what happened when the loop ran.
    """
    task: str
    status: str          # "done", "paused", "max_turns", "error"
    answer: str = ""
    steps: list = field(default_factory=list)
    feel_stats: dict = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "done"


# ============================================================
# SYSTEM PROMPT
# ============================================================

def _build_system(abilities: list[dict], ide_context: str = "") -> str:
    """Build the system prompt that tells the oracle what abilities it has.

    Lists all seeing abilities (auto-triggered) and hand abilities
    (explicitly invoked). Includes the JSON format the oracle must
    respond with on each turn.

    in the world: the briefing before the mission starts.
    """

    hands = ["read", "write", "edit", "search", "ls", "run"]
    seeing = []

    for ab in abilities:
        if ab["name"] in hands:
            continue
        seeing.append(f"  {ab['name']}: {ab['description']}")

    hands_desc = [
        "  read: read a file. args: {file_path}",
        "  write: write a file. args: {file_path, content}",
        "  edit: targeted edit. args: {file_path, old_string, new_string}",
        "  search: grep/glob for code. args: {pattern, path?, glob?}",
        "  ls: list directory. args: {path}",
        "  run: shell command. args: {command}",
    ]

    base = f"""You are keanu, an agent that solves tasks by using abilities.

You have two kinds of abilities:

SEEING (these run automatically when relevant):
{chr(10).join(seeing)}

HANDS (you invoke these explicitly):
{chr(10).join(hands_desc)}

On each turn, respond with JSON:
{{
    "thinking": "what you're considering (1-2 sentences)",
    "action": "ability_name",
    "args": {{}},
    "done": false
}}

When the task is complete:
{{
    "thinking": "why this is done",
    "action": "none",
    "args": {{}},
    "done": true,
    "answer": "final answer or summary"
}}

Rules:
- One action per turn. You'll see the result before choosing the next.
- Read before you edit. Always.
- If something fails, try a different approach.
- If you're stuck, say so in the answer and set done=true.
- Be direct. No filler."""

    if ide_context:
        base += ide_context

    return base


# ============================================================
# LOOP
# ============================================================

class AgentLoop:
    """The general-purpose agentic loop.

    Creates a Feel instance for monitoring cognitive state, then runs
    a turn-based loop: ask the oracle -> parse response -> execute
    ability -> feed result back. Stops when the oracle says done,
    feel detects black state, or we hit max turns.

    in the world: the heartbeat. feel, think, act, repeat.
    """

    def __init__(self, store=None, max_turns: int = 25):
        self.feel = Feel(store=store)
        self.max_turns = max_turns
        self.steps: list[Step] = []

    def run(self, task: str, legend: str = "creator",
            model: str = None) -> LoopResult:
        """Run the loop on a task.

        Calls the oracle directly (not through the router) because
        do.py handles its own ability dispatch via the JSON action field.
        Feel.check() runs on every oracle response to monitor aliveness.

        in the world: light the fire and let it burn until the task is done.
        """
        from keanu.hero.ide import ide_context_string

        ide_ctx = ide_context_string()
        system = _build_system(list_abilities(), ide_context=ide_ctx)
        messages = [f"TASK: {task}"]

        for turn in range(self.max_turns):
            prompt = "\n\n".join(messages)

            # ask the oracle directly (bypasses router to avoid ability loop)
            try:
                response = call_oracle(prompt, system, legend=legend, model=model)
            except ConnectionError as e:
                warn("loop", f"oracle unreachable: {e}")
                return LoopResult(
                    task=task,
                    status="paused",
                    steps=self.steps,
                    feel_stats=self.feel.stats(),
                    error=str(e),
                )

            # feel checks the response for aliveness
            feel_result = self.feel.check(response)

            if feel_result.should_pause:
                warn("loop", f"paused at turn {turn}")
                return LoopResult(
                    task=task,
                    status="paused",
                    steps=self.steps,
                    feel_stats=self.feel.stats(),
                    error="black state detected",
                )

            # parse the oracle's response
            parsed = try_interpret(response)
            if parsed is None:
                self.steps.append(Step(
                    turn=turn, action="think",
                    input_summary="(unparseable response)",
                    result=response[:200],
                ))
                messages.append("RESULT: Your response wasn't valid JSON. Respond with the JSON format specified.")
                continue

            thinking = parsed.get("thinking", "")
            action = parsed.get("action", "none")
            args = parsed.get("args", {})
            done = parsed.get("done", False)

            info("loop", f"turn {turn}: {action} {'(done)' if done else ''}")
            if thinking:
                debug("loop", f"  thinking: {thinking[:80]}")

            # done?
            if done:
                answer = parsed.get("answer", thinking)
                self.steps.append(Step(
                    turn=turn, action="done",
                    input_summary=thinking,
                    result=answer,
                ))
                return LoopResult(
                    task=task,
                    status="done",
                    answer=answer,
                    steps=self.steps,
                    feel_stats=self.feel.stats(),
                )

            # no action
            if action == "none" or action == "think":
                self.steps.append(Step(
                    turn=turn, action="think",
                    input_summary=thinking,
                    result="(no action taken)",
                ))
                messages.append("RESULT: OK, what's your next action?")
                continue

            # look up the ability
            ab = _REGISTRY.get(action)
            if ab is None:
                self.steps.append(Step(
                    turn=turn, action=action,
                    input_summary=str(args)[:100],
                    result=f"unknown ability: {action}",
                    ok=False,
                ))
                messages.append(f"RESULT: Unknown ability '{action}'. Available: {', '.join(sorted(_REGISTRY.keys()))}")
                continue

            # execute
            try:
                exec_result = ab.execute(
                    prompt=json.dumps(args) if args else "",
                    context=args,
                )
            except Exception as e:
                exec_result = {"success": False, "result": str(e), "data": {}}

            if exec_result["success"]:
                if ab.cast_line:
                    info("cast", ab.cast_line)
                is_new = record_cast(action)
                if is_new:
                    info("cast", f"ability unlocked: {action}")

            step = Step(
                turn=turn, action=action,
                input_summary=str(args)[:100],
                result=exec_result["result"][:500],
                ok=exec_result["success"],
            )
            self.steps.append(step)

            # feed result back to the oracle
            status = "OK" if exec_result["success"] else "FAILED"
            messages.append(f"RESULT ({status}): {exec_result['result'][:2000]}")

        # hit max turns
        return LoopResult(
            task=task,
            status="max_turns",
            steps=self.steps,
            feel_stats=self.feel.stats(),
            error=f"hit {self.max_turns} turn limit",
        )

# ============================================================
# CONVENIENCE
# ============================================================

def run(task: str, legend: str = "creator", model: str = None,
        store=None, max_turns: int = 25) -> LoopResult:
    """Run the agentic loop on a task. Convenience wrapper around AgentLoop.

    in the world: light the fire and see what happens.
    """
    loop = AgentLoop(store=store, max_turns=max_turns)
    return loop.run(task, legend=legend, model=model)
