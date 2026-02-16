"""tests for proactive code suggestions."""

from keanu.analysis.suggestions import (
    scan_file, scan_directory, check_missing_tests,
    Suggestion, SuggestionReport,
    _check_unused_imports, _check_dead_code,
    _check_complexity, _check_style,
)


class TestUnusedImports:

    def test_detects_unused(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("import os\nimport sys\n\nprint(sys.argv)\n")

        suggestions = _check_unused_imports(f.read_text(), str(f))

        names = [s.message for s in suggestions]
        assert any("os" in m for m in names)
        # sys is used
        assert not any("sys" in m for m in names)

    def test_no_false_positive_on_used(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("import json\n\ndata = json.loads('{}')\n")

        suggestions = _check_unused_imports(f.read_text(), str(f))
        assert len(suggestions) == 0

    def test_from_import(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("from os import path, getcwd\n\nprint(path.exists('.'))\n")

        suggestions = _check_unused_imports(f.read_text(), str(f))
        names = [s.message for s in suggestions]
        assert any("getcwd" in m for m in names)


class TestDeadCode:

    def test_code_after_return(self):
        source = "def foo():\n    return 1\n    x = 2\n"
        suggestions = _check_dead_code(source, "test.py")
        assert any("unreachable" in s.message for s in suggestions)

    def test_commented_out_code(self):
        source = "x = 1\n# def old_function():\n#     pass\n"
        suggestions = _check_dead_code(source, "test.py")
        assert any("commented-out" in s.message for s in suggestions)


class TestComplexity:

    def test_long_function(self, tmp_path):
        lines = ["def big():\n"]
        for i in range(60):
            lines.append(f"    x{i} = {i}\n")

        f = tmp_path / "mod.py"
        f.write_text("".join(lines))

        suggestions = _check_complexity(f.read_text(), str(f))
        assert any("lines" in s.message for s in suggestions)

    def test_high_branch_count(self, tmp_path):
        lines = ["def branchy():\n"]
        for i in range(10):
            lines.append(f"    if x{i}:\n        pass\n")

        f = tmp_path / "mod.py"
        f.write_text("".join(lines))

        suggestions = _check_complexity(f.read_text(), str(f))
        assert any("branches" in s.message for s in suggestions)


class TestStyle:

    def test_bare_except(self):
        source = "try:\n    x = 1\nexcept:\n    pass\n"
        suggestions = _check_style(source, "test.py")
        assert any("bare except" in s.message for s in suggestions)

    def test_mutable_default(self):
        source = "def foo(items=[]):\n    pass\n"
        suggestions = _check_style(source, "test.py")
        assert any("mutable default" in s.message for s in suggestions)

    def test_print_in_production(self):
        source = "print('debug')\n"
        suggestions = _check_style(source, "src/keanu/oracle.py")
        assert any("print()" in s.message for s in suggestions)

    def test_print_ok_in_test(self):
        source = "print('debug')\n"
        suggestions = _check_style(source, "tests/test_foo.py")
        assert not any("print()" in s.message for s in suggestions)


class TestScanFile:

    def test_scan_python_file(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("import os\n\nx = 1\n")

        suggestions = scan_file(str(f))
        assert any(s.category == "unused_import" for s in suggestions)

    def test_scan_nonexistent(self):
        assert scan_file("/nonexistent.py") == []

    def test_scan_non_python(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# hello\n")
        assert scan_file(str(f)) == []


class TestScanDirectory:

    def test_scans_multiple_files(self, tmp_path):
        (tmp_path / "a.py").write_text("import os\nx = 1\n")
        (tmp_path / "b.py").write_text("import sys\ny = 1\n")

        report = scan_directory(str(tmp_path))
        assert report.files_scanned == 2
        assert report.count > 0

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "mod.cpython-310.pyc").write_text("")
        (tmp_path / "real.py").write_text("x = 1\n")

        report = scan_directory(str(tmp_path))
        assert report.files_scanned == 1


class TestCheckMissingTests:

    def test_detects_missing(self, tmp_path):
        src = tmp_path / "src"
        tests = tmp_path / "tests"
        src.mkdir()
        tests.mkdir()
        (src / "oracle.py").write_text("x = 1\n")
        (tests / "test_alive.py").write_text("pass\n")

        suggestions = check_missing_tests(str(tmp_path))
        files = [s.file for s in suggestions]
        assert any("oracle" in f for f in files)


class TestSuggestionReport:

    def test_by_category(self):
        report = SuggestionReport(suggestions=[
            Suggestion(file="a.py", line=1, category="unused_import", message="x"),
            Suggestion(file="b.py", line=2, category="unused_import", message="y"),
            Suggestion(file="c.py", line=3, category="style", message="z"),
        ])
        cats = report.by_category()
        assert len(cats["unused_import"]) == 2
        assert len(cats["style"]) == 1

    def test_summary(self):
        report = SuggestionReport(
            suggestions=[Suggestion(file="a.py", line=1, category="style", message="x")],
            files_scanned=5,
        )
        s = report.summary()
        assert "1 suggestions" in s
        assert "5 files" in s

    def test_str(self):
        s = Suggestion(file="a.py", line=10, category="style", message="bare except")
        assert "a.py:10" in str(s)
