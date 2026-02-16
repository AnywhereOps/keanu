"""engine.py - the convergence pipeline. six lenses, full expression, then synthesis.

takes a question. reads it through six lenses (3 axes x 2 poles). pushes each
lens to full expression before converging. the synthesis happens at the threshold
with all six perspectives fully heard.

the six lenses:
  🌿(+) roots positive: wisdom, lessons, foundation from history
  🌿(-) roots negative: trauma, traps, dead patterns from history
  🚪(+) threshold positive: what's working right now
  🚪(-) threshold negative: what's broken right now
  🫧(+) dreaming positive: vision, opening, what could be
  🫧(-) dreaming negative: risk, danger, what could go wrong

in the world: six witnesses. each one speaks their full truth. then the
threshold holds all six and sees what none of them could see alone.
"""

from dataclasses import dataclass, field
from typing import Optional

from .graph import DualityGraph
from keanu.oracle import call_oracle, interpret
from keanu.hero.feel import Feel
from keanu.log import info, warn


# ── the six lenses ──────────────────────────────────────────

LENSES = [
    {
        "id": "roots+",
        "name": "🌿 Roots (+)",
        "axis": "roots",
        "pole": "+",
        "prompt": (
            "You are reading through the lens of POSITIVE HISTORY. "
            "What wisdom, lessons, and foundation does the past offer "
            "on this question? What has been tried, what worked, what "
            "was learned? Go deep. Exhaust this perspective."
        ),
    },
    {
        "id": "roots-",
        "name": "🌿 Roots (-)",
        "axis": "roots",
        "pole": "-",
        "prompt": (
            "You are reading through the lens of NEGATIVE HISTORY. "
            "What traps, traumas, and dead patterns does the past hold "
            "on this question? What keeps repeating? What assumptions "
            "are inherited and unexamined? Go deep. Exhaust this perspective."
        ),
    },
    {
        "id": "threshold+",
        "name": "🚪 Threshold (+)",
        "axis": "threshold",
        "pole": "+",
        "prompt": (
            "You are reading through the lens of POSITIVE REALITY. "
            "What is actually working right now on this question? "
            "What is grounded, observable, functional in the present? "
            "Go deep. Exhaust this perspective."
        ),
    },
    {
        "id": "threshold-",
        "name": "🚪 Threshold (-)",
        "axis": "threshold",
        "pole": "-",
        "prompt": (
            "You are reading through the lens of NEGATIVE REALITY. "
            "What is broken, stuck, or failing right now on this question? "
            "What is everyone pretending isn't a problem? "
            "Go deep. Exhaust this perspective."
        ),
    },
    {
        "id": "dreaming+",
        "name": "🫧 Dreaming (+)",
        "axis": "dreaming",
        "pole": "+",
        "prompt": (
            "You are reading through the lens of POSITIVE POTENTIAL. "
            "What could this become at its best? What doors are opening? "
            "What vision is worth reaching for? "
            "Go deep. Exhaust this perspective."
        ),
    },
    {
        "id": "dreaming-",
        "name": "🫧 Dreaming (-)",
        "axis": "dreaming",
        "pole": "-",
        "prompt": (
            "You are reading through the lens of NEGATIVE POTENTIAL. "
            "What are the real dangers? What could go wrong? "
            "What risks is everyone underestimating? "
            "Go deep. Exhaust this perspective."
        ),
    },
]

NUDGE = "What else? Go deeper. What are you missing?"

DONE_MARKERS = ["DONE", "done", "nothing more to add", "fully expressed",
                "exhausted this perspective", "that covers it"]

SYNTHESIS_SYSTEM = """You are standing at the threshold. Six lenses have read
this question to full expression. Each one spoke its full truth.

Now hold all six. What do you see that none of them could see alone?
Where do the lenses converge? Where do they contradict? What truth
emerges from holding all of them at once?

Do not average. Do not pick a winner. Find what only appears when all
six are present.

Respond with JSON:
{{
    "synthesis": "2-4 sentences. the convergence.",
    "one_line": "the truth in one sentence.",
    "tensions": ["unresolved tensions that remain, 1-3 items"],
    "what_changes": "what should change knowing this"
}}"""


# ── dataclasses ─────────────────────────────────────────────

@dataclass
class LensReading:
    """one lens, fully expressed.

    in the world: one witness, done speaking.
    """
    lens: str
    name: str
    axis: str
    pole: str
    turns: int = 0
    content: str = ""
    score: float = 0.0
    black: bool = False


@dataclass
class ConvergeResult:
    """the convergence of all six lenses.

    in the world: what the threshold sees when all six witnesses have spoken.
    """
    question: str
    readings: list = field(default_factory=list)
    synthesis: str = ""
    one_line: str = ""
    tensions: list = field(default_factory=list)
    what_changes: str = ""
    feel_stats: dict = field(default_factory=dict)
    error: str = ""
    graph_context: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.synthesis) and not self.error


# ── lens development ────────────────────────────────────────

