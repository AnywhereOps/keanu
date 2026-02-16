"""docgen.py - documentation generation.

generate docstrings from code, architecture diagrams (mermaid),
changelog from git history, README updates when public API changes.

in the world: the scribe. code that documents itself.
"""

import ast
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DocResult:
    """result of a documentation generation operation."""
    success: bool
    content: str = ""
    filepath: str = ""
    errors: list[str] = field(default_factory=list)


# ============================================================
# DOCSTRING GENERATION
# ============================================================

def generate_docstrings(filepath: str, style: str = "google") -> DocResult:
    """generate docstrings for functions/classes that don't have them.

    reads the file, finds undocumented definitions, generates docstrings
    from parameter names and return types. no LLM needed.

    style: "google" (default), "numpy", or "terse" (keanu's style).
    """
    path = Path(filepath)
    if not path.exists():
        return DocResult(success=False, errors=[f"file not found: {filepath}"])

    try:
        source = path.read_text()
        tree = ast.parse(source)
    except SyntaxError as e:
        return DocResult(success=False, errors=[f"syntax error: {e}"])

    lines = source.split("\n")
    insertions = []  # (line_number, docstring_text)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _has_docstring(node):
                continue
            doc = _generate_func_docstring(node, style)
            indent = _get_indent(lines, node.lineno - 1) + "    "
            insertions.append((node.body[0].lineno - 1, indent, doc))

        elif isinstance(node, ast.ClassDef):
            if _has_docstring(node):
                continue
            doc = _generate_class_docstring(node, style)
            indent = _get_indent(lines, node.lineno - 1) + "    "
            insertions.append((node.body[0].lineno - 1, indent, doc))

    if not insertions:
        return DocResult(success=True, content=source, filepath=filepath)

    # apply insertions in reverse order (so line numbers stay valid)
    new_lines = list(lines)
    for line_num, indent, doc in sorted(insertions, key=lambda x: -x[0]):
        doc_lines = doc.split("\n")
        formatted = [f'{indent}{line}' if line.strip() else '' for line in doc_lines]
        for i, dl in enumerate(formatted):
            new_lines.insert(line_num + i, dl)

    content = "\n".join(new_lines)
    return DocResult(success=True, content=content, filepath=filepath)


# ============================================================
# ARCHITECTURE DIAGRAMS
# ============================================================

def generate_module_diagram(root: str = ".", title: str = "Module Architecture") -> DocResult:
    """generate a mermaid diagram of module dependencies.

    reads the import graph and generates a mermaid flowchart.
    """
    try:
        from keanu.analysis.deps import build_graph
        graph = build_graph(root)
    except ImportError:
        return DocResult(success=False, errors=["deps module not available"])

    if not graph:
        return DocResult(success=False, errors=["no modules found"])

    lines = [f"```mermaid", f"graph TD"]
    lines.append(f"    subgraph {title}")

    # collect nodes and edges
    nodes = set()
    edges = []
    for source_file, imports in graph.items():
        source = _simplify_name(source_file)
        nodes.add(source)
        for imp in imports:
            target = _simplify_name(imp)
            if target != source:
                nodes.add(target)
                edges.append((source, target))

    # deduplicate and limit
    seen_edges = set()
    for src, tgt in edges[:100]:
        edge = (src, tgt)
        if edge not in seen_edges:
            seen_edges.add(edge)
            lines.append(f"    {src} --> {tgt}")

    lines.append("    end")
    lines.append("```")

    return DocResult(success=True, content="\n".join(lines))


def generate_class_diagram(filepath: str) -> DocResult:
    """generate a mermaid class diagram from a Python file."""
    path = Path(filepath)
    if not path.exists():
        return DocResult(success=False, errors=[f"file not found: {filepath}"])

    try:
        source = path.read_text()
        tree = ast.parse(source)
    except SyntaxError as e:
        return DocResult(success=False, errors=[f"syntax error: {e}"])

    lines = ["```mermaid", "classDiagram"]

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name

            # bases
            for base in node.bases:
                if isinstance(base, ast.Name):
                    lines.append(f"    {base.id} <|-- {class_name}")
                elif isinstance(base, ast.Attribute):
                    lines.append(f"    {ast.dump(base)} <|-- {class_name}")

            # methods and attributes
            lines.append(f"    class {class_name} {{")
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    vis = "-" if item.name.startswith("_") else "+"
                    params = ", ".join(
                        a.arg for a in item.args.args if a.arg != "self"
                    )
                    lines.append(f"        {vis}{item.name}({params})")
                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            lines.append(f"        +{target.id}")
            lines.append("    }")

    lines.append("```")
    return DocResult(success=True, content="\n".join(lines))


# ============================================================
# CHANGELOG
# ============================================================

