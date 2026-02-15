"""dream.py - the planner. dreams the path before walking it.

takes a goal or problem and breaks it into sequenced steps with
dependencies. the oracle sees the road, dream.py maps it.

practically: "dream up a plan for X" returns structured phases and steps
that do.py or craft.py can execute.

in the world: you dream the path before you walk it.
"""

from dataclasses import dataclass, field

from keanu.oracle import call_oracle, interpret
from keanu.hero.feel import Feel
from keanu.log import info, warn


DREAM_PROMPT = """You are a planner. Your job is to break a goal into clear,
sequenced phases and steps.

Respond with JSON:
{
    "phases": [
        {
            "name": "short phase name",
            "steps": [
                {
                    "action": "what to do (imperative, specific)",
                    "depends_on": "previous step action or null if none",
                    "why": "one sentence, why this step matters"
                }
            ]
        }
    ]
}

Rules:
- Each step should be small enough to do in one sitting.
- Steps within a phase can run in parallel unless depends_on says otherwise.
- Phases run in order. Phase 2 waits for phase 1 to finish.
- Be specific. "write tests" is bad. "write tests for the parse function in codec.py" is good.
- 2-5 phases. 1-5 steps per phase. No filler phases.
- If context is provided, use it. Don't invent requirements that aren't there."""


@dataclass
class DreamResult:
    """everything that came back from dreaming.

    in the world: the map. phases are legs of the journey, steps are footfalls.
    """
    goal: str
    phases: list = field(default_factory=list)
    total_steps: int = 0
    raw: str = ""
    feel_stats: dict = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return len(self.phases) > 0 and not self.error


def dream(goal: str, context: str = "", legend: str = "creator",
          model: str = None) -> DreamResult:
    """dream up a plan. oracle sees the road, we map it.

    takes a goal string and optional context. asks the oracle to break it
    into phases and steps. feel checks the response for aliveness.
    returns structured DreamResult with phases, steps, and dependencies.

    in the world: close your eyes. see the path. open them. walk.
    """
    feel = Feel()

    prompt = f"GOAL: {goal}"
    if context:
        prompt += f"\n\nCONTEXT:\n{context}"

    info("dream", f"dreaming: {goal[:80]}")

    try:
        response = call_oracle(prompt, DREAM_PROMPT, legend=legend, model=model)
    except ConnectionError as e:
        warn("dream", f"oracle unreachable: {e}")
        return DreamResult(goal=goal, error=str(e), feel_stats=feel.stats())

    feel_result = feel.check(response)

    if feel_result.should_pause:
        warn("dream", "black state in dream response")
        return DreamResult(goal=goal, error="black state", feel_stats=feel.stats())

    try:
        parsed = interpret(response)
    except Exception:
        return DreamResult(
            goal=goal, raw=response,
            error="couldn't parse oracle response",
            feel_stats=feel.stats(),
        )

    phases = parsed.get("phases", [])
    total = sum(len(p.get("steps", [])) for p in phases)

    info("dream", f"dreamed {len(phases)} phases, {total} steps")

    return DreamResult(
        goal=goal,
        phases=phases,
        total_steps=total,
        raw=response,
        feel_stats=feel.stats(),
    )