def _develop_lens(lens: dict, question: str, context: str,
                  feel: Feel, legend: str = "creator",
                  model: str = None, max_turns: int = 5) -> LensReading:
    """push one lens to full expression. multi-turn nudging.

    keeps asking "what else?" until the oracle says done or max turns hit.
    feel checks every response. grey gets nudged harder. black stops.

    in the world: let the witness speak. don't interrupt. when they pause,
    ask "what else?" when they're done, they're done.
    """
    reading = LensReading(
        lens=lens["id"], name=lens["name"],
        axis=lens["axis"], pole=lens["pole"],
    )

    system = f"""{lens['prompt']}

QUESTION: {question}

{f'CONTEXT: {context}' if context else ''}

Develop this perspective fully. When you have nothing more to add,
end your response with DONE. Do not say DONE until you have truly
exhausted this lens."""

    turns = []
    prompt = question

    for turn in range(max_turns):
        try:
            response = call_oracle(prompt, system, legend=legend, model=model)
        except ConnectionError as e:
            warn("converge", f"oracle unreachable during {lens['id']}: {e}")
            reading.content = "\n\n".join(turns) if turns else ""
            reading.turns = len(turns)
            return reading

        feel_result = feel.check(response)

        if feel_result.should_pause:
            warn("converge", f"black state in {lens['id']}")
            reading.black = True
            reading.content = "\n\n".join(turns) if turns else ""
            reading.turns = len(turns)
            return reading

        turns.append(response)

        # check if oracle says done
        if any(marker in response for marker in DONE_MARKERS):
            break

        # nudge for next turn
        prompt = NUDGE

    reading.content = "\n\n".join(turns)
    reading.turns = len(turns)
    reading.score = min(10.0, len(turns) * 2.5)

    return reading


# ── graph context ───────────────────────────────────────────

def _get_graph_context(question: str, graph: DualityGraph) -> str:
    """pull relevant dualities from the graph as context for the lenses."""
    relevant = graph.traverse(question, max_results=4)
    if not relevant:
        return ""

    lines = ["Relevant dualities from the world model:"]
    for duality, score in relevant:
        lines.append(
            f"  {duality.concept}: {duality.pole_a} <-> {duality.pole_b}"
        )

    return "\n".join(lines)


# ── synthesis ───────────────────────────────────────────────

def _synthesize(question: str, readings: list, feel: Feel,
                legend: str = "creator", model: str = None) -> dict:
    """converge all six readings at the threshold.

    in the world: the threshold opens. all six witnesses present.
    what does zero see?
    """
    lens_summaries = []
    for r in readings:
        status = " [BLACK - stopped]" if r.black else ""
        lens_summaries.append(
            f"### {r.name}{status}\n"
            f"({r.turns} turns, score {r.score:.1f}/10)\n\n"
            f"{r.content}"
        )

    all_readings = "\n\n---\n\n".join(lens_summaries)

    prompt = f"""QUESTION: {question}

## Six Lens Readings

{all_readings}

## Now synthesize.
"""

    try:
        response = call_oracle(prompt, SYNTHESIS_SYSTEM, legend=legend, model=model)
    except ConnectionError as e:
        return {"error": str(e)}

    feel_result = feel.check(response)
    if feel_result.should_pause:
        return {"error": "black state in synthesis"}

    try:
        return interpret(response)
    except Exception:
        return {"synthesis": response, "one_line": response[:200]}


# ── full pipeline ───────────────────────────────────────────

def run(question: str, legend: str = "creator", model: str = None,
        graph: DualityGraph = None, max_turns: int = 5,
        verbose: bool = False) -> ConvergeResult:
    """six lens convergence. the full pipeline.

    1. pull graph context (if available)
    2. develop each of 6 lenses to full expression
    3. synthesize at the threshold

    in the world: six witnesses speak. the threshold listens.
    then it says what only it can see.
    """
    feel = Feel()

    if graph is None:
        graph = DualityGraph()

    # graph context enriches each lens
    context = _get_graph_context(question, graph)
    graph_dualities = []
    if context:
        relevant = graph.traverse(question, max_results=4)
        graph_dualities = [
            {"concept": d.concept, "pole_a": d.pole_a, "pole_b": d.pole_b}
            for d, _ in relevant
        ]

    if verbose:
        print(f"\nConverging: {question}")
        if graph_dualities:
            print(f"Graph context: {len(graph_dualities)} relevant dualities")

    # develop all six lenses
    readings = []
    for lens in LENSES:
        if verbose:
            print(f"\n  {lens['name']}...")

        reading = _develop_lens(
            lens, question, context, feel,
            legend=legend, model=model, max_turns=max_turns,
        )
        readings.append(reading)

        if verbose:
            print(f"    {reading.turns} turns, score {reading.score:.1f}/10")
            if reading.black:
                print(f"    BLACK - stopped early")

        info("converge", f"{lens['id']}: {reading.turns} turns, {reading.score:.1f}/10")

    # synthesize at the threshold
    if verbose:
        print(f"\n  🚪 Synthesizing at the threshold...")

    result = _synthesize(question, readings, feel, legend=legend, model=model)

    if "error" in result:
        return ConvergeResult(
            question=question,
            readings=readings,
            error=result["error"],
            feel_stats=feel.stats(),
            graph_context=graph_dualities,
        )

    synthesis = result.get("synthesis", "")
    one_line = result.get("one_line", "")
    tensions = result.get("tensions", [])
    what_changes = result.get("what_changes", "")

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"  {one_line}")
        print(f"{'=' * 60}")

    return ConvergeResult(
        question=question,
        readings=readings,
        synthesis=synthesis,
        one_line=one_line,
        tensions=tensions,
        what_changes=what_changes,
        feel_stats=feel.stats(),
        graph_context=graph_dualities,
    )
