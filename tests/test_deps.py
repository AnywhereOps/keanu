"""Tests for the dependency graph module."""

import pytest
from pathlib import Path

from keanu.analysis.deps import (
    build_import_graph, who_imports, what_imports,
    find_circular, external_deps, stats,
    _extract_imports, _build_module_map,
)


@pytest.fixture
def mini_project(tmp_path):
    """create a minimal Python project for testing."""
    pkg = tmp_path / "myapp"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")

    (pkg / "main.py").write_text(
        "from myapp.utils import helper\n"
        "from myapp.db import connect\n"
        "import os\n"
    )
    (pkg / "utils.py").write_text(
        "import json\n"
        "def helper(): pass\n"
    )
    (pkg / "db.py").write_text(
        "from myapp.utils import helper\n"
        "import sqlite3\n"
        "def connect(): pass\n"
    )
    return tmp_path


@pytest.fixture
def circular_project(tmp_path):
    """create a project with circular imports."""
    pkg = tmp_path / "loop"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from loop.b import foo\n")
    (pkg / "b.py").write_text("from loop.a import bar\n")
    return tmp_path


class TestExtractImports:

    def test_import_statement(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("import os\nimport json\n")
        imports = _extract_imports(f)
        assert "os" in imports
        assert "json" in imports

    def test_from_import(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("from pathlib import Path\nfrom os.path import join\n")
        imports = _extract_imports(f)
        assert "pathlib" in imports
        assert "os.path" in imports

    def test_mixed_imports(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("import os\nfrom keanu.oracle import call_oracle\n")
        imports = _extract_imports(f)
        assert "os" in imports
        assert "keanu.oracle" in imports

    def test_syntax_error_file(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def foo(\n")
        imports = _extract_imports(f)
        assert imports == []

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        imports = _extract_imports(f)
        assert imports == []


class TestBuildModuleMap:

    def test_basic_mapping(self, tmp_path):
        pkg = tmp_path / "foo"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "bar.py").write_text("")

        files = list(tmp_path.rglob("*.py"))
        mm = _build_module_map(tmp_path, files)
        assert "foo" in mm
        assert "foo.bar" in mm

    def test_src_prefix_stripped(self, tmp_path):
        src = tmp_path / "src" / "foo"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "bar.py").write_text("")

        files = list(tmp_path.rglob("*.py"))
        mm = _build_module_map(tmp_path, files)
        # both with and without src prefix
        assert "foo" in mm
        assert "foo.bar" in mm


class TestBuildImportGraph:

    def test_basic_graph(self, mini_project):
        graph = build_import_graph(str(mini_project))
        assert "myapp/main.py" in graph["nodes"]
        assert "myapp/utils.py" in graph["nodes"]
        assert "myapp/db.py" in graph["nodes"]

    def test_edges_exist(self, mini_project):
        graph = build_import_graph(str(mini_project))
        edges = graph["edges"]
        # main imports utils and db
        assert ("myapp/main.py", "myapp/utils.py") in edges
        assert ("myapp/main.py", "myapp/db.py") in edges

    def test_imported_by(self, mini_project):
        graph = build_import_graph(str(mini_project))
        utils_node = graph["nodes"]["myapp/utils.py"]
        assert "myapp/main.py" in utils_node["imported_by"]
        assert "myapp/db.py" in utils_node["imported_by"]

    def test_external_deps(self, mini_project):
        graph = build_import_graph(str(mini_project))
        ext = graph["external"]
        assert "os" in ext
        assert "json" in ext
        assert "sqlite3" in ext


class TestWhoImports:

    def test_who_imports_utils(self, mini_project):
        utils_path = str(mini_project / "myapp" / "utils.py")
        importers = who_imports(utils_path, str(mini_project))
        assert "myapp/main.py" in importers
        assert "myapp/db.py" in importers

    def test_who_imports_leaf(self, mini_project):
        main_path = str(mini_project / "myapp" / "main.py")
        importers = who_imports(main_path, str(mini_project))
        assert importers == []


class TestWhatImports:

    def test_what_main_imports(self, mini_project):
        main_path = str(mini_project / "myapp" / "main.py")
        deps = what_imports(main_path, str(mini_project))
        assert "myapp/utils.py" in deps
        assert "myapp/db.py" in deps


class TestCircular:

    def test_finds_circular_imports(self, circular_project):
        cycles = find_circular(str(circular_project))
        assert len(cycles) > 0
        # should contain both a.py and b.py
        flat = [f for cycle in cycles for f in cycle]
        assert any("a.py" in f for f in flat)
        assert any("b.py" in f for f in flat)

    def test_no_circular_in_normal_project(self, mini_project):
        cycles = find_circular(str(mini_project))
        assert len(cycles) == 0


class TestExternalDeps:

    def test_lists_externals(self, mini_project):
        ext = external_deps(str(mini_project))
        assert "os" in ext
        assert "json" in ext
        assert "sqlite3" in ext


class TestStats:

    def test_basic_stats(self, mini_project):
        s = stats(str(mini_project))
        assert s["files"] >= 3
        assert s["edges"] >= 2
        assert s["external"] >= 2
        assert s["avg_imports"] > 0
        assert len(s["hubs"]) > 0

    def test_empty_project(self, tmp_path):
        s = stats(str(tmp_path))
        assert s["files"] == 0
