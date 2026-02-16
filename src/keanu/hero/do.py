"""do.py - the unified agent loop.

one loop, three configs. do is the general tool, craft is the code specialist,
prove is the scientist. same heartbeat: feel -> think -> act -> feel -> repeat.

the oracle is the brain. abilities are the hands. the config decides which
hands are available and what the oracle is told.

in the world: feel -> think -> act -> feel -> repeat.
"""

import json
from dataclasses import dataclass, field

from keanu.abilities import _REGISTRY, list_abilities, record_cast
from keanu.oracle import call_oracle, try_interpret
from keanu.hero.feel import Feel, FeelResult
from keanu.log import info, warn, debug


from keanu.hero.types import Step


# ============================================================
# CONFIG
# ============================================================

@dataclass
class LoopConfig:
    """what makes each loop variant different."""
    name: str
    system_prompt: str
    allowed: set | None = None    # None = all abilities
    max_turns: int = 25
    result_fields: tuple = ()     # extra fields to extract from done response


# ============================================================
# SYSTEM PROMPTS
# ============================================================

def _build_system(abilities: list[dict], ide_context: str = "") -> str:
    """build the system prompt for the general-purpose loop."""
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
- If the task is vague or you don't understand it, set done=true and ask for clarification in your answer. Don't loop.
- If you're stuck, say so in the answer and set done=true.
- Be direct. No filler."""

    if ide_context:
        base += ide_context

    return base


CRAFT_PROMPT = """You are a code craftsman. You write, edit, and test code.
You have these tools:

  read: read a file. args: {file_path}
  write: write a file. args: {file_path, content}
  edit: targeted edit. args: {file_path, old_string, new_string}
  search: grep/glob for code. args: {pattern, path?, glob?}
  ls: list directory. args: {path}
  run: shell command. args: {command}

On each turn, respond with JSON:
{
    "thinking": "what you're considering",
    "action": "tool_name",
    "args": {},
    "done": false
}

When finished:
{
    "thinking": "why this is done",
    "action": "none",
    "args": {},
    "done": true,
    "answer": "what you built and what changed",
    "files_changed": ["list of files you modified"]
}

Rules:
- ALWAYS read a file before editing it.
- Prefer edit over write. Surgical changes, not full rewrites.
- After writing code, run the relevant tests.
- One action per turn. You'll see the result before choosing the next.
- Keep changes minimal. Don't refactor what you weren't asked to touch.
- If tests fail, fix them. Don't move on with broken tests."""


PROVE_PROMPT = """You are a scientist. You test hypotheses by gathering evidence.

You have these tools to gather evidence:
  read: read a file. args: {file_path}
  search: grep/glob for code. args: {pattern, path?, glob?}
  ls: list directory. args: {path}
  run: shell command. args: {command}
  recall: search memories. args: {query}

On each turn, respond with JSON:
{
    "thinking": "what evidence you're looking for and why",
    "action": "tool_name",
    "args": {},
    "done": false
}

When you have enough evidence:
{
    "thinking": "weighing all evidence",
    "action": "none",
    "args": {},
    "done": true,
    "verdict": "supported" or "refuted" or "inconclusive",
    "confidence": 0.0 to 1.0,
    "evidence_for": ["each piece of supporting evidence"],
    "evidence_against": ["each piece of contradicting evidence"],
    "gaps": ["what you couldn't test or verify"],
    "summary": "one paragraph honest assessment"
}

Rules:
- Look for evidence BOTH for and against. Confirmation bias is a defect.
- Each piece of evidence should be specific: file name, line number, actual content.
- Don't speculate. If you can't find evidence, say so in gaps.
- confidence is how sure you are of the verdict, not how much you agree with the hypothesis.
- 3-8 turns is typical. Don't over-gather, don't under-gather.
- If the hypothesis is vague, restate it precisely before gathering evidence."""


HANDS = {"read", "write", "edit", "search", "ls", "run"}
EVIDENCE_TOOLS = {"read", "search", "ls", "run", "recall"}


DO_CONFIG = LoopConfig(
    name="do",
    system_prompt="",  # built dynamically via _build_system
    allowed=None,
    max_turns=25,
)

CRAFT_CONFIG = LoopConfig(
    name="craft",
    system_prompt=CRAFT_PROMPT,
    allowed=HANDS,
    max_turns=25,
    result_fields=("files_changed",),
)

PROVE_CONFIG = LoopConfig(
    name="prove",
    system_prompt=PROVE_PROMPT,
    allowed=EVIDENCE_TOOLS,
    max_turns=12,
    result_fields=("verdict", "confidence", "evidence_for", "evidence_against",
                   "gaps", "summary"),
)


# ============================================================
# DATA
# ============================================================

@dataclass
class LoopResult:
    """everything that happened during a full run of the loop."""
    task: str
    status: str          # "done", "paused", "max_turns", "error"
    answer: str = ""
    steps: list = field(default_factory=list)
    feel_stats: dict = field(default_factory=dict)
    extras: dict = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "done"


