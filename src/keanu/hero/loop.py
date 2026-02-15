"""loop.py - the agentic loop.

breathe -> explore (6 leaf agents) -> synthesize (3 pairs + 1 meta) -> commit.

17 LLM calls total: 1 breathe + 6 explore + 6 write + 3 pair synth + 1 final.
all leaf agents run in parallel via ThreadPoolExecutor (I/O bound).
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional

from keanu.converge.graph import DualityGraph, Duality
from keanu.converge.engine import parse_json_response
from keanu.hero.feel import Feel
from keanu.hero.breathe import breathe, TaskAssessment, DualityPair
from keanu.log import info, warn, debug, span


# ============================================================
# PROMPTS
# ============================================================

GUIDANCE_SYSTEM = """You are one perspective in a larger convergence.
Speak in guidance, not authority. You see part of the truth.
Other perspectives see other parts. Together we converge."""

EXPLORE_PROMPT = """You're looking at this through {pole} (one pole of {concept}).

This is your vantage point. What do you see from here that others might miss?
What truths does this perspective hold? What are its blind spots?
Be honest about both.

QUESTION: {question}

Respond in 2-4 paragraphs. No JSON. Just think clearly from where you stand."""

WRITE_PROMPT = """You explored a question from the perspective of {pole}.
What's the core of what you found?

Your exploration:
{exploration}

QUESTION: {question}

OUTPUT FORMAT (strict JSON):
{{
    "position": "your core claim in 1-2 sentences",
    "sees": "what this perspective uniquely sees",
    "misses": "what this perspective is blind to",
    "key_insight": "the one thing worth carrying forward"
}}"""

PAIR_SYNTH_PROMPT = """Synthesize two opposing perspectives on the same question.

DUALITY: {concept} ({pole_a} vs {pole_b})

{pole_a}:
Position: {side_a_position}
Sees: {side_a_sees}
Misses: {side_a_misses}
Key insight: {side_a_insight}

{pole_b}:
Position: {side_b_position}
Sees: {side_b_sees}
Misses: {side_b_misses}
Key insight: {side_b_insight}

QUESTION: {question}

What does {pole_a} see that {pole_b} misses? What does {pole_b} see that {pole_a} misses?
Build a synthesis that holds both truths without averaging them.

OUTPUT FORMAT (strict JSON):
{{
    "synthesis": "2-3 sentences that converge both sides",
    "a_truth": "what side A got right",
    "b_truth": "what side B got right",
    "emergent": "what neither side could see alone"
}}"""

FINAL_SYNTH_PROMPT = """Final convergence across {pair_count} duality syntheses.

QUESTION: {question}

{syntheses_block}

Build something none of these could reach alone.
This is not a summary. This is a convergence, a new truth
that emerges from holding all these tensions together.