def generate_changelog(n_commits: int = 20) -> DocResult:
    """generate a changelog from recent git history.

    groups commits by type (feat, fix, refactor, docs, test, chore).
    """
    try:
        result = subprocess.run(
            ["git", "log", f"-{n_commits}", "--pretty=format:%h|%s|%an|%ai"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return DocResult(success=False, errors=["git log failed"])
    except Exception as e:
        return DocResult(success=False, errors=[str(e)])

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 3)
        if len(parts) >= 2:
            commits.append({
                "hash": parts[0],
                "message": parts[1],
                "author": parts[2] if len(parts) > 2 else "",
                "date": parts[3][:10] if len(parts) > 3 else "",
            })

    # group by type
    groups: dict[str, list] = {}
    for c in commits:
        ctype = _classify_commit(c["message"])
        groups.setdefault(ctype, []).append(c)

    # format
    lines = ["# Changelog", ""]
    type_labels = {
        "feat": "Features",
        "fix": "Bug Fixes",
        "refactor": "Refactoring",
        "docs": "Documentation",
        "test": "Tests",
        "chore": "Chores",
        "other": "Other",
    }

    for ctype in ["feat", "fix", "refactor", "docs", "test", "chore", "other"]:
        items = groups.get(ctype, [])
        if not items:
            continue
        lines.append(f"## {type_labels.get(ctype, ctype)}")
        lines.append("")
        for c in items:
            lines.append(f"- {c['message']} ({c['hash']})")
        lines.append("")

    return DocResult(success=True, content="\n".join(lines))


# ============================================================
# API SUMMARY
# ============================================================

def generate_api_summary(filepath: str) -> DocResult:
    """generate an API summary of public functions and classes."""
    path = Path(filepath)
    if not path.exists():
        return DocResult(success=False, errors=[f"file not found: {filepath}"])

    try:
        source = path.read_text()
        tree = ast.parse(source)
    except SyntaxError as e:
        return DocResult(success=False, errors=[f"syntax error: {e}"])

    lines = [f"# API: {path.stem}", ""]

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            doc = ast.get_docstring(node) or ""
            lines.append(f"## class {node.name}")
            if doc:
                lines.append(f"  {doc.split(chr(10))[0]}")
            lines.append("")

            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("_") and item.name != "__init__":
                        continue
                    params = _format_params(item)
                    doc = ast.get_docstring(item) or ""
                    lines.append(f"### {item.name}({params})")
                    if doc:
                        lines.append(f"  {doc.split(chr(10))[0]}")
                    lines.append("")

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            params = _format_params(node)
            doc = ast.get_docstring(node) or ""
            lines.append(f"## {node.name}({params})")
            if doc:
                lines.append(f"  {doc.split(chr(10))[0]}")
            lines.append("")

    return DocResult(success=True, content="\n".join(lines))


# ============================================================
# HELPERS
# ============================================================

def _has_docstring(node) -> bool:
    """check if a function or class has a docstring."""
    return (node.body and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant))


def _get_indent(lines: list[str], line_idx: int) -> str:
    """get the indentation of a line."""
    if line_idx < len(lines):
        line = lines[line_idx]
        return line[:len(line) - len(line.lstrip())]
    return ""


def _generate_func_docstring(node, style: str) -> str:
    """generate a docstring for a function."""
    params = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
    name = node.name

    if style == "terse":
        # keanu style: lowercase, terse
        return f'"""{name}."""'

    if style == "numpy":
        lines = [f'"""{name}.', "", "Parameters", "----------"]
        for p in params:
            lines.append(f"{p} : TYPE")
            lines.append(f"    Description.")
        if node.returns:
            lines.extend(["", "Returns", "-------", "TYPE", "    Description."])
        lines.append('"""')
        return "\n".join(lines)

    # google style (default)
    if not params:
        return f'"""{name}."""'
    lines = [f'"""{name}.', ""]
    if params:
        lines.append("Args:")
        for p in params:
            lines.append(f"    {p}: Description.")
    if node.returns:
        lines.extend(["", "Returns:", "    Description."])
    lines.append('"""')
    return "\n".join(lines)


def _generate_class_docstring(node, style: str) -> str:
    """generate a docstring for a class."""
    if style == "terse":
        return f'"""{node.name}."""'
    return f'"""{node.name}."""'


def _classify_commit(message: str) -> str:
    """classify a commit message by conventional commit type."""
    msg = message.lower().strip()

    # conventional commits: feat:, fix:, etc.
    for prefix in ["feat", "fix", "refactor", "docs", "test", "chore"]:
        if msg.startswith(f"{prefix}:") or msg.startswith(f"{prefix}("):
            return prefix

    # heuristic
    if any(w in msg for w in ["add", "new", "implement", "create", "build"]):
        return "feat"
    if any(w in msg for w in ["fix", "bug", "patch", "repair", "resolve"]):
        return "fix"
    if any(w in msg for w in ["refactor", "clean", "simplify", "rename", "move"]):
        return "refactor"
    if any(w in msg for w in ["doc", "readme", "comment", "changelog"]):
        return "docs"
    if any(w in msg for w in ["test", "spec", "assert"]):
        return "test"

    return "other"


def _format_params(node) -> str:
    """format function parameters for display."""
    params = []
    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        params.append(arg.arg)
    return ", ".join(params)


def _simplify_name(filepath: str) -> str:
    """simplify a filepath for diagram display."""
    name = Path(filepath).stem
    return name.replace("-", "_")
