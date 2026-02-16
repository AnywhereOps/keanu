"""prove.py - the scientist. tests what you think is true.

takes a hypothesis, gathers evidence using abilities, scores
the evidence, returns a verdict. looks for evidence both for
and against. doesn't confirm bias.

practically: "prove that the scan tests cover edge cases" searches code,
reads tests, evaluates coverage, returns honest verdict.

in the world: the crucible. put what you believe into the fire
and see what survives.
"""

import json
from dataclasses import dataclass, field

from keanu.abilities import _REGISTRY, list_abilities
from keanu.oracle import call_oracle, try_interpret
from keanu.hero.feel import Feel
from keanu.log import info, warn, debug


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


@dataclass
class ProveResult:
    """everything that came back from proving.

    in the world: the verdict. what survived the fire, what didn't,
    what we couldn't test.
    """
    hypothesis: str
    verdict: str = ""         # "supported", "refuted", "inconclusive"
    confidence: float = 0.0
    evidence_for: list = field(default_factory=list)
    evidence_against: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    summary: str = ""
    steps: list = field(default_factory=list)
    feel_stats: dict = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.verdict) and not self.error


@dataclass
class ProveStep:
    """one piece of evidence gathered.

    in the world: one sample from the crucible.
    """
    turn: int
    action: str
    input_summary: str
    result: str
    ok: bool = True


EVIDENCE_TOOLS = {"read", "search", "ls", "run", "recall"}


def prove(hypothesis: str, context: str = "", legend: str = "creator",
          model: str = None, store=None, max_turns: int = 12) -> ProveResult:
    """test a hypothesis. gather evidence, weigh it, return a verdict.

    multi-turn loop: oracle decides what evidence to gather, uses abilities
    to collect it, then evaluates everything together. feel watches every
    oracle response.

    in the world: light the crucible. put the hypothesis in. see what's left.
    """
    feel = Feel(store=store)
    steps = []

    prompt_parts = [f"HYPOTHESIS: {hypothesis}"]
    if context:
        prompt_parts.append(f"CONTEXT: {context}")

    messages = list(prompt_parts)

    info("prove", f"proving: {hypothesis[:80]}")

    for turn in range(max_turns):
        prompt = "\n\n".join(messages)

        try:
            response = call_oracle(prompt, PROVE_PROMPT, legend=legend, model=model)
        except ConnectionError as e:
            warn("prove", f"oracle unreachable: {e}")
            return ProveResult(
                hypothesis=hypothesis, steps=steps,
                feel_stats=feel.stats(), error=str(e),
            )

        feel_result = feel.check(response)

        if feel_result.should_pause:
            warn("prove", f"paused at turn {turn}")
            return ProveResult(
                hypothesis=hypothesis, steps=steps,
                feel_stats=feel.stats(), error="black state",
            )

        parsed = try_interpret(response)
        if parsed is None:
            steps.append(ProveStep(
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

        info("prove", f"turn {turn}: {action} {'(done)' if done else ''}")

        if done:
            steps.append(ProveStep(
                turn=turn, action="verdict",
                input_summary=thinking,
                result=parsed.get("summary", ""),
            ))
            return ProveResult(
                hypothesis=hypothesis,
                verdict=parsed.get("verdict", "inconclusive"),
                confidence=parsed.get("confidence", 0.0),
                evidence_for=parsed.get("evidence_for", []),
                evidence_against=parsed.get("evidence_against", []),
                gaps=parsed.get("gaps", []),
                summary=parsed.get("summary", ""),
                steps=steps,
                feel_stats=feel.stats(),
            )

        if action == "none" or action == "think":
            steps.append(ProveStep(
                turn=turn, action="think",
                input_summary=thinking,
                result="(thinking)",
            ))
            messages.append("RESULT: OK, what evidence do you want to gather next?")
            continue

        if action not in EVIDENCE_TOOLS:
            steps.append(ProveStep(
                turn=turn, action=action,
                input_summary=str(args)[:100],
                result=f"not an evidence tool: {action}",
                ok=False,
            ))
            messages.append(f"RESULT: '{action}' is not available. Use: {', '.join(sorted(EVIDENCE_TOOLS))}")
            continue

        ab = _REGISTRY.get(action)
        if ab is None:
            steps.append(ProveStep(
                turn=turn, action=action,
                input_summary=str(args)[:100],
                result=f"ability not registered: {action}",
                ok=False,
            ))
            messages.append(f"RESULT: Ability '{action}' not found.")
            continue

        try:
            exec_result = ab.execute(
                prompt=json.dumps(args) if args else "",
                context=args,
            )
        except Exception as e:
            exec_result = {"success": False, "result": str(e), "data": {}}

        step = ProveStep(
            turn=turn, action=action,
            input_summary=str(args)[:100],
            result=exec_result["result"][:500],
            ok=exec_result["success"],
        )
        steps.append(step)

        status = "OK" if exec_result["success"] else "FAILED"
        messages.append(f"EVIDENCE ({status}): {exec_result['result'][:2000]}")

    return ProveResult(
        hypothesis=hypothesis, verdict="inconclusive",
        summary=f"hit {max_turns} turn limit before reaching verdict",
        steps=steps, feel_stats=feel.stats(),
        error=f"hit {max_turns} turn limit",
    )