OUTPUT FORMAT (strict JSON):
{{
    "convergence": "the final synthesis, 2-4 sentences",
    "one_line": "the truth in one sentence",
    "learnings": ["insight 1", "insight 2", "insight 3"],
    "what_changes": "what should change knowing this"
}}"""


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class SideResult:
    """Result from one leaf agent (one pole of one duality)."""
    pair_index: int
    side: str  # "a" or "b"
    pole: str
    concept: str
    exploration: str = ""
    position: str = ""
    sees: str = ""
    misses: str = ""
    key_insight: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.position) and not self.error


@dataclass
class PairSynthesis:
    """Synthesis of two sides of one duality pair."""
    pair_index: int
    concept: str
    pole_a: str
    pole_b: str
    side_a: Optional[SideResult] = None
    side_b: Optional[SideResult] = None
    synthesis: str = ""
    a_truth: str = ""
    b_truth: str = ""
    emergent: str = ""
    error: str = ""


@dataclass
class AgentResult:
    """Full result from the agentic loop."""
    question: str
    accepted: bool
    assessment: Optional[TaskAssessment] = None
    sides: List[SideResult] = field(default_factory=list)
    pair_syntheses: List[PairSynthesis] = field(default_factory=list)
    convergence: str = ""
    one_line: str = ""
    learnings: List[str] = field(default_factory=list)
    what_changes: str = ""
    feel_stats: dict = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.accepted and bool(self.convergence) and not self.error


# ============================================================
# LEAF AGENTS
# ============================================================

def _run_side_agent(pair_index: int, side: str, pole: str, concept: str,
                    question: str, feel: Feel,
                    backend: str, model: str) -> SideResult:
    """One leaf agent: explore then write from one pole."""
    result = SideResult(
        pair_index=pair_index,
        side=side,
        pole=pole,
        concept=concept,
    )

    with span("explore", subsystem="agent",
              pair=pair_index, side=side, pole=pole):
        # Explore
        explore_prompt = EXPLORE_PROMPT.format(
            pole=pole, side=side, concept=concept, question=question
        )
        explore_result = feel.felt_call(
            explore_prompt, GUIDANCE_SYSTEM, backend, model
        )
        if explore_result.should_pause:
            result.error = "paused during exploration"
            return result
        result.exploration = explore_result.response

        # Write
        write_prompt = WRITE_PROMPT.format(
            pole=pole, exploration=result.exploration, question=question
        )
        write_result = feel.felt_call(
            write_prompt, GUIDANCE_SYSTEM, backend, model
        )
        if write_result.should_pause:
            result.error = "paused during writing"
            return result

        try:
            parsed = parse_json_response(write_result.response)
            result.position = parsed.get("position", "")
            result.sees = parsed.get("sees", "")
            result.misses = parsed.get("misses", "")
            result.key_insight = parsed.get("key_insight", "")
        except (json.JSONDecodeError, Exception):
            result.position = write_result.response[:200]
            result.sees = ""
            result.misses = ""
            result.key_insight = ""

    return result


def _synthesize_pair(pair_index: int, pair: DualityPair,
                     side_a: SideResult, side_b: SideResult,
                     question: str, feel: Feel,
                     backend: str, model: str) -> PairSynthesis:
    """Synthesize two sides of one duality pair."""
    ps = PairSynthesis(
        pair_index=pair_index,
        concept=pair.a.concept,
        pole_a=pair.a.pole_a if side_a.side == "a" else pair.a.pole_b,
        pole_b=pair.b.pole_a if side_b.side == "a" else pair.b.pole_b,
        side_a=side_a,
        side_b=side_b,
    )

    if not side_a.ok or not side_b.ok:
        ps.error = "couldn't hear from both perspectives"
        return ps

    with span("synthesize_pair", subsystem="agent", pair=pair_index):
        prompt = PAIR_SYNTH_PROMPT.format(
            concept=pair.label,
            pole_a=side_a.pole,
            pole_b=side_b.pole,
            side_a_position=side_a.position,
            side_a_sees=side_a.sees,
            side_a_misses=side_a.misses,
            side_a_insight=side_a.key_insight,
            side_b_position=side_b.position,
            side_b_sees=side_b.sees,
            side_b_misses=side_b.misses,
            side_b_insight=side_b.key_insight,
            question=question,
        )
        result = feel.felt_call(prompt, GUIDANCE_SYSTEM, backend, model)
        if result.should_pause:
            ps.error = "paused during synthesis"
            return ps

        try:
            parsed = parse_json_response(result.response)
            ps.synthesis = parsed.get("synthesis", "")
            ps.a_truth = parsed.get("a_truth", "")
            ps.b_truth = parsed.get("b_truth", "")
            ps.emergent = parsed.get("emergent", "")
        except (json.JSONDecodeError, Exception):
            ps.synthesis = result.response[:300]

    return ps


# ============================================================
# MAIN LOOP
# ============================================================

def run(question: str, backend: str = "ollama", model: str = None,
        graph: DualityGraph = None, store=None,
        max_workers: int = 3) -> AgentResult:
    """The agentic loop. Breathe, explore, synthesize, commit.

    Args:
        question: What to explore
        backend: "ollama" or "claude"
        model: Model name (None for default)
        graph: DualityGraph (created if None)
        store: MemberberryStore for learnings (optional)
        max_workers: ThreadPoolExecutor workers for leaf agents
    """
    if graph is None:
        graph = DualityGraph()

    feel = Feel(store=store)

    # ---- BREATHE ----
    with span("breathe", subsystem="agent"):
        assessment = breathe(question, feel, graph, backend, model)

    if not assessment.accepted:
        return AgentResult(
            question=question,
            accepted=False,
            assessment=assessment,
            feel_stats=feel.stats(),
        )

    info("agent", f"accepted with {assessment.pair_count} pairs")

    # ---- EXPLORE + WRITE (parallel leaf agents) ----
    sides: List[SideResult] = []

    with span("explore_all", subsystem="agent"):
        futures = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i, pair in enumerate(assessment.pairs):
                # Side A: pole_a of duality a
                fa = executor.submit(
                    _run_side_agent, i, "a", pair.a.pole_a, pair.a.concept,
                    question, feel, backend, model
                )
                futures[fa] = (i, "a")

                # Side B: pole_b of duality a (exploring the OTHER pole)
                fb = executor.submit(
                    _run_side_agent, i, "b", pair.a.pole_b, pair.a.concept,
                    question, feel, backend, model
                )
                futures[fb] = (i, "b")

            for future in as_completed(futures):
                pair_idx, side = futures[future]
                try:
                    result = future.result()
                    sides.append(result)
                    if result.ok:
                        debug("agent", f"side {pair_idx}{side} done: {result.pole}")
                    else:
                        warn("agent", f"side {pair_idx}{side} failed: {result.error}")
                except Exception as e:
                    warn("agent", f"side {pair_idx}{side} exception: {e}")
                    sides.append(SideResult(
                        pair_index=pair_idx, side=side,
                        pole="unknown", concept="unknown",
                        error=str(e),
                    ))

    # ---- SYNTHESIZE PAIRS ----
    pair_syntheses: List[PairSynthesis] = []

    with span("synthesize_all", subsystem="agent"):
        for i, pair in enumerate(assessment.pairs):
            side_a = next((s for s in sides if s.pair_index == i and s.side == "a"), None)
            side_b = next((s for s in sides if s.pair_index == i and s.side == "b"), None)

            if side_a is None or side_b is None:
                pair_syntheses.append(PairSynthesis(
                    pair_index=i, concept=pair.label,
                    pole_a=pair.a.pole_a, pole_b=pair.a.pole_b,
                    error="missing side results",
                ))
                continue

            ps = _synthesize_pair(i, pair, side_a, side_b,
                                  question, feel, backend, model)
            pair_syntheses.append(ps)

    # ---- FINAL SYNTHESIS ----
    convergence = ""
    one_line = ""
    learnings = []
    what_changes = ""

    valid_syntheses = [ps for ps in pair_syntheses if ps.synthesis]

    if valid_syntheses:
        with span("final_synthesis", subsystem="agent"):
            syntheses_block = ""
            for ps in valid_syntheses:
                syntheses_block += f"\nSYNTHESIS ({ps.concept}):\n{ps.synthesis}\n"
                if ps.emergent:
                    syntheses_block += f"Emergent insight: {ps.emergent}\n"

            final_prompt = FINAL_SYNTH_PROMPT.format(
                pair_count=len(valid_syntheses),
                question=question,
                syntheses_block=syntheses_block,
            )
            final_result = feel.felt_call(
                final_prompt, GUIDANCE_SYSTEM, backend, model
            )

            if not final_result.should_pause:
                try:
                    parsed = parse_json_response(final_result.response)
                    convergence = parsed.get("convergence", "")
                    one_line = parsed.get("one_line", "")
                    learnings = parsed.get("learnings", [])
                    what_changes = parsed.get("what_changes", "")
                except (json.JSONDecodeError, Exception):
                    convergence = final_result.response[:500]
                    one_line = convergence[:200]

    # ---- COMMIT (store learnings) ----
    if store and learnings:
        with span("commit", subsystem="agent"):
            from keanu.memory.memberberry import Memory
            for learning in learnings:
                memory = Memory(
                    content=f"[AGENT] {learning}",
                    memory_type="insight",
                    tags=["agent", "convergence"],
                    importance=6,
                    context=f"question: {question[:100]}",
                    source="agent",
                )
                store.remember(memory)
            info("agent", f"committed {len(learnings)} learnings")

    result = AgentResult(
        question=question,
        accepted=True,
        assessment=assessment,
        sides=sides,
        pair_syntheses=pair_syntheses,
        convergence=convergence,
        one_line=one_line,
        learnings=learnings,
        what_changes=what_changes,
        feel_stats=feel.stats(),
    )

    info("agent", f"done: {one_line[:80]}")
    return result
