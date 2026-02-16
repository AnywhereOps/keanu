"""deps.py - dependency graph for Python projects.

parses import statements to build a graph of which files depend on which.
used by the context manager to know: "if I edit file A, what else might break?"

in the world: the web. pull one thread, see what moves.
"""

import ast
import os
from collections import defaultdict
from pathlib import Path


def build_import_graph(root: str = ".") -> dict:
    """build a graph of Python imports within a project.

    returns {
        "nodes": {filepath: {"imports": [...], "imported_by": [...]}},
        "edges": [(from_file, to_file), ...],
        "external": {package_name: [files_that_import_it]},
    }
    """
    root_path = Path(root).resolve()
    py_files = list(root_path.rglob("*.py"))

    # map module paths to file paths
    module_map = _build_module_map(root_path, py_files)

    nodes = {}
    edges = []
    external = defaultdict(list)

    for py_file in py_files:
        rel = str(py_file.relative_to(root_path))
        imports = _extract_imports(py_file)

        resolved = []
        for imp in imports:
            target = module_map.get(imp)
            if target:
                resolved.append(target)
                edges.append((rel, target))
            else:
                # external dependency
                top_level = imp.split(".")[0]
                external[top_level].append(rel)

        nodes[rel] = {"imports": resolved, "imported_by": []}

    # build reverse edges
    for from_file, to_file in edges:
        if to_file in nodes:
            nodes[to_file]["imported_by"].append(from_file)

    return {
        "nodes": nodes,
        "edges": edges,
        "external": dict(external),
    }


def who_imports(filepath: str, root: str = ".") -> list[str]:
    """find all files that import the given file.

    the key question: "if I change this file, what might break?"
    """
    graph = build_import_graph(root)
    rel = str(Path(filepath).relative_to(Path(root).resolve()))
    node = graph["nodes"].get(rel, {})
    return node.get("imported_by", [])


def what_imports(filepath: str, root: str = ".") -> list[str]:
    """find all files that the given file imports.

    useful for understanding context: "what does this file depend on?"
    """
    graph = build_import_graph(root)
    rel = str(Path(filepath).relative_to(Path(root).resolve()))
    node = graph["nodes"].get(rel, {})
    return node.get("imports", [])


def find_circular(root: str = ".") -> list[list[str]]:
    """find circular import chains.

    returns a list of cycles, each cycle is a list of file paths.
    """
    graph = build_import_graph(root)
    edges_map = defaultdict(list)
    for from_file, to_file in graph["edges"]:
        edges_map[from_file].append(to_file)

    visited = set()
    path = []
    path_set = set()
    cycles = []

    def dfs(node):
        if node in path_set:
            # found a cycle
            idx = path.index(node)
            cycle = path[idx:] + [node]
            cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        path.append(node)
        path_set.add(node)
        for neighbor in edges_map.get(node, []):
            dfs(neighbor)
        path.pop()
        path_set.remove(node)

    for node in graph["nodes"]:
        dfs(node)

    return cycles


def external_deps(root: str = ".") -> dict:
    """list external dependencies and which files use them.

    useful for: "you imported X but it's not in requirements.txt"
    """
    graph = build_import_graph(root)
    return graph["external"]


def stats(root: str = ".") -> dict:
    """summary stats for the dependency graph."""
    graph = build_import_graph(root)
    nodes = graph["nodes"]
    edges = graph["edges"]

    if not nodes:
        return {"files": 0, "edges": 0, "external": 0, "avg_imports": 0}

    total_imports = sum(len(n["imports"]) for n in nodes.values())

    # find most-imported files (hubs)
    import_counts = defaultdict(int)
    for _, to_file in edges:
        import_counts[to_file] += 1
    hubs = sorted(import_counts.items(), key=lambda x: -x[1])[:10]

    return {
        "files": len(nodes),
        "edges": len(edges),
        "external": len(graph["external"]),
        "avg_imports": round(total_imports / len(nodes), 1),
        "hubs": [{"file": f, "imported_by": c} for f, c in hubs],
    }


# ============================================================
# INTERNALS
# ============================================================

def _build_module_map(root: Path, py_files: list[Path]) -> dict:
    """map dotted module names to relative file paths."""
    module_map = {}

    for py_file in py_files:
        rel = py_file.relative_to(root)
        parts = list(rel.parts)

        # foo/bar/baz.py -> foo.bar.baz
        if parts[-1] == "__init__.py":
            # foo/bar/__init__.py -> foo.bar
            module_name = ".".join(parts[:-1])
        else:
            # foo/bar/baz.py -> foo.bar.baz
            module_name = ".".join(parts)[:-3]  # strip .py

        rel_str = str(rel)
        module_map[module_name] = rel_str

        # also map with src/ prefix stripped if present
        if parts[0] == "src" and len(parts) > 1:
            if parts[-1] == "__init__.py":
                alt = ".".join(parts[1:-1])
            else:
                alt = ".".join(parts[1:])[:-3]
            module_map[alt] = rel_str

    return module_map


def _extract_imports(filepath: Path) -> list[str]:
    """extract import targets from a Python file using AST.

    returns dotted module names: ["keanu.oracle", "os", "json"]
    """
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    return imports
