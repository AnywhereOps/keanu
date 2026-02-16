"""test: discover and run tests, parse failures.

pytest first. structured output: file, line, assertion, traceback.
the agent runs tests after edits, knows what broke and where.
invoked explicitly by the loop, never by keyword match.

in the world: the proving ground. every change tested, every failure traced.
"""

import json
import re
import subprocess
from pathlib import Path

from keanu.abilities import Ability, ability


def _run_pytest(*args, cwd=None):
    """run pytest with args, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", *args],
            capture_output=True, text=True, timeout=120,
            cwd=cwd or str(Path.cwd()),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "pytest timed out (120s)"
    except FileNotFoundError:
        return -1, "", "python not found"


def _parse_failures(stdout, stderr):
    """parse pytest output into structured failure list."""
    failures = []
    combined = stdout + "\n" + stderr

    # parse FAILED lines: FAILED tests/test_foo.py::test_bar - AssertionError: ...
    failed_pattern = re.compile(r"FAILED\s+(\S+?)::(\S+?)(?:\s+-\s+(.+))?$", re.MULTILINE)
    for m in failed_pattern.finditer(combined):
        failures.append({
            "file": m.group(1),
            "test": m.group(2),
            "error": m.group(3) or "",
        })

    # parse ERROR lines: ERROR tests/test_foo.py::test_bar - ...
    error_pattern = re.compile(r"ERROR\s+(\S+?)::(\S+?)(?:\s+-\s+(.+))?$", re.MULTILINE)
    for m in error_pattern.finditer(combined):
        failures.append({
            "file": m.group(1),
            "test": m.group(2),
            "error": m.group(3) or "collection error",
        })

    return failures


def _parse_summary(stdout):
    """parse the pytest summary line."""
    # "5 passed, 2 failed, 1 error in 3.45s"
    m = re.search(r"=+ (.+?) =+\s*$", stdout, re.MULTILINE)
    if m:
        return m.group(1)
    return ""


@ability
class TestAbility(Ability):

    name = "test"
    description = "Run tests: discover, execute, parse failures"
    keywords = ["test", "pytest", "unittest", "tests", "run tests"]
    cast_line = "test enters the proving ground..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        ctx = context or {}
        op = ctx.get("op", "run")
        return _OPS.get(op, _op_unknown)(ctx)


def _op_run(ctx):
    """run tests. target= specific file/test, verbose= show all output."""
    args = ["-v", "--tb=short", "--no-header", "-q"]
    target = ctx.get("target", "")
    if target:
        args.append(target)

    # extra pytest args
    extra = ctx.get("args", [])
    if extra:
        args.extend(extra)

    rc, stdout, stderr = _run_pytest(*args)

    summary = _parse_summary(stdout)
    failures = _parse_failures(stdout, stderr) if rc != 0 else []

    output = stdout
    if stderr and "error" in stderr.lower():
        output += f"\n--- stderr ---\n{stderr}"

    if len(output) > 8000:
        output = output[:8000] + f"\n... (truncated, {len(output)} total chars)"

    return {
        "success": rc == 0,
        "result": output if output.strip() else summary or "(no output)",
        "data": {
            "returncode": rc,
            "summary": summary,
            "failures": failures,
            "failure_count": len(failures),
        },
    }


def _op_discover(ctx):
    """discover tests without running them."""
    args = ["--collect-only", "-q"]
    target = ctx.get("target", "")
    if target:
        args.append(target)

    rc, stdout, stderr = _run_pytest(*args)

    # count tests
    tests = [line for line in stdout.strip().split("\n") if line.strip() and "::" in line]

    return {
        "success": rc == 0,
        "result": stdout if stdout.strip() else "(no tests found)",
        "data": {"count": len(tests), "tests": tests[:100]},
    }


def _op_targeted(ctx):
    """run tests for specific changed files. files= list of changed paths."""
    files = ctx.get("files", [])
    if not files:
        return {"success": False, "result": "No files specified.", "data": {}}

    # map source files to test files
    test_targets = set()
    for f in files:
        p = Path(f)
        # if it's already a test file, run it directly
        if p.name.startswith("test_"):
            test_targets.add(str(p))
            continue

        # try to find corresponding test file
        # src/keanu/foo/bar.py -> tests/test_bar.py
        stem = p.stem
        candidates = [
            f"tests/test_{stem}.py",
            f"tests/{p.parent.name}/test_{stem}.py",
        ]
        for c in candidates:
            if Path(c).exists():
                test_targets.add(c)

    if not test_targets:
        # no specific tests found, run all as fallback
        return _op_run(ctx)

    ctx_copy = dict(ctx)
    ctx_copy["target"] = " ".join(sorted(test_targets))
    return _op_run(ctx_copy)


def _op_coverage(ctx):
    """run tests with coverage."""
    args = ["--cov=src", "--cov-report=term-missing", "-v", "--tb=short", "--no-header"]
    target = ctx.get("target", "")
    if target:
        args.append(target)

    rc, stdout, stderr = _run_pytest(*args)
    summary = _parse_summary(stdout)
    failures = _parse_failures(stdout, stderr) if rc != 0 else []

    output = stdout
    if len(output) > 8000:
        output = output[:8000] + "\n... (truncated)"

    return {
        "success": rc == 0,
        "result": output if output.strip() else summary or "(no output)",
        "data": {
            "returncode": rc,
            "summary": summary,
            "failures": failures,
            "failure_count": len(failures),
        },
    }


def _op_unknown(ctx):
    ops = ", ".join(sorted(_OPS.keys()))
    return {"success": False, "result": f"Unknown test op. Available: {ops}", "data": {}}


_OPS = {
    "run": _op_run,
    "discover": _op_discover,
    "targeted": _op_targeted,
    "coverage": _op_coverage,
}
