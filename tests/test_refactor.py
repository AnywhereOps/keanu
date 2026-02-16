"""tests for refactoring operations."""

from keanu.analysis.refactor import (
    rename, extract_function, move_symbol, RefactorResult,
    _find_used_names, _find_defined_names, _find_block_end,
    _find_containing_function, _find_import_end,
)


class TestRename:

    def test_rename_function(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def old_func():\n    return 1\n\nresult = old_func()\n")

        result = rename("old_func", "new_func", root=str(tmp_path))

        assert result.success
        content = f.read_text()
        assert "def new_func():" in content
        assert "result = new_func()" in content
        assert "old_func" not in content

    def test_rename_variable(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("count = 0\ncount += 1\nprint(count)\n")

        result = rename("count", "total", root=str(tmp_path))

        assert result.success
        content = f.read_text()
        assert "total = 0" in content
        assert "total += 1" in content

    def test_rename_across_files(self, tmp_path):
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("def helper():\n    pass\n")
        b.write_text("from a import helper\nhelper()\n")

        result = rename("helper", "util", root=str(tmp_path))

        assert result.success
        assert len(result.files_changed) == 2

    def test_rename_not_found(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("x = 1\n")

        result = rename("nonexistent", "new", root=str(tmp_path))

        assert not result.success

    def test_rename_dry_run(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def foo():\n    pass\n")

        result = rename("foo", "bar", root=str(tmp_path), dry_run=True)

        assert result.success
        assert result.dry_run
        assert "foo" in f.read_text()  # not actually changed

    def test_rename_same_name(self):
        result = rename("x", "x")
        assert not result.success

    def test_rename_empty(self):
        result = rename("", "new")
        assert not result.success

    def test_word_boundary(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("count = 0\ncounter = 0\nrecount = 0\n")

        result = rename("count", "total", root=str(tmp_path))

        content = f.read_text()
        assert "total = 0" in content
        # should NOT rename counter or recount
        assert "counter" in content
        assert "recount" in content


class TestExtractFunction:

    def test_basic_extract(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def main():\n    x = 1\n    y = 2\n    z = x + y\n    print(z)\n")

        result = extract_function(str(f), 3, 4, "compute")

        assert result.success
        content = f.read_text()
        assert "def compute" in content

    def test_extract_invalid_range(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("x = 1\n")

        result = extract_function(str(f), 5, 10, "nope")
        assert not result.success

    def test_extract_nonexistent_file(self):
        result = extract_function("/nonexistent.py", 1, 2, "foo")
        assert not result.success

    def test_extract_dry_run(self, tmp_path):
        f = tmp_path / "mod.py"
        original = "def main():\n    x = 1\n    y = 2\n"
        f.write_text(original)

        result = extract_function(str(f), 2, 3, "setup", dry_run=True)

        assert result.success
        assert result.dry_run
        assert f.read_text() == original


class TestMoveSymbol:

    def test_move_function(self, tmp_path):
        src = tmp_path / "source.py"
        dst = tmp_path / "dest.py"
        src.write_text("import os\n\ndef helper():\n    return 1\n\ndef main():\n    pass\n")
        dst.write_text("# dest\n")

        result = move_symbol("helper", "source.py", "dest.py", root=str(tmp_path))

        assert result.success
        assert "def helper" in dst.read_text()
        # source should have re-export
        assert "import helper" in src.read_text()

    def test_move_not_found(self, tmp_path):
        src = tmp_path / "source.py"
        src.write_text("x = 1\n")

        result = move_symbol("nonexistent", "source.py", "dest.py", root=str(tmp_path))
        assert not result.success

    def test_move_source_missing(self, tmp_path):
        result = move_symbol("foo", "nope.py", "dest.py", root=str(tmp_path))
        assert not result.success

    def test_move_dry_run(self, tmp_path):
        src = tmp_path / "source.py"
        src.write_text("def myfunc():\n    pass\n")
        original = src.read_text()

        result = move_symbol("myfunc", "source.py", "dest.py",
                            root=str(tmp_path), dry_run=True)

        assert result.success
        assert result.dry_run
        assert src.read_text() == original


class TestHelpers:

    def test_find_used_names(self):
        lines = ["x = foo(bar)", "print(x)"]
        names = _find_used_names(lines)
        assert "foo" in names
        assert "bar" in names
        assert "x" in names
        assert "print" not in names  # filtered as builtin

    def test_find_defined_names(self):
        lines = ["x = 1", "for i in range(10):", "    y = i"]
        names = _find_defined_names(lines)
        assert "x" in names
        assert "i" in names

    def test_find_block_end(self):
        lines = ["def foo():", "    x = 1", "    return x", "", "y = 2"]
        assert _find_block_end(lines, 0) == 4

    def test_find_containing_function(self):
        lines = ["def main():", "    x = 1", "    y = 2"]
        assert _find_containing_function(lines, 3) == 1

    def test_find_import_end(self):
        lines = ["import os", "from sys import path", "", "x = 1"]
        assert _find_import_end(lines) == 2