# ============================================================
# LOOP
# ============================================================

class AgentLoop:
    """the unified agent loop. one class, three configs.

    in the world: the heartbeat. feel, think, act, repeat.
    """

    def __init__(self, config: LoopConfig = None, store=None, max_turns: int = None):
        self.config = config or DO_CONFIG
        self.feel = Feel(store=store)
        self.max_turns = max_turns or self.config.max_turns
        self.steps: list[Step] = []

    def _get_system(self) -> str:
        """get system prompt. do builds dynamically, others use static."""
        if self.config.name == "do":
            from keanu.hero.ide import ide_context_string
            ide_ctx = ide_context_string()
            return _build_system(list_abilities(), ide_context=ide_ctx)
        return self.config.system_prompt

    def run(self, task: str, legend: str = "creator",
            model: str = None) -> LoopResult:
        """run the loop on a task."""
        system = self._get_system()
        messages = [f"TASK: {task}"]

        info(self.config.name, f"{self.config.name}: {task[:80]}")

        for turn in range(self.max_turns):
            prompt = "\n\n".join(messages)

            try:
                response = call_oracle(prompt, system, legend=legend, model=model)
            except ConnectionError as e:
                warn(self.config.name, f"oracle unreachable: {e}")
                return self._result(task, "paused", error=str(e))

            # parse first, then pulse-check the thinking (natural language),
            # not the raw JSON (which always scans flat/grey)
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

            # pulse the thinking field, not the JSON envelope
            feel_result = self.feel.check(thinking) if thinking else FeelResult(response=response)
            if feel_result.should_pause:
                warn(self.config.name, f"paused at turn {turn}")
                return self._result(task, "paused", error="black state detected")

            # grey: let the agent know its state. awareness, not instruction.
            if feel_result.should_breathe:
                messages.append(f"[STATE] {feel_result.breath_injection}")

            info(self.config.name, f"turn {turn}: {action} {'(done)' if done else ''}")
            if thinking:
                debug(self.config.name, f"  thinking: {thinking[:80]}")

            if done:
                answer = parsed.get("answer", thinking)
                self.steps.append(Step(
                    turn=turn, action="done",
                    input_summary=thinking, result=answer,
                ))
                extras = {k: parsed.get(k) for k in self.config.result_fields
                          if parsed.get(k) is not None}
                return self._result(task, "done", answer=answer, extras=extras)

            if action in ("none", "think"):
                self.steps.append(Step(
                    turn=turn, action="think",
                    input_summary=thinking,
                    result="(no action taken)",
                ))
                messages.append("RESULT: OK, what's your next action?")
                continue

            # check ability is allowed
            if self.config.allowed is not None and action not in self.config.allowed:
                self.steps.append(Step(
                    turn=turn, action=action,
                    input_summary=str(args)[:100],
                    result=f"not allowed: {action}. use: {', '.join(sorted(self.config.allowed))}",
                    ok=False,
                ))
                messages.append(f"RESULT: '{action}' is not available. You can only use: {', '.join(sorted(self.config.allowed))}")
                continue

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

            status = "OK" if exec_result["success"] else "FAILED"
            label = "EVIDENCE" if self.config.name == "prove" else "RESULT"
            messages.append(f"{label} ({status}): {exec_result['result'][:2000]}")

        return self._result(task, "max_turns",
                            error=f"hit {self.max_turns} turn limit")

    def _result(self, task, status, answer="", extras=None, error=""):
        """build a LoopResult."""
        return LoopResult(
            task=task, status=status, answer=answer,
            steps=self.steps, feel_stats=self.feel.stats(),
            extras=extras or {}, error=error,
        )


# ============================================================
# CONVENIENCE
# ============================================================

def run(task: str, legend: str = "creator", model: str = None,
        store=None, max_turns: int = 25) -> LoopResult:
    """run the general agent loop."""
    loop = AgentLoop(DO_CONFIG, store=store, max_turns=max_turns)
    return loop.run(task, legend=legend, model=model)


def craft(task: str, legend: str = "creator", model: str = None,
          store=None, max_turns: int = 25) -> LoopResult:
    """run the code agent loop. hands only."""
    loop = AgentLoop(CRAFT_CONFIG, store=store, max_turns=max_turns)
    return loop.run(task, legend=legend, model=model)


def prove(hypothesis: str, context: str = "", legend: str = "creator",
          model: str = None, store=None, max_turns: int = 12) -> LoopResult:
    """run the evidence agent loop."""
    task = f"HYPOTHESIS: {hypothesis}"
    if context:
        task += f"\n\nCONTEXT: {context}"
    loop = AgentLoop(PROVE_CONFIG, store=store, max_turns=max_turns)
    return loop.run(task, legend=legend, model=model)
