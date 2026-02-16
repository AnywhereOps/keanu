"""ci.py - continuous integration monitoring.

run full test suite, detect flaky tests, bisect failures,
track test health over time. no LLM needed.

in the world: the watcher. keeps the green lights green.
"""

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_CI_LOG = keanu_home() / "ci_log.jsonl"


@dataclass
class TestRun:
    """result of a test suite run."""
    timestamp: float
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_s: float = 0.0
    failures: list[dict] = field(default_factory=list)
    commit: str = ""

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors

    @property
    def success_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def green(self) -> bool:
        return self.failed == 0 and self.errors == 0


@dataclass
class FlakyTest:
    """a test that sometimes passes and sometimes fails."""
    name: str
    pass_count: int = 0
    fail_count: int = 0
    last_failure: str = ""

    @property
    def flakiness(self) -> float:
        total = self.pass_count + self.fail_count
        if total == 0:
            return 0.0
        minority = min(self.pass_count, self.fail_count)
        return minority / total


# ============================================================
# TEST RUNNING
# ============================================================

def run_tests(target: str = "", timeout: int = 300) -> TestRun:
    """run the test suite and parse results."""
    cmd = ["python3", "-m", "pytest", "--tb=line", "-q"]
    if target:
        cmd.append(target)

    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return TestRun(
            timestamp=time.time(), duration_s=timeout,
            errors=1, failures=[{"test": "TIMEOUT", "error": f"exceeded {timeout}s"}],
        )

    duration = time.time() - start
    run = _parse_pytest_output(result.stdout + result.stderr)
    run.timestamp = time.time()
    run.duration_s = duration
    run.commit = _current_commit()

    return run


def run_tests_n(n: int = 3, target: str = "") -> list[TestRun]:
    """run the test suite n times to detect flakiness."""
    runs = []
    for _ in range(n):
        runs.append(run_tests(target))
    return runs


# ============================================================
# FLAKY TEST DETECTION
# ============================================================

def detect_flaky(runs: list[TestRun], threshold: float = 0.1) -> list[FlakyTest]:
    """detect flaky tests from multiple runs."""
    test_results: dict[str, FlakyTest] = {}

    for run in runs:
        # track failures
        failed_names = {f.get("test", "") for f in run.failures}
        for name in failed_names:
            if name not in test_results:
                test_results[name] = FlakyTest(name=name)
            test_results[name].fail_count += 1
            test_results[name].last_failure = run.failures[0].get("error", "") if run.failures else ""

    # for each test that failed at least once, check if it passed in other runs
    for name, ft in test_results.items():
        ft.pass_count = len(runs) - ft.fail_count

    return [ft for ft in test_results.values() if ft.flakiness >= threshold]


# ============================================================
# BISECT
# ============================================================

