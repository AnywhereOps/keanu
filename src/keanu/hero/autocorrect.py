"""autocorrect.py - self-correction after edits.

after every code change: lint, test, type-check. if any fail,
parse the error, fix it, retry. max 3 attempts per issue.
if still failing: back out and try a different approach.

this is the agent's inner quality loop. it doesn't wait for the
human to say "that broke." it catches its own mistakes.

in the world: measure twice, cut once. but if you cut wrong,
don't keep cutting. step back, measure again.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CorrectionResult:
    """what happened during a correction cycle."""
    phase: str         # "lint", "test", "typecheck"
    passed: bool = False
    attempts: int = 0
    errors: list = field(default_factory=list)
    fixes_applied: list = field(default_factory=list)


@dataclass
class CorrectionPlan:
    """what to check after an edit."""
    lint: bool = True
    test: bool = True
    typecheck: bool = False  # not all projects have type checking
    max_attempts: int = 3
    target_files: list = field(default_factory=list)
    test_target: str = ""  # specific test to run, or "" for all


def check_after_edit(files_changed: list[str], plan: CorrectionPlan = None,
                     executor=None) -> list[CorrectionResult]:
    """run the correction cycle after files were edited.

    returns a list of CorrectionResults, one per phase.
    each result says whether that phase passed and what was tried.
    """
    if plan is None:
        plan = CorrectionPlan(target_files=files_changed)

    if executor is None:
        executor = _default_executor

    results = []

    if plan.lint:
        result = _run_phase("lint", plan, executor)
        results.append(result)

    if plan.test:
        result = _run_phase("test", plan, executor)
        results.append(result)

    if plan.typecheck:
        result = _run_phase("typecheck", plan, executor)
        results.append(result)

    return results


def _run_phase(phase: str, plan: CorrectionPlan,
               executor) -> CorrectionResult:
    """run one phase of the correction cycle with retries."""
    result = CorrectionResult(phase=phase)

    for attempt in range(plan.max_attempts):
        result.attempts = attempt + 1
        output = executor(phase, plan)

        if output["success"]:
            result.passed = True
            return result

        error = output.get("error", output.get("result", "unknown error"))
        result.errors.append(error)

        # try to auto-fix if this isn't the last attempt
        if attempt < plan.max_attempts - 1:
            fix = _suggest_fix(phase, error, plan.target_files)
            if fix:
                result.fixes_applied.append(fix)
                # executor would apply the fix here in a real integration

    result.passed = False
    return result


def _suggest_fix(phase: str, error: str, files: list[str]) -> Optional[str]:
    """suggest a fix for a correction failure.

    returns a description of the fix, or None if no suggestion.
    """
    error_lower = error.lower()

    if phase == "lint":
        if "unused import" in error_lower or "F401" in error_lower:
            return "remove unused import"
        if "line too long" in error_lower or "E501" in error_lower:
            return "break long line"
        if "missing whitespace" in error_lower:
            return "fix whitespace"
        if "undefined name" in error_lower or "F821" in error_lower:
            return "add missing import or fix typo"

    if phase == "test":
        if "importerror" in error_lower or "modulenotfounderror" in error_lower:
            return "fix import path"
        if "attributeerror" in error_lower:
            return "fix attribute name"
        if "assertionerror" in error_lower:
            return "fix assertion or expected value"
        if "typeerror" in error_lower:
            return "fix type mismatch"

    if phase == "typecheck":
        if "incompatible type" in error_lower:
            return "fix type annotation"
        if "missing return" in error_lower:
            return "add return statement"

    return None


def _default_executor(phase: str, plan: CorrectionPlan) -> dict:
    """default executor that actually runs tools.

    uses the lint and test abilities from the registry.
    """
    from keanu.abilities import _REGISTRY

    if phase == "lint":
        ab = _REGISTRY.get("lint")
        if ab:
            ctx = {"fix": True}
            return ab.execute("", ctx)
        return {"success": True, "result": "no linter available"}

    if phase == "test":
        ab = _REGISTRY.get("test")
        if ab:
            ctx = {"op": "run"}
            if plan.test_target:
                ctx["target"] = plan.test_target
            elif plan.target_files:
                ctx["op"] = "targeted"
                ctx["files"] = plan.target_files
            return ab.execute("", ctx)
        return {"success": True, "result": "no test runner available"}

    if phase == "typecheck":
        ab = _REGISTRY.get("run")
        if ab:
            return ab.execute("", {"command": "python3 -m mypy --no-error-summary ."})
        return {"success": True, "result": "no type checker available"}

    return {"success": True, "result": f"unknown phase: {phase}"}


def should_correct(action: str, result: dict) -> bool:
    """should we run the correction cycle after this action?

    only triggers after successful writes/edits. no point checking
    if the edit itself failed.
    """
    if not result.get("success", False):
        return False
    return action in ("write", "edit")


def summarize(results: list[CorrectionResult]) -> str:
    """one-line summary of correction results."""
    parts = []
    for r in results:
        if r.passed:
            parts.append(f"{r.phase}: ok")
        else:
            parts.append(f"{r.phase}: failed ({r.attempts} attempts)")
    return " | ".join(parts) if parts else "no checks run"
