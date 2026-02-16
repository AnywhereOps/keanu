"""suggestions.py - proactive code suggestions.

while reading code, notice: unused imports, dead code, missing tests,
code smells. surface them gently. respect pulse state.

in the world: the quiet voice. not a critic, an observer.
it notices things. you decide what to do about them.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Suggestion:
    """a proactive code suggestion."""
    file: str
    line: int
    category: str      # "unused_import", "dead_code", "missing_test", "complexity", "style"
    message: str
    severity: str = "info"  # "info", "warning", "hint"
    fix: str = ""           # suggested fix if applicable

    def __str__(self):
        return f"{self.file}:{self.line} [{self.category}] {self.message}"


@dataclass
class SuggestionReport:
    """all suggestions for a scan."""
    suggestions: list[Suggestion] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def count(self) -> int:
        return len(self.suggestions)

    def by_category(self) -> dict[str, list[Suggestion]]:
        cats: dict[str, list[Suggestion]] = {}
        for s in self.suggestions:
            cats.setdefault(s.category, []).append(s)
        return cats

    def summary(self) -> str:
        cats = self.by_category()
        parts = [f"{len(v)} {k}" for k, v in sorted(cats.items())]
        return f"{self.count} suggestions in {self.files_scanned} files: {', '.join(parts)}"


# ============================================================
# SCANNERS
# ============================================================

def scan_file(filepath: str) -> list[Suggestion]:
    """scan a single file for suggestions."""
    path = Path(filepath)
    if not path.exists() or not path.suffix == ".py":
        return []

    try:
        source = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []

    suggestions = []
    rel = str(path)

    suggestions.extend(_check_unused_imports(source, rel))
    suggestions.extend(_check_dead_code(source, rel))
    suggestions.extend(_check_complexity(source, rel))
    suggestions.extend(_check_style(source, rel))

    return suggestions


def scan_directory(root: str = ".", max_files: int = 100) -> SuggestionReport:
    """scan a directory for suggestions across all Python files."""
    root_path = Path(root).resolve()
    report = SuggestionReport()

    skip_dirs = {"__pycache__", ".git", "node_modules", ".tox",
                 ".venv", "venv", ".eggs", "dist", "build"}

    count = 0
    for py_file in sorted(root_path.rglob("*.py")):
        if any(part in skip_dirs for part in py_file.parts):
            continue
        if count >= max_files:
            break

        try:
            rel = str(py_file.relative_to(root_path))
        except ValueError:
            rel = str(py_file)

        report.suggestions.extend(scan_file(str(py_file)))
        count += 1

    report.files_scanned = count
    return report


def check_missing_tests(root: str = ".") -> list[Suggestion]:
    """check which source files don't have corresponding test files."""
    root_path = Path(root).resolve()
    suggestions = []

    src_files = set()
    test_files = set()

    for py_file in root_path.rglob("*.py"):
        if "__pycache__" in str(py_file) or ".git" in str(py_file):
            continue
        rel = str(py_file.relative_to(root_path))
        if rel.startswith("tests/") or "/tests/" in rel:
            test_files.add(py_file.stem)
        elif not rel.startswith(".") and py_file.stem != "__init__":
            src_files.add((rel, py_file.stem))

    for rel, stem in sorted(src_files):
        test_name = f"test_{stem}"
        if test_name not in test_files:
            suggestions.append(Suggestion(
                file=rel, line=0,
                category="missing_test",
                message=f"no test file found (expected tests/{test_name}.py)",
                severity="hint",
            ))

    return suggestions


# ============================================================
# INDIVIDUAL CHECKERS
# ============================================================

def _check_unused_imports(source: str, filepath: str) -> list[Suggestion]:
    """detect imports that are never used in the file."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    suggestions = []
    imports = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                imports.append((name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                imports.append((name, node.lineno))

    # check if each imported name is used in the rest of the source
    for name, line in imports:
        if name == "*":
            continue
        # count occurrences (excluding the import line itself)
        lines = source.split("\n")
        used = False
        for i, src_line in enumerate(lines, 1):
            if i == line:
                continue
            if re.search(rf'\b{re.escape(name)}\b', src_line):
                used = True
                break

        if not used:
            suggestions.append(Suggestion(
                file=filepath, line=line,
                category="unused_import",
                message=f"'{name}' imported but never used",
                severity="warning",
                fix=f"remove import of '{name}'",
            ))

    return suggestions


def _check_dead_code(source: str, filepath: str) -> list[Suggestion]:
    """detect potential dead code patterns."""
    suggestions = []
    lines = source.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # unreachable code after return
        if i > 1 and stripped and not stripped.startswith("#"):
            prev = lines[i - 2].strip()
            if prev.startswith("return ") or prev == "return":
                indent_curr = len(line) - len(line.lstrip())
                indent_prev = len(lines[i - 2]) - len(lines[i - 2].lstrip())
                if indent_curr == indent_prev:
                    suggestions.append(Suggestion(
                        file=filepath, line=i,
                        category="dead_code",
                        message="code after return statement (unreachable)",
                        severity="warning",
                    ))

        # commented-out code
        if stripped.startswith("# ") and any(
            stripped[2:].strip().startswith(kw)
            for kw in ["def ", "class ", "if ", "for ", "while ", "return ", "import "]
        ):
            suggestions.append(Suggestion(
                file=filepath, line=i,
                category="dead_code",
                message="commented-out code",
                severity="hint",
            ))

    return suggestions


def _check_complexity(source: str, filepath: str) -> list[Suggestion]:
    """detect overly complex functions."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    suggestions = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # count lines
            if hasattr(node, 'end_lineno') and node.end_lineno:
                length = node.end_lineno - node.lineno
                if length > 50:
                    suggestions.append(Suggestion(
                        file=filepath, line=node.lineno,
                        category="complexity",
                        message=f"function '{node.name}' is {length} lines (consider splitting)",
                        severity="hint",
                    ))

            # count branches (if/for/while/try)
            branches = sum(1 for _ in ast.walk(node)
                          if isinstance(_, (ast.If, ast.For, ast.While, ast.Try,
                                           ast.ExceptHandler)))
            if branches > 8:
                suggestions.append(Suggestion(
                    file=filepath, line=node.lineno,
                    category="complexity",
                    message=f"function '{node.name}' has {branches} branches (high complexity)",
                    severity="warning",
                ))

    return suggestions


def _check_style(source: str, filepath: str) -> list[Suggestion]:
    """detect common style issues."""
    suggestions = []
    lines = source.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # bare except
        if stripped == "except:" or stripped.startswith("except: "):
            suggestions.append(Suggestion(
                file=filepath, line=i,
                category="style",
                message="bare except (catches all exceptions including KeyboardInterrupt)",
                severity="warning",
                fix="use 'except Exception:' instead",
            ))

        # mutable default argument
        if re.match(r'def \w+\(.*=\s*(\[\]|\{\}|\bset\(\))', stripped):
            suggestions.append(Suggestion(
                file=filepath, line=i,
                category="style",
                message="mutable default argument (shared between calls)",
                severity="warning",
                fix="use None as default and create the mutable in the function body",
            ))

        # print statement in non-test, non-cli
        if (stripped.startswith("print(") and
                "test" not in filepath.lower() and
                "cli" not in filepath.lower() and
                "repl" not in filepath.lower()):
            suggestions.append(Suggestion(
                file=filepath, line=i,
                category="style",
                message="print() in production code (use logging instead)",
                severity="hint",
            ))

    return suggestions
