"""craft.py - the coder. shapes code with the oracle and hands.

specialized do.py loop that understands code. reads before editing,
runs tests after changes, knows about imports and file structure.
the oracle decides what to do, the hands do it.

practically: "craft a function that does X" reads context, writes code,
runs tests.

in the world: the craftsman shapes steel. read the grain, strike once,
test the edge.
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from keanu.abilities import _REGISTRY, list_abilities
from keanu.oracle import call_oracle, interpret
from keanu.hero.feel import Feel
from keanu.log import info, warn, debug


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


@dataclass
class CraftResult:
    """everything that happened during a craft session.

    in the world: the finished piece. what was shaped, how many strikes,
    whether the edge holds.
    """
    task: str
    status: str          # "done", "paused", "max_turns", "error"
    answer: str = ""
    files_changed: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    feel_stats: dict = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "done"


@dataclass
class CraftStep:
    """one strike of the hammer.

    in the world: one heartbeat of the craft loop.
    """
    turn: int
    action: str
    input_summary: str
    result: str
    ok: bool = True


HANDS = {"read", "write", "edit", "search", "ls", "run"}


def craft(task: str, legend: str = "creator", model: str = None,
          store=None, max_turns: int = 25) -> CraftResult:
    """shape code. oracle decides, hands execute, feel watches.

    specialized loop that only uses hand abilities (read/write/edit/search/
    ls/run). the system prompt is tuned for code: read first, edit surgically,
    test after changes.

    in the world: pick up the hammer. read the grain. strike. test the edge.
    """
    feel = Feel(store=store)
    steps = []
    messages = [f"TASK: {task}"]

    info("craft", f"crafting: {task[:80]}")

    for turn in range(max_turns):
        prompt = "\n\n".join(messages)

        try:
            response = call_oracle(prompt, CRAFT_PROMPT, legend=legend, model=model)
        except ConnectionError as e:
            warn("craft", f"oracle unreachable: {e}")
            return CraftResult(
                task=task, status="paused", steps=steps,
                feel_stats=feel.stats(), error=str(e),
            )

        feel_result = feel.check(response)

        if feel_result.should_pause:
            warn("craft", f"paused at turn {turn}")
            return CraftResult(
                task=task, status="paused", steps=steps,
                feel_stats=feel.stats(), error="black state",
            )

        parsed = _parse(response)
        if parsed is None:
            steps.append(CraftStep(
                turn=turn, action="think",
                input_summary="(unparseable response)",
                result=response[:200],
            ))
            messages.append("RESULT: Your response wasn't valid JSON. Use the JSON format specified.")
            continue

        thinking = parsed.get("thinking", "")
        action = parsed.get("action", "none")
        args = parsed.get("args", {})
        done = parsed.get("done", False)

        info("craft", f"turn {turn}: {action} {'(done)' if done else ''}")

        if done:
            files = parsed.get("files_changed", [])
            answer = parsed.get("answer", thinking)
            steps.append(CraftStep(
                turn=turn, action="done",
                input_summary=thinking, result=answer,
            ))
            return CraftResult(
                task=task, status="done", answer=answer,
                files_changed=files, steps=steps,
                feel_stats=feel.stats(),
            )

        if action not in HANDS:
            steps.append(CraftStep(
                turn=turn, action=action,
                input_summary=str(args)[:100],
                result=f"not a hand ability: {action}. use: {', '.join(sorted(HANDS))}",
                ok=False,
            ))
            messages.append(f"RESULT: '{action}' is not available. You can only use: {', '.join(sorted(HANDS))}")
            continue

        ab = _REGISTRY.get(action)
        if ab is None:
            steps.append(CraftStep(
                turn=turn, action=action,
                input_summary=str(args)[:100],
                result=f"ability not registered: {action}",
                ok=False,
            ))
            messages.append(f"RESULT: Ability '{action}' not found in registry.")
            continue

        try:
            exec_result = ab.execute(
                prompt=json.dumps(args) if args else "",
                context=args,
            )
        except Exception as e:
            exec_result = {"success": False, "result": str(e), "data": {}}

        step = CraftStep(
            turn=turn, action=action,
            input_summary=str(args)[:100],
            result=exec_result["result"][:500],
            ok=exec_result["success"],
        )
        steps.append(step)

        status = "OK" if exec_result["success"] else "FAILED"
        messages.append(f"RESULT ({status}): {exec_result['result'][:2000]}")

    return CraftResult(
        task=task, status="max_turns", steps=steps,
        feel_stats=feel.stats(),
        error=f"hit {max_turns} turn limit",
    )


def _parse(response: str) -> Optional[dict]:
    """interpret the oracle's JSON response, stripping code fences."""
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
