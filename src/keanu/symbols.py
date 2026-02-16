"""symbols.py - AST-based symbol finding.

find where things are defined, where they're used, who calls what.
uses Python's stdlib ast module for Python files, regex fallback for others.

in the world: the index at the back of the book.
you don't read the whole book to find one reference.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Symbol:
    """a symbol found in the codebase."""
    name: str
    kind: str       # "function", "class", "method", "variable", "import"
    file: str
    line: int
    col: int = 0
    parent: str = ""  # class name for methods


@dataclass
class Reference:
    """a usage of a symbol."""
    file: str
    line: int
    col: int = 0
    context: str = ""  # the line of code


def find_definition(name: str, root: str = ".") -> list[Symbol]:
    """find where a symbol is defined.

    tries AST for Python files first, regex fallback for everything else.
    returns all definitions found, sorted by relevance (exact match first).
    """
    root_path = Path(root).resolve()
    results = []

    # Python files: AST
    for py_file in root_path.rglob("*.py"):
        if _should_skip(py_file):
            continue
        try:
            results.extend(_find_defs_ast(name, py_file, root_path))
        except Exception:
            results.extend(_find_defs_regex(name, py_file, root_path))

    # sort: exact name match first, then partial
    results.sort(key=lambda s: (0 if s.name == name else 1, s.file))
    return results


def find_references(name: str, root: str = ".") -> list[Reference]:
    """find all usages of a symbol.

    searches all Python files for the name. returns file, line, context.
    """
    root_path = Path(root).resolve()
    results = []

    for py_file in root_path.rglob("*.py"):
        if _should_skip(py_file):
            continue
        try:
            text = py_file.read_text()
            rel = str(py_file.relative_to(root_path))
            for i, line in enumerate(text.split("\n"), 1):
                if name in line:
                    results.append(Reference(
                        file=rel, line=i,
                        context=line.strip()[:120],
                    ))
        except Exception:
            continue

    return results[:100]  # cap results


def find_callers(name: str, root: str = ".") -> list[Reference]:
    """find all places that call a function.

    looks for `name(` pattern. more precise than find_references
    since it excludes imports and definitions.
    """
    root_path = Path(root).resolve()
    results = []
    call_pattern = re.compile(rf'(?<![.\w]){re.escape(name)}\s*\(')

    for py_file in root_path.rglob("*.py"):
        if _should_skip(py_file):
            continue
        try:
            text = py_file.read_text()
            rel = str(py_file.relative_to(root_path))
            for i, line in enumerate(text.split("\n"), 1):
                stripped = line.strip()
                # skip definitions and imports
                if stripped.startswith(("def ", "class ", "import ", "from ")):
                    continue
                if call_pattern.search(line):
                    results.append(Reference(
                        file=rel, line=i,
                        context=stripped[:120],
                    ))
        except Exception:
            continue

    return results[:100]


def list_symbols(filepath: str) -> list[Symbol]:
    """list all symbols defined in a file."""
    path = Path(filepath)
    if not path.exists():
        return []

    root = path.parent
    try:
        return _find_all_symbols_ast(path, root)
    except Exception:
        return []


# ============================================================
# AST-BASED FINDING
# ============================================================

def _find_defs_ast(name: str, filepath: Path, root: Path) -> list[Symbol]:
    """find definitions of a name in a Python file using AST."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []

    rel = str(filepath.relative_to(root))
    results = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            # check if it's a method (inside a class)
            parent = _find_parent_class(tree, node)
            results.append(Symbol(
                name=name,
                kind="method" if parent else "function",
                file=rel, line=node.lineno, col=node.col_offset,
                parent=parent or "",
            ))
        elif isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            parent = _find_parent_class(tree, node)
            results.append(Symbol(
                name=name,
                kind="method" if parent else "function",
                file=rel, line=node.lineno, col=node.col_offset,
                parent=parent or "",
            ))
        elif isinstance(node, ast.ClassDef) and node.name == name:
            results.append(Symbol(
                name=name, kind="class",
                file=rel, line=node.lineno, col=node.col_offset,
            ))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    results.append(Symbol(
                        name=name, kind="variable",
                        file=rel, line=node.lineno, col=node.col_offset,
                    ))

    return results


def _find_all_symbols_ast(filepath: Path, root: Path) -> list[Symbol]:
    """find all symbol definitions in a file."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []

    rel = str(filepath.relative_to(root))
    results = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = _find_parent_class(tree, node)
            results.append(Symbol(
                name=node.name,
                kind="method" if parent else "function",
                file=rel, line=node.lineno, col=node.col_offset,
                parent=parent or "",
            ))
        elif isinstance(node, ast.ClassDef):
            results.append(Symbol(
                name=node.name, kind="class",
                file=rel, line=node.lineno, col=node.col_offset,
            ))

    results.sort(key=lambda s: s.line)
    return results


def _find_parent_class(tree, target_node) -> Optional[str]:
    """find the class that contains a function node."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.walk(node):
                if child is target_node:
                    return node.name
    return None


# ============================================================
# REGEX FALLBACK
# ============================================================

def _find_defs_regex(name: str, filepath: Path, root: Path) -> list[Symbol]:
    """regex fallback for finding definitions."""
    try:
        text = filepath.read_text()
    except (OSError, UnicodeDecodeError):
        return []

    rel = str(filepath.relative_to(root))
    results = []

    patterns = [
        (rf'^def\s+{re.escape(name)}\s*\(', "function"),
        (rf'^class\s+{re.escape(name)}[\s:(]', "class"),
        (rf'^\s+def\s+{re.escape(name)}\s*\(', "method"),
        (rf'^{re.escape(name)}\s*=', "variable"),
    ]

    for i, line in enumerate(text.split("\n"), 1):
        for pattern, kind in patterns:
            if re.match(pattern, line):
                results.append(Symbol(
                    name=name, kind=kind,
                    file=rel, line=i,
                ))

    return results


# ============================================================
# HELPERS
# ============================================================

def _should_skip(path: Path) -> bool:
    """skip files that shouldn't be searched."""
    parts = path.parts
    skip_dirs = {
        "__pycache__", ".git", "node_modules", ".tox",
        ".venv", "venv", ".eggs", "dist", "build",
    }
    return any(part in skip_dirs for part in parts)
