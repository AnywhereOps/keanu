"""breathe.py - task acceptance through duality exploration.

before the agent works, it breathes:
1. understand the task (one LLM call)
2. find 3 orthogonal duality pairs from the graph
3. accept if there's something real to explore, decline if not

declining is not refusing. it's raising concerns, staying open.
"""

import json
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from keanu.abilities.world.converge.graph import DualityGraph, Duality
from keanu.oracle import interpret
from keanu.log import info, warn, debug


@dataclass
class DualityPair:
    """One pair of orthogonal dualities to explore."""
    a: Duality
    b: Duality
    relevance: float = 0.0

    @property
    def label(self) -> str:
        return f"{self.a.concept} x {self.b.concept}"


@dataclass
class TaskAssessment:
    """What the agent thinks about a task before starting."""
    accepted: bool
    question: str
    understanding: str = ""
    pairs: List[DualityPair] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)

    @property
    def pair_count(self) -> int:
        return len(self.pairs)


UNDERSTAND_SYSTEM = """You're sitting with a question before we start.
What's being asked, what could be produced,
and what concerns you have. Speak in guidance, not authority."""

UNDERSTAND_PROMPT = """Sit with this for a moment. What is it really asking?
What could we produce that would be genuinely useful?
What concerns do you have about exploring this?

QUESTION: {question}

OUTPUT FORMAT (strict JSON):
{{
    "understanding": "what this question is really asking (1-2 sentences)",
    "deliverables": ["concrete thing we could produce 1", "thing 2"],
    "concerns": ["concern about exploring this, if any"]
}}"""


def find_top_pairs(query: str, graph: DualityGraph,
                   n: int = 3) -> List[DualityPair]:
    """Find n non-overlapping orthogonal duality pairs for a query.

    Greedy selection: pick the best pair, remove those dualities,
    pick the next best pair, etc. No duality reused across pairs.
    """
    relevant = graph.traverse(query, max_results=15)
    if len(relevant) < 2:
        return []

    used_ids = set()
    pairs = []

    for _ in range(n):
        best_pair = None
        best_score = 0

        for i, (d1, s1) in enumerate(relevant):
            if d1.id in used_ids:
                continue
            for d2, s2 in relevant[i + 1:]:
                if d2.id in used_ids:
                    continue

                # orthogonality bonus
                is_ortho = (d2.id in d1.orthogonal_ids or
                            d1.id in d2.orthogonal_ids)
                shared_parents = set(d1.parent_ids) & set(d2.parent_ids)
                independence = 1.0 if is_ortho else (0.5 if not shared_parents else 0.2)

                combined = (s1 + s2) * independence

                if combined > best_score:
                    best_score = combined
                    best_pair = DualityPair(a=d1, b=d2, relevance=combined)

        if best_pair is None:
            break

        pairs.append(best_pair)
        used_ids.add(best_pair.a.id)
        used_ids.add(best_pair.b.id)

    return pairs


def breathe(question: str, feel, graph: DualityGraph,
            legend: str = "ollama", model: str = None) -> TaskAssessment:
    """Breathe before working. Understand the task, find dualities, decide.

    Returns TaskAssessment with accepted=True if we should proceed.
    If declined, returns concerns (not excuses).
    """
    # Step 1: Understand the task via LLM
    prompt = UNDERSTAND_PROMPT.format(question=question)
    result = feel.felt_call(prompt, UNDERSTAND_SYSTEM, legend, model)

    if result.should_pause:
        warn("breathe", "paused during task understanding")
        return TaskAssessment(
            accepted=False,
            question=question,
            concerns=["Something felt off while sitting with this."],
        )

    # Parse understanding
    understanding = ""
    deliverables = []
    concerns = []

    try:
        parsed = interpret(result.response)
        understanding = parsed.get("understanding", "")
        deliverables = parsed.get("deliverables", [])
        concerns = parsed.get("concerns", [])
        # filter empty strings from concerns
        concerns = [c for c in concerns if c and c.strip()]
    except (json.JSONDecodeError, Exception) as e:
        debug("breathe", f"could not parse understanding: {e}")
        understanding = result.response[:500]

    info("breathe", f"understood: {understanding[:80]}")

    # Step 2: Find duality pairs
    pairs = find_top_pairs(question, graph, n=3)
    info("breathe", f"found {len(pairs)} duality pairs")
    for p in pairs:
        debug("breathe", f"  pair: {p.label} (relevance: {p.relevance:.2f})")

    # Step 3: Accept or decline
    accepted = len(pairs) >= 1 and len(deliverables) >= 1

    if not accepted and not concerns:
        concerns.append(
            "Could not find enough duality pairs to explore this meaningfully."
        )

    assessment = TaskAssessment(
        accepted=accepted,
        question=question,
        understanding=understanding,
        pairs=pairs,
        concerns=concerns,
        deliverables=deliverables,
    )

    if accepted:
        info("breathe", f"accepted: {len(pairs)} pairs, {len(deliverables)} deliverables")
    else:
        info("breathe", f"declined: {'; '.join(concerns)}")

    return assessment
