"""decompose.py - break complex tasks into subtasks.

looks at a task and decides: is this one thing or many things?
if many: use dream.py to plan, then run each step through the loop.
if one: just run it directly.

in the world: you don't build a house in one step.
you lay the foundation, frame the walls, then add the roof.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Subtask:
    """one step extracted from a complex task."""
    action: str
    phase: str = ""
    depends_on: str = ""
    why: str = ""
    status: str = "pending"  # pending, running, done, failed


@dataclass
class Decomposition:
    """the result of breaking down a task."""
    original: str
    subtasks: list = field(default_factory=list)
    is_complex: bool = False
    phases: list = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.subtasks)

    @property
    def done(self) -> int:
        return sum(1 for s in self.subtasks if s.status == "done")

    @property
    def failed(self) -> int:
        return sum(1 for s in self.subtasks if s.status == "failed")

    @property
    def progress(self) -> str:
        return f"{self.done}/{self.total}"


def is_complex(task: str) -> bool:
    """decide if a task needs decomposition.

    heuristics:
    - multiple sentences or bullet points
    - words like "and then", "also", "first...then"
    - mentions multiple files
    - longer than 200 chars
    - explicit structure markers
    """
    task_lower = task.lower()

    # bullet point lines (count each occurrence)
    bullet_count = len(re.findall(r'(?:^|\n)\s*[-*]\s+', task))
    if bullet_count >= 2:
        return True

    # explicit multi-step markers
    multi_markers = [
        "and then", "after that", "first,", "then,",
        "1.", "2.", "step 1", "step 2",
    ]
    marker_count = sum(1 for m in multi_markers if m in task_lower)
    if marker_count >= 2:
        return True

    # multiple sentences (3+)
    sentences = [s.strip() for s in re.split(r'[.!?]+', task) if s.strip()]
    if len(sentences) >= 3:
        return True

    # mentions multiple files
    file_patterns = re.findall(r'\b\w+\.\w{1,4}\b', task)
    if len(file_patterns) >= 3:
        return True

    # long task
    if len(task) > 300:
        return True

    return False


def decompose_simple(task: str) -> Decomposition:
    """break a task into subtasks using simple heuristics.

    no LLM call. splits on sentence boundaries, bullet points,
    and numbered steps. fast but less intelligent than dream.
    """
    subtasks = []

    # try numbered steps first
    numbered = re.findall(r'(?:^|\n)\s*(\d+[\.\)]\s*.+?)(?=\n\s*\d+[\.\)]|\n\n|$)', task, re.DOTALL)
    if numbered:
        for step in numbered:
            step = re.sub(r'^\d+[\.\)]\s*', '', step).strip()
            if step:
                subtasks.append(Subtask(action=step))
        return Decomposition(
            original=task, subtasks=subtasks, is_complex=True,
        )

    # try bullet points
    bullets = re.findall(r'(?:^|\n)\s*[-*]\s*(.+)', task)
    if len(bullets) >= 2:
        for bullet in bullets:
            subtasks.append(Subtask(action=bullet.strip()))
        return Decomposition(
            original=task, subtasks=subtasks, is_complex=True,
        )

    # try "and then" / "first...then" splitting
    if " and then " in task.lower() or "first," in task.lower():
        parts = re.split(r'\band then\b|\bfirst,?\b|\bthen,?\b', task, flags=re.IGNORECASE)
        parts = [p.strip().strip(",").strip() for p in parts if p.strip()]
        if len(parts) >= 2:
            for part in parts:
                subtasks.append(Subtask(action=part))
            return Decomposition(
                original=task, subtasks=subtasks, is_complex=True,
            )

    # fallback: split on sentence boundaries
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', task) if s.strip()]
    if len(sentences) >= 3:
        for sentence in sentences:
            subtasks.append(Subtask(action=sentence))
        return Decomposition(
            original=task, subtasks=subtasks, is_complex=True,
        )

    # not complex enough to decompose
    return Decomposition(original=task, subtasks=[], is_complex=False)


def decompose_with_dream(task: str, legend: str = "creator",
                         model: str = None) -> Decomposition:
    """break a task into subtasks using dream.py (LLM-powered).

    calls the oracle to plan the work. more intelligent than simple
    decomposition but costs a fire call.
    """
    from keanu.hero.dream import dream

    result = dream(task, legend=legend, model=model)
    if not result.ok:
        # fall back to simple decomposition
        return decompose_simple(task)

    subtasks = []
    phases = []
    for phase in result.phases:
        phase_name = phase.get("name", "")
        phases.append(phase_name)
        for step in phase.get("steps", []):
            subtasks.append(Subtask(
                action=step.get("action", ""),
                phase=phase_name,
                depends_on=step.get("depends_on", ""),
                why=step.get("why", ""),
            ))

    return Decomposition(
        original=task, subtasks=subtasks,
        is_complex=True, phases=phases,
    )


def decompose(task: str, use_dream: bool = False,
              legend: str = "creator", model: str = None) -> Decomposition:
    """decompose a task. uses dream if requested and task is complex.

    default behavior: simple heuristic decomposition (no LLM).
    pass use_dream=True for LLM-powered planning.
    """
    if not is_complex(task):
        return Decomposition(original=task, subtasks=[], is_complex=False)

    if use_dream:
        return decompose_with_dream(task, legend=legend, model=model)

    return decompose_simple(task)
