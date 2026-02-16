"""bisect.py - automated git bisect helpers.

finds which commit introduced a bug or broke a test. builds scripts,
parses logs, runs binary search over commit lists. pure python, no
new dependencies.

in the world: when something breaks, you need to know when it broke.
bisect is the divination spell. point it at a good commit and a bad
one, it finds the culprit.
"""

import math
import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class BisectStep:
    """one step in a bisect run."""
    commit: str
    message: str
    result: str  # "good", "bad", "skip"
    output: str


@dataclass
class BisectResult:
    """outcome of a completed bisect."""
    bad_commit: str
    good_commit: str
    culprit_commit: str
    culprit_message: str
    steps: int
    commits_tested: list[str] = field(default_factory=list)


def parse_git_log(log_output: str) -> list[dict]:
    """parse git log output into structured dicts."""
    entries = []
    for line in log_output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # format: "hash message" (oneline) or "hash|author|date|message" (custom)
        if "|" in line:
            parts = line.split("|", 3)
            if len(parts) >= 4:
                entries.append({
                    "hash": parts[0].strip(),
                    "author": parts[1].strip(),
                    "date": parts[2].strip(),
                    "message": parts[3].strip(),
                })
            elif len(parts) == 3:
                entries.append({
                    "hash": parts[0].strip(),
                    "author": parts[1].strip(),
                    "date": "",
                    "message": parts[2].strip(),
                })
        else:
            # oneline: first token is hash, rest is message
            parts = line.split(None, 1)
            if len(parts) == 2:
                entries.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "author": "",
                    "date": "",
                })
            elif len(parts) == 1:
                entries.append({
                    "hash": parts[0],
                    "message": "",
                    "author": "",
                    "date": "",
                })
    return entries


def find_commits_between(good: str, bad: str, root: str = ".") -> list[str]:
    """return commit hashes between good and bad, oldest first."""
    cmd = ["git", "rev-list", "--reverse", f"{good}..{bad}"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=root
    )
    if result.returncode != 0:
        return []
    return [h.strip() for h in result.stdout.strip().splitlines() if h.strip()]


def _run_test_at_commit(
    commit: str, test_cmd: str, root: str
) -> tuple[bool, str]:
    """build commands to checkout commit and run test. returns (passed, output).

    does not execute git commands directly. builds the command strings
    and returns them so the caller can run or dry-run.
    """
    checkout_cmd = f"git checkout {commit}"
    full_cmd = f"cd {root} && {checkout_cmd} && {test_cmd}"
    # return the command string as output, caller decides execution
    return (True, full_cmd)


def build_bisect_script(test_cmd: str, good: str, bad: str) -> str:
    """generate a shell script that runs git bisect with a test command."""
    lines = [
        "#!/bin/bash",
        "set -e",
        "",
        "# automated git bisect",
        f"git bisect start {bad} {good}",
        f"git bisect run {test_cmd}",
        "",
        "# show result",
        "git bisect log",
        "git bisect reset",
    ]
    return "\n".join(lines) + "\n"


def analyze_bisect_log(log: str) -> BisectResult:
    """parse git bisect log output into structured result."""
    good_commit = ""
    bad_commit = ""
    culprit_commit = ""
    culprit_message = ""
    commits_tested = []
    steps = 0

    for line in log.strip().splitlines():
        line = line.strip()

        # "# good: [hash] message"
        m = re.match(r"#\s+good:\s+\[([a-f0-9]+)\]\s*(.*)", line)
        if m:
            if not good_commit:
                good_commit = m.group(1)
            commits_tested.append(m.group(1))
            steps += 1
            continue

        # "# bad: [hash] message"
        m = re.match(r"#\s+bad:\s+\[([a-f0-9]+)\]\s*(.*)", line)
        if m:
            if not bad_commit:
                bad_commit = m.group(1)
            commits_tested.append(m.group(1))
            steps += 1
            continue

        # "# first bad commit: [hash] message"
        m = re.match(
            r"#\s+first bad commit:\s+\[([a-f0-9]+)\]\s*(.*)", line
        )
        if m:
            culprit_commit = m.group(1)
            culprit_message = m.group(2)
            continue

        # "git bisect good hash" or "git bisect bad hash"
        m = re.match(r"git bisect (good|bad)\s+([a-f0-9]+)", line)
        if m:
            commits_tested.append(m.group(2))
            steps += 1

    return BisectResult(
        bad_commit=bad_commit,
        good_commit=good_commit,
        culprit_commit=culprit_commit,
        culprit_message=culprit_message,
        steps=steps,
        commits_tested=commits_tested,
    )


def format_bisect_report(result: BisectResult) -> str:
    """human-readable report of bisect findings."""
    lines = [
        "bisect report",
        "=============",
        f"good commit: {result.good_commit}",
        f"bad commit:  {result.bad_commit}",
        f"culprit:     {result.culprit_commit}",
        f"message:     {result.culprit_message}",
        f"steps taken: {result.steps}",
        f"commits tested: {len(result.commits_tested)}",
    ]
    if result.commits_tested:
        lines.append("")
        lines.append("tested:")
        for c in result.commits_tested:
            lines.append(f"  {c}")
    return "\n".join(lines)


def suggest_test_command(description: str) -> str:
    """suggest a test command based on failure description."""
    desc = description.lower()

    if "import error" in desc or "importerror" in desc:
        # extract module name: look for "in X" or "from X" or "import X"
        # but skip "import error" itself
        m = re.search(r"\b(?:in|from)\s+(\w+)", desc)
        if m:
            module = m.group(1)
        else:
            module = "module"
        return f"python -c 'import {module}'"

    if "syntax error" in desc or "syntaxerror" in desc:
        m = re.search(r"in\s+(\S+\.py)", desc)
        if m:
            return f"python -c 'import py_compile; py_compile.compile(\"{m.group(1)}\", doraise=True)'"
        return "python -m py_compile ."

    # "test X fails" or "test_X broken"
    m = re.search(r"test[_\s]+(\w+)", desc)
    if m:
        return f"pytest -xvs -k {m.group(1)}"

    if "build" in desc or "compile" in desc:
        return "python -m build"

    if "type" in desc and ("error" in desc or "check" in desc):
        return "mypy ."

    # default: run the full test suite
    return "pytest -x"


def binary_search_commits(
    commits: list[str], test_fn
) -> tuple[int, list[BisectStep]]:
    """pure binary search over commits. test_fn(commit) -> bool (True=good).

    assumes commits[0] is good and commits[-1] is bad. finds the first
    bad commit. returns (index of first bad, list of steps taken).
    """
    if not commits:
        return (-1, [])

    lo, hi = 0, len(commits) - 1
    steps: list[BisectStep] = []

    while lo < hi:
        mid = (lo + hi) // 2
        passed = test_fn(commits[mid])
        result = "good" if passed else "bad"
        steps.append(BisectStep(
            commit=commits[mid],
            message="",
            result=result,
            output=f"tested {commits[mid]}: {result}",
        ))
        if passed:
            lo = mid + 1
        else:
            hi = mid

    return (lo, steps)


def estimate_steps(total_commits: int) -> int:
    """calculate expected bisect steps (ceil of log2)."""
    if total_commits <= 1:
        return 0
    return math.ceil(math.log2(total_commits))