def bisect_failure(test_name: str, good_commit: str, bad_commit: str = "HEAD",
                   max_steps: int = 20) -> dict:
    """find the commit that introduced a test failure using git bisect."""
    try:
        # get commits between good and bad
        result = subprocess.run(
            ["git", "log", "--oneline", f"{good_commit}..{bad_commit}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"error": "git log failed"}

        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                commits.append(line.split()[0])

        if not commits:
            return {"error": "no commits between good and bad"}

        # binary search
        left, right = 0, len(commits) - 1
        steps = 0

        while left < right and steps < max_steps:
            mid = (left + right) // 2
            commit = commits[mid]

            # checkout and test
            subprocess.run(["git", "stash"], capture_output=True, timeout=10)
            subprocess.run(["git", "checkout", commit], capture_output=True, timeout=10)

            run = run_tests(test_name, timeout=60)
            steps += 1

            if run.green:
                right = mid
            else:
                left = mid + 1

        # restore
        subprocess.run(["git", "checkout", "-"], capture_output=True, timeout=10)
        subprocess.run(["git", "stash", "pop"], capture_output=True, timeout=10)

        if left < len(commits):
            guilty = commits[left]
            # get commit message
            msg_result = subprocess.run(
                ["git", "log", "--oneline", "-1", guilty],
                capture_output=True, text=True, timeout=10,
            )
            return {
                "commit": guilty,
                "message": msg_result.stdout.strip(),
                "steps": steps,
            }

        return {"error": "could not isolate the commit", "steps": steps}

    except Exception as e:
        # make sure we're back on original branch
        subprocess.run(["git", "checkout", "-"], capture_output=True, timeout=10)
        subprocess.run(["git", "stash", "pop"], capture_output=True, timeout=10)
        return {"error": str(e)}


# ============================================================
# TEST HEALTH TRACKING
# ============================================================

def log_run(run: TestRun):
    """log a test run to the CI log."""
    _CI_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": run.timestamp,
        "passed": run.passed,
        "failed": run.failed,
        "errors": run.errors,
        "skipped": run.skipped,
        "duration_s": round(run.duration_s, 2),
        "commit": run.commit,
        "failure_names": [f.get("test", "") for f in run.failures],
    }
    try:
        with open(_CI_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def get_history(limit: int = 50) -> list[dict]:
    """get recent CI history."""
    if not _CI_LOG.exists():
        return []
    entries = []
    try:
        for line in _CI_LOG.read_text().strip().split("\n"):
            if line.strip():
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return entries[-limit:]


def health_summary(history: list[dict] | None = None) -> dict:
    """summarize test health from history."""
    if history is None:
        history = get_history()

    if not history:
        return {"status": "no data", "runs": 0}

    total_runs = len(history)
    green_runs = sum(1 for h in history if h.get("failed", 0) == 0 and h.get("errors", 0) == 0)
    avg_duration = sum(h.get("duration_s", 0) for h in history) / total_runs
    avg_passed = sum(h.get("passed", 0) for h in history) / total_runs

    # find most common failures
    failure_counts: dict[str, int] = {}
    for h in history:
        for name in h.get("failure_names", []):
            failure_counts[name] = failure_counts.get(name, 0) + 1

    top_failures = sorted(failure_counts.items(), key=lambda x: -x[1])[:5]

    # trend
    recent = history[-5:]
    recent_green = sum(1 for h in recent if h.get("failed", 0) == 0)
    trend = "improving" if recent_green >= 4 else "declining" if recent_green <= 1 else "stable"

    return {
        "status": "green" if green_runs == total_runs else "red" if green_runs == 0 else "yellow",
        "runs": total_runs,
        "green_runs": green_runs,
        "success_rate": green_runs / total_runs,
        "avg_duration_s": round(avg_duration, 1),
        "avg_tests": round(avg_passed),
        "trend": trend,
        "top_failures": [{"test": name, "count": count} for name, count in top_failures],
    }


# ============================================================
# HELPERS
# ============================================================

def _parse_pytest_output(output: str) -> TestRun:
    """parse pytest output into a TestRun."""
    import re
    run = TestRun(timestamp=time.time())

    # look for the summary line: "X passed, Y failed, Z errors in Ns"
    summary_match = re.search(
        r'(\d+)\s+passed(?:,\s*(\d+)\s+failed)?(?:,\s*(\d+)\s+error)?(?:,\s*(\d+)\s+skipped)?',
        output,
    )
    if summary_match:
        run.passed = int(summary_match.group(1))
        run.failed = int(summary_match.group(2) or 0)
        run.errors = int(summary_match.group(3) or 0)
        run.skipped = int(summary_match.group(4) or 0)

    # also check for "X failed" at start (when 0 passed)
    if run.passed == 0:
        fail_match = re.search(r'(\d+)\s+failed', output)
        if fail_match:
            run.failed = int(fail_match.group(1))

    # extract failure details
    for match in re.finditer(r'FAILED\s+(\S+)', output):
        test_id = match.group(1)
        run.failures.append({"test": test_id, "error": ""})

    # extract error lines (after FAILED lines)
    for match in re.finditer(r'(\S+::\S+)\s+-\s+(.+)', output):
        test_id = match.group(1)
        error_msg = match.group(2)
        # update existing failure or add new
        updated = False
        for f in run.failures:
            if f["test"] == test_id:
                f["error"] = error_msg
                updated = True
                break
        if not updated:
            run.failures.append({"test": test_id, "error": error_msg})

    return run


def _current_commit() -> str:
    """get the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""
