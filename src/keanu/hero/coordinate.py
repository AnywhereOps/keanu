"""coordinate.py - multi-agent coordination.

architect plans, craft builds, prove verifies.
agents share context through working memory.
pipeline execution with parallel and sequential steps.

in the world: the war room. many minds, one mission.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum


class AgentRole(Enum):
    ARCHITECT = "architect"  # plans tasks
    CRAFT = "craft"          # builds code
    PROVE = "prove"          # verifies claims
    EXPLORE = "explore"      # investigates


@dataclass
class AgentTask:
    """a task assigned to an agent."""
    role: AgentRole
    task: str
    depends_on: list[str] = field(default_factory=list)  # task IDs
    id: str = ""
    status: str = "pending"  # pending, running, done, failed
    result: dict = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.role.value}_{int(time.time() * 1000) % 100000}"


@dataclass
class PipelineResult:
    """result of a multi-agent pipeline."""
    success: bool
    tasks: list[AgentTask] = field(default_factory=list)
    duration_s: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def completed(self) -> list[AgentTask]:
        return [t for t in self.tasks if t.status == "done"]

    @property
    def failed(self) -> list[AgentTask]:
        return [t for t in self.tasks if t.status == "failed"]


@dataclass
class Disagreement:
    """when agents disagree on something."""
    topic: str
    positions: dict[str, str]  # role -> position
    resolution: str = ""       # how it was resolved
    resolved_by: str = ""      # human, vote, architect


# ============================================================
# PIPELINE
# ============================================================

class Pipeline:
    """execute a sequence of agent tasks with dependency ordering."""

    def __init__(self, legend: str = "creator", model: str | None = None,
                 store=None, max_workers: int = 3):
        self.legend = legend
        self.model = model
        self.store = store
        self.max_workers = max_workers
        self.tasks: list[AgentTask] = []
        self.context: dict[str, str] = {}  # shared context between agents

    def add(self, role: AgentRole, task: str, depends_on: list[str] | None = None,
            task_id: str = "") -> str:
        """add a task to the pipeline. returns the task ID."""
        t = AgentTask(role=role, task=task, depends_on=depends_on or [])
        if task_id:
            t.id = task_id
        self.tasks.append(t)
        return t.id

    def run(self) -> PipelineResult:
        """execute the pipeline respecting dependencies."""
        start = time.time()
        completed_ids: set[str] = set()
        errors: list[str] = []

        # topological execution
        remaining = list(self.tasks)
        while remaining:
            # find tasks whose dependencies are met
            ready = [t for t in remaining if all(d in completed_ids for d in t.depends_on)]

            if not ready:
                # deadlock
                errors.append(f"deadlock: {len(remaining)} tasks waiting on unresolvable deps")
                for t in remaining:
                    t.status = "failed"
                break

            # run ready tasks in parallel
            if len(ready) == 1 or self.max_workers <= 1:
                for t in ready:
                    self._run_task(t)
                    if t.status == "done":
                        completed_ids.add(t.id)
                    elif t.status == "failed":
                        errors.append(f"{t.id}: {t.result.get('error', 'unknown')}")
            else:
                with ThreadPoolExecutor(max_workers=min(self.max_workers, len(ready))) as pool:
                    futures = {pool.submit(self._run_task, t): t for t in ready}
                    for future in as_completed(futures):
                        t = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            t.status = "failed"
                            t.result = {"error": str(e)}
                        if t.status == "done":
                            completed_ids.add(t.id)
                        elif t.status == "failed":
                            errors.append(f"{t.id}: {t.result.get('error', 'unknown')}")

            remaining = [t for t in remaining if t.id not in completed_ids and t.status != "failed"]

        duration = time.time() - start
        success = all(t.status == "done" for t in self.tasks)

        return PipelineResult(
            success=success,
            tasks=self.tasks,
            duration_s=duration,
            errors=errors,
        )

    def _run_task(self, task: AgentTask):
        """run a single agent task."""
        task.status = "running"
        task.started_at = time.time()

        try:
            # inject shared context
            full_task = task.task
            if self.context:
                context_str = "\n".join(f"[{k}]: {v}" for k, v in self.context.items())
                full_task = f"Context from previous agents:\n{context_str}\n\nTask: {task.task}"

            result = _dispatch_to_agent(task.role, full_task, self.legend, self.model, self.store)
            task.result = result
            task.status = "done"

            # store result in shared context
            if result.get("answer"):
                self.context[task.id] = result["answer"][:500]

        except Exception as e:
            task.status = "failed"
            task.result = {"error": str(e)}

        task.finished_at = time.time()


def _dispatch_to_agent(role: AgentRole, task: str, legend: str,
                       model: str | None, store) -> dict:
    """dispatch a task to the appropriate agent."""
    from keanu.hero.do import run as do_run, craft, prove

    if role == AgentRole.CRAFT:
        result = craft(task, legend=legend, model=model, store=store, max_turns=15)
    elif role == AgentRole.PROVE:
        result = prove(task, legend=legend, model=model, store=store, max_turns=15)
    elif role == AgentRole.ARCHITECT:
        from keanu.hero.dream import dream
        result = dream(task, legend=legend, model=model)
        return {
            "ok": result.ok,
            "answer": str(result.phases) if result.ok else result.error,
        }
    elif role == AgentRole.EXPLORE:
        from keanu.hero.do import AgentLoop, EXPLORE_CONFIG
        loop = AgentLoop(EXPLORE_CONFIG, store=store)
        result = loop.run(task, legend=legend, model=model)
    else:
        result = do_run(task=task, legend=legend, model=model, store=store, max_turns=15)

    return {
        "ok": result.ok,
        "answer": result.answer or "",
        "steps": len(result.steps),
        "extras": result.extras,
        "error": result.error or "",
    }


# ============================================================
# COMMON PIPELINES
# ============================================================

def plan_build_verify(goal: str, legend: str = "creator", model: str | None = None,
                      store=None) -> PipelineResult:
    """the standard pipeline: plan, then build, then verify."""
    pipeline = Pipeline(legend=legend, model=model, store=store)

    plan_id = pipeline.add(AgentRole.ARCHITECT, f"plan how to: {goal}", task_id="plan")
    build_id = pipeline.add(AgentRole.CRAFT, f"implement: {goal}", depends_on=[plan_id], task_id="build")
    pipeline.add(AgentRole.PROVE, f"verify the implementation of: {goal}", depends_on=[build_id], task_id="verify")

    return pipeline.run()


def explore_then_build(question: str, task: str, legend: str = "creator",
                       model: str | None = None, store=None) -> PipelineResult:
    """explore first, then build based on findings."""
    pipeline = Pipeline(legend=legend, model=model, store=store)

    explore_id = pipeline.add(AgentRole.EXPLORE, question, task_id="explore")
    pipeline.add(AgentRole.CRAFT, task, depends_on=[explore_id], task_id="build")

    return pipeline.run()


def parallel_investigate(questions: list[str], legend: str = "creator",
                         model: str | None = None, store=None) -> PipelineResult:
    """investigate multiple questions in parallel."""
    pipeline = Pipeline(legend=legend, model=model, store=store, max_workers=len(questions))

    for i, q in enumerate(questions):
        pipeline.add(AgentRole.EXPLORE, q, task_id=f"explore_{i}")

    return pipeline.run()


# ============================================================
# DISAGREEMENT PROTOCOL
# ============================================================

def detect_disagreement(results: dict[str, dict]) -> Disagreement | None:
    """detect if agents disagree on a topic.

    takes a dict of {role: result} and checks for contradictions.
    """
    positions = {}
    for role, result in results.items():
        answer = result.get("answer", "")
        if answer:
            positions[role] = answer[:200]

    if len(positions) < 2:
        return None

    # simple heuristic: check for negation patterns
    answers = list(positions.values())
    for i, a in enumerate(answers):
        for j, b in enumerate(answers):
            if i >= j:
                continue
            lower_a = a.lower()
            lower_b = b.lower()
            # check for contradiction signals
            contradictions = [
                ("yes" in lower_a and "no" in lower_b),
                ("no" in lower_a and "yes" in lower_b),
                ("should" in lower_a and "should not" in lower_b),
                ("can" in lower_a and "cannot" in lower_b),
            ]
            if any(contradictions):
                roles = list(positions.keys())
                return Disagreement(
                    topic="agent positions conflict",
                    positions=positions,
                )

    return None
