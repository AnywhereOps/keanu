"""ops.py - proactive operations monitoring.

monitors project health without being asked. dependency updates,
security patches, test rot, doc drift, stale TODOs.

in the world: the IT guy pattern. notices problems before they
become tickets. surfaces issues, doesn't nag.
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_OPS_LOG = keanu_home() / "ops_log.jsonl"
_OPS_CACHE = keanu_home() / "ops_cache.json"


@dataclass
class OpsIssue:
    """a proactive issue detected by ops monitoring."""
    category: str       # deps, security, tests, docs, code
    severity: str       # critical, warning, info
    message: str
    file: str = ""
    detail: str = ""
    auto_fixable: bool = False

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "detail": self.detail,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class OpsReport:
    """full ops monitoring report."""
    issues: list[OpsIssue] = field(default_factory=list)
    checks_run: int = 0
    duration_s: float = 0.0
    timestamp: float = 0.0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def fixable_count(self) -> int:
        return sum(1 for i in self.issues if i.auto_fixable)

    def summary(self) -> str:
        total = len(self.issues)
        if total == 0:
            return "all clear. no issues found."
        parts = []
        if self.critical_count:
            parts.append(f"{self.critical_count} critical")
        if self.warning_count:
            parts.append(f"{self.warning_count} warnings")
        info = total - self.critical_count - self.warning_count
        if info:
            parts.append(f"{info} info")
        return f"{total} issues: {', '.join(parts)}"

    def to_dict(self) -> dict:
        return {
            "issues": [i.to_dict() for i in self.issues],
            "checks_run": self.checks_run,
            "duration_s": round(self.duration_s, 2),
            "summary": self.summary(),
            "timestamp": self.timestamp,
        }


# ============================================================
# INDIVIDUAL CHECKS
# ============================================================

def check_stale_deps(root: str = ".") -> list[OpsIssue]:
    """check for outdated dependencies."""
    issues = []
    root_path = Path(root)

    # check Python deps
    requirements = root_path / "requirements.txt"
    if requirements.exists():
        try:
            r = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                outdated = json.loads(r.stdout)
                for pkg in outdated[:10]:
                    issues.append(OpsIssue(
                        category="deps",
                        severity="info",
                        message=f"{pkg['name']} {pkg['version']} -> {pkg['latest_version']}",
                        auto_fixable=True,
                    ))
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
            pass

    # check for lock file freshness
    lock_files = ["poetry.lock", "Pipfile.lock", "package-lock.json", "yarn.lock"]
    for lock in lock_files:
        lock_path = root_path / lock
        if lock_path.exists():
            age_days = (time.time() - lock_path.stat().st_mtime) / 86400
            if age_days > 90:
                issues.append(OpsIssue(
                    category="deps",
                    severity="warning",
                    message=f"{lock} is {int(age_days)} days old",
                    file=lock,
                ))

    return issues


def check_test_health(root: str = ".") -> list[OpsIssue]:
    """check test suite health."""
    issues = []
    root_path = Path(root)

    # check test directory exists
    test_dirs = [root_path / d for d in ["tests", "test", "spec"]]
    has_tests = any(d.is_dir() for d in test_dirs)

    if not has_tests:
        issues.append(OpsIssue(
            category="tests",
            severity="warning",
            message="no test directory found",
        ))
        return issues

    # check for test files
    test_count = 0
    for td in test_dirs:
        if td.is_dir():
            test_count += sum(1 for f in td.rglob("test_*.py"))
            test_count += sum(1 for f in td.rglob("*_test.py"))
            test_count += sum(1 for f in td.rglob("*.test.js"))
            test_count += sum(1 for f in td.rglob("*.test.ts"))

    # check source-to-test ratio
    src_count = 0
    src_dir = root_path / "src"
    if src_dir.is_dir():
        src_count = sum(1 for f in src_dir.rglob("*.py") if not f.name.startswith("_"))

    if src_count > 0 and test_count > 0:
        ratio = test_count / src_count
        if ratio < 0.5:
            issues.append(OpsIssue(
                category="tests",
                severity="info",
                message=f"low test coverage: {test_count} tests for {src_count} source files (ratio: {ratio:.1f})",
            ))

    return issues


def check_doc_drift(root: str = ".") -> list[OpsIssue]:
    """check for documentation that might be outdated."""
    issues = []
    root_path = Path(root)

    # check if README exists
    readmes = ["README.md", "README.rst", "README.txt"]
    readme = None
    for name in readmes:
        p = root_path / name
        if p.exists():
            readme = p
            break

    if readme is None:
        issues.append(OpsIssue(
            category="docs",
            severity="warning",
            message="no README found",
            auto_fixable=True,
        ))
    else:
        # check README age vs latest source change
        readme_mtime = readme.stat().st_mtime
        src_dir = root_path / "src"
        if src_dir.is_dir():
            latest_src = max(
                (f.stat().st_mtime for f in src_dir.rglob("*.py") if f.is_file()),
                default=0,
            )
            if latest_src > 0 and (latest_src - readme_mtime) > 7 * 86400:
                days = int((latest_src - readme_mtime) / 86400)
                issues.append(OpsIssue(
                    category="docs",
                    severity="info",
                    message=f"README is {days} days older than latest source change",
                    file=str(readme),
                ))

    # check for stale TODOs in code
    todo_count = 0
    src_dir = root_path / "src"
    if src_dir.is_dir():
        for f in src_dir.rglob("*.py"):
            try:
                content = f.read_text(errors="replace")
                todo_count += len(re.findall(r"#\s*TODO", content))
            except OSError:
                pass

    if todo_count > 20:
        issues.append(OpsIssue(
            category="docs",
            severity="info",
            message=f"{todo_count} TODO comments in source",
        ))

    return issues


def check_code_quality(root: str = ".") -> list[OpsIssue]:
    """check code quality indicators."""
    issues = []
    root_path = Path(root)

    src_dir = root_path / "src"
    if not src_dir.is_dir():
        return issues

    large_files = []
    for f in src_dir.rglob("*.py"):
        try:
            line_count = len(f.read_text(errors="replace").split("\n"))
            if line_count > 500:
                large_files.append((f, line_count))
        except OSError:
            pass

    for f, lines in sorted(large_files, key=lambda x: -x[1])[:5]:
        issues.append(OpsIssue(
            category="code",
            severity="info",
            message=f"{f.name} has {lines} lines (consider splitting)",
            file=str(f.relative_to(root_path)),
        ))

    return issues


def check_git_hygiene(root: str = ".") -> list[OpsIssue]:
    """check git repository hygiene."""
    issues = []
    root_path = Path(root)

    if not (root_path / ".git").is_dir():
        return issues

    # check for uncommitted changes
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
            cwd=root,
        )
        if r.returncode == 0 and r.stdout.strip():
            changed = len(r.stdout.strip().split("\n"))
            issues.append(OpsIssue(
                category="code",
                severity="info",
                message=f"{changed} uncommitted changes",
            ))
    except (subprocess.TimeoutExpired, OSError):
        pass

    # check for .gitignore
    if not (root_path / ".gitignore").exists():
        issues.append(OpsIssue(
            category="code",
            severity="warning",
            message="no .gitignore found",
            auto_fixable=True,
        ))

    return issues


# ============================================================
# FULL SCAN
# ============================================================

def scan(root: str = ".", checks: list[str] = None) -> OpsReport:
    """run all ops checks and return a report.

    checks: optional list of check names to run. default is all.
    valid names: deps, tests, docs, code, git
    """
    start = time.time()
    report = OpsReport(timestamp=time.time())

    all_checks = {
        "deps": check_stale_deps,
        "tests": check_test_health,
        "docs": check_doc_drift,
        "code": check_code_quality,
        "git": check_git_hygiene,
    }

    to_run = checks or list(all_checks.keys())

    for name in to_run:
        if name in all_checks:
            try:
                issues = all_checks[name](root)
                report.issues.extend(issues)
                report.checks_run += 1
            except Exception:
                pass

    report.duration_s = time.time() - start

    # log the report
    _log_report(report)

    return report


# ============================================================
# OPS LOG
# ============================================================

def _log_report(report: OpsReport):
    """persist ops report."""
    _OPS_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        entry = {
            "timestamp": report.timestamp,
            "checks_run": report.checks_run,
            "issue_count": len(report.issues),
            "critical": report.critical_count,
            "warnings": report.warning_count,
        }
        with open(_OPS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def get_ops_history(limit: int = 50) -> list[dict]:
    """get recent ops scan history."""
    if not _OPS_LOG.exists():
        return []
    entries = []
    try:
        for line in _OPS_LOG.read_text().strip().split("\n"):
            if line.strip():
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return entries[-limit:]


def should_scan(interval_hours: int = 24) -> bool:
    """check if enough time has passed since last scan."""
    history = get_ops_history(limit=1)
    if not history:
        return True
    last = history[-1].get("timestamp", 0)
    return (time.time() - last) > (interval_hours * 3600)
