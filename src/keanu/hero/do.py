"""do.py - the general-purpose agentic loop.

feel -> think -> act -> feel -> repeat.

the LLM is the brain. abilities are the hands.
feel monitors every response for ALIVE/GREY/BLACK.
the loop keeps going until the task is done or paused.
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from keanu.abilities import _REGISTRY, list_abilities
from keanu.hero.feel import Feel, FeelResult
from keanu.log import info, warn, debug


# ============================================================
# DATA
# ============================================================

@dataclass
class Step:
    """One step in the loop."""
    turn: int
    action: str          # ability name or "think" or "done"
    input_summary: str   # what was asked
    result: str          # what came back
    ok: bool = True


@dataclass
class LoopResult:
    """Full result from the agentic loop."""
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
    """Build the system prompt that tells the LLM what tools it has."""

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
    """The general-purpose agentic loop."""

    def __init__(self, store=None, max_turns: int = 25):
        self.feel = Feel(store=store)
        self.max_turns = max_turns
        self.steps: list[Step] = []

    def run(self, task: str, backend: str = "claude",
            model: str = None) -> LoopResult:
        """Run the loop on a task."""
        from keanu.hero.ide import ide_context_string

        ide_ctx = ide_context_string()
        system = _build_system(list_abilities(), ide_context=ide_ctx)
        messages = [f"TASK: {task}"]

        for turn in range(self.max_turns):
            prompt = "\n\n".join(messages)

            # think (LLM call through feel, which monitors ALIVE state)
            result = self.feel.felt_call(
                prompt, system=system, backend=backend, model=model,
            )

            if result.should_pause:
                warn("loop", f"paused at turn {turn}")
                return LoopResult(
                    task=task,
                    status="paused",
                    steps=self.steps,
                    feel_stats=self.feel.stats(),
                    error="black state detected",
                )

            # parse the LLM's response
            parsed = self._parse_response(result.response)
            if parsed is None:
                self.steps.append(Step(
                    turn=turn, action="think",
                    input_summary="(unparseable response)",
                    result=result.response[:200],
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

            step = Step(
                turn=turn, action=action,
                input_summary=str(args)[:100],
                result=exec_result["result"][:500],
                ok=exec_result["success"],
            )
            self.steps.append(step)

            # feed result back to LLM
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

    def _parse_response(self, response: str) -> Optional[dict]:
        """Parse JSON from LLM response. Tolerant of markdown fences."""
        text = response.strip()

        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None

        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None


# ============================================================
# CONVENIENCE
# ============================================================

def run(task: str, backend: str = "claude", model: str = None,
        store=None, max_turns: int = 25) -> LoopResult:
    """Run the agentic loop on a task."""
    loop = AgentLoop(store=store, max_turns=max_turns)
    return loop.run(task, backend=backend, model=model)
