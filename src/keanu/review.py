"""review.py - code review.

reads a diff, finds issues, suggests fixes. can review staged changes,
a PR, or a specific file. flags security issues, performance problems,
style inconsistencies.

in the world: the second pair of eyes. not to judge, to catch what you missed.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Issue:
    """a single review finding."""
    severity: str      # "critical", "warning", "info", "style"
    category: str      # "security", "performance", "logic", "style", "naming"
    file: str
    line: int
    message: str
    suggestion: str = ""


@dataclass
class ReviewResult:
    """the full review output."""
    issues: list = field(default_factory=list)
    summary: str = ""
    files_reviewed: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "critical" for i in self.issues)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


def review_diff(diff_text: str) -> ReviewResult:
    """review a git diff for common issues.

    parses the diff, runs each hunk through pattern checkers,
    returns structured findings.
    """
    result = ReviewResult()
    hunks = _parse_diff(diff_text)

    for hunk in hunks:
        result.files_reviewed.append(hunk["file"])
        for added_line, line_num in hunk["additions"]:
            issues = _check_line(added_line, hunk["file"], line_num)
            result.issues.extend(issues)

    result.summary = _summarize(result)
    return result


def review_file(filepath: str) -> ReviewResult:
    """review a single file for common issues."""
    result = ReviewResult()
    try:
        content = Path(filepath).read_text()
    except (OSError, UnicodeDecodeError):
        result.summary = f"could not read {filepath}"
        return result

    result.files_reviewed.append(filepath)
    for i, line in enumerate(content.split("\n"), 1):
        issues = _check_line(line, filepath, i)
        result.issues.extend(issues)

    result.summary = _summarize(result)
    return result


# ============================================================
# DIFF PARSER
# ============================================================

def _parse_diff(diff_text: str) -> list[dict]:
    """parse a unified diff into hunks with file + line info."""
    hunks = []
    current_file = ""
    current_line = 0
    current_additions = []

    for line in diff_text.split("\n"):
        if line.startswith("+++ b/"):
            if current_file and current_additions:
                hunks.append({"file": current_file, "additions": current_additions})
            current_file = line[6:]
            current_additions = []
        elif line.startswith("@@ "):
            # parse hunk header: @@ -old,count +new,count @@
            match = re.search(r'\+(\d+)', line)
            if match:
                current_line = int(match.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            current_additions.append((line[1:], current_line))
            current_line += 1
        elif not line.startswith("-"):
            current_line += 1

    if current_file and current_additions:
        hunks.append({"file": current_file, "additions": current_additions})

    return hunks


# ============================================================
# CHECKERS
# ============================================================

# security patterns
_SECURITY_PATTERNS = [
    (r'eval\s*\(', "eval() is a security risk. use ast.literal_eval() for data."),
    (r'exec\s*\(', "exec() is a security risk. avoid dynamic code execution."),
    (r'__import__\s*\(', "dynamic import is a security risk."),
    (r'os\.system\s*\(', "os.system is unsafe. use subprocess.run() with shell=False."),
    (r'shell\s*=\s*True', "shell=True in subprocess is a command injection risk."),
    (r'pickle\.loads?\s*\(', "pickle is unsafe for untrusted data. use json instead."),
    (r'yaml\.load\s*\([^)]*\)\s*$', "yaml.load without Loader is unsafe. use yaml.safe_load."),
    (r'password\s*=\s*["\']', "hardcoded password detected."),
    (r'(api_key|secret|token)\s*=\s*["\'][^"\']{8}', "possible hardcoded secret."),
    (r'chmod\s+777', "chmod 777 is overly permissive."),
    (r'SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*%s', "possible SQL injection. use parameterized queries."),
    (r'\.format\(.*request\.', "string formatting with user input is a security risk."),
    (r'f["\'].*\{.*request\.', "f-string with user input is a security risk."),
]

# performance patterns
_PERF_PATTERNS = [
    (r'for\s+\w+\s+in\s+range\(len\(', "use enumerate() instead of range(len())."),
    (r'\+= \s*["\']', "string concatenation in loop. use join() or list append."),
    (r'\.readlines\(\)', ".readlines() loads entire file into memory. iterate the file directly."),
    (r'time\.sleep\(', "blocking sleep. consider async/non-blocking alternatives."),
    (r'except\s*:', "bare except catches SystemExit and KeyboardInterrupt. use except Exception."),
    (r'except\s+Exception\s*:\s*$', "catching Exception without handling is usually a bug."),
]

# style patterns
_STYLE_PATTERNS = [
    (r'#\s*TODO', "TODO comment found. track in issue tracker."),
    (r'#\s*FIXME', "FIXME comment found. should be addressed."),
    (r'#\s*HACK', "HACK comment found. tech debt marker."),
    (r'print\s*\(', "print() statement. use logging for production code."),
    (r'import pdb', "debugger import left in code."),
    (r'breakpoint\(\)', "breakpoint left in code."),
    (r'\.strip\(\)\s*==\s*["\']["\']', "use 'not s.strip()' instead of comparing to empty string."),
]

# logic patterns
_LOGIC_PATTERNS = [
    (r'==\s*None', "use 'is None' instead of '== None'."),
    (r'!=\s*None', "use 'is not None' instead of '!= None'."),
    (r'==\s*True', "use 'if x:' instead of 'if x == True:'."),
    (r'==\s*False', "use 'if not x:' instead of 'if x == False:'."),
    (r'type\(\w+\)\s*==', "use isinstance() instead of type() comparison."),
    (r'except.*pass\s*$', "empty except block swallows errors silently."),
    (r'return\s+True\s*\n\s*return\s+False', "simplify: return the condition directly."),
]


def _check_line(line: str, filepath: str, line_num: int) -> list[Issue]:
    """run all checkers against a single line."""
    issues = []

    for pattern, msg in _SECURITY_PATTERNS:
        if re.search(pattern, line):
            issues.append(Issue(
                severity="critical", category="security",
                file=filepath, line=line_num, message=msg,
            ))

    for pattern, msg in _PERF_PATTERNS:
        if re.search(pattern, line):
            issues.append(Issue(
                severity="warning", category="performance",
                file=filepath, line=line_num, message=msg,
            ))

    for pattern, msg in _STYLE_PATTERNS:
        if re.search(pattern, line):
            issues.append(Issue(
                severity="info", category="style",
                file=filepath, line=line_num, message=msg,
            ))

    for pattern, msg in _LOGIC_PATTERNS:
        if re.search(pattern, line):
            issues.append(Issue(
                severity="warning", category="logic",
                file=filepath, line=line_num, message=msg,
            ))

    return issues


def _summarize(result: ReviewResult) -> str:
    """build a one-line summary."""
    total = len(result.issues)
    if total == 0:
        return f"clean. {len(result.files_reviewed)} files reviewed."

    parts = []
    if result.critical_count:
        parts.append(f"{result.critical_count} critical")
    if result.warning_count:
        parts.append(f"{result.warning_count} warnings")
    info_count = total - result.critical_count - result.warning_count
    if info_count:
        parts.append(f"{info_count} info")

    return f"{', '.join(parts)}. {len(result.files_reviewed)} files reviewed."
