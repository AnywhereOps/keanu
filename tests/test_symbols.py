"""tests for symbol finding."""

from keanu.analysis.symbols import (
    find_definition, find_references, find_callers,
    list_symbols, Symbol, Reference,
)


class TestFindDefinition:

    def test_finds_function(self, tmp_path):
        (tmp_path / "foo.py").write_text("def hello():\n    pass\n")
        results = find_definition("hello", str(tmp_path))
        assert len(results) >= 1
        assert results[0].name == "hello"
        assert results[0].kind == "function"
        assert results[0].line == 1

    def test_finds_class(self, tmp_path):
        (tmp_path / "foo.py").write_text("class MyClass:\n    pass\n")
        results = find_definition("MyClass", str(tmp_path))
        assert len(results) >= 1
        assert results[0].kind == "class"

    def test_finds_method(self, tmp_path):
        (tmp_path / "foo.py").write_text(
            "class Foo:\n    def bar(self):\n        pass\n"
        )
        results = find_definition("bar", str(tmp_path))
        assert len(results) >= 1
        assert results[0].kind == "method"
        assert results[0].parent == "Foo"

    def test_finds_variable(self, tmp_path):
        (tmp_path / "foo.py").write_text("MAX_SIZE = 100\n")
        results = find_definition("MAX_SIZE", str(tmp_path))
        assert len(results) >= 1
        assert results[0].kind == "variable"

    def test_not_found(self, tmp_path):
        (tmp_path / "foo.py").write_text("x = 1\n")
        results = find_definition("nonexistent", str(tmp_path))
        assert len(results) == 0

    def test_across_files(self, tmp_path):
        (tmp_path / "a.py").write_text("def greet(): pass\n")
        (tmp_path / "b.py").write_text("def greet(): pass\n")
        results = find_definition("greet", str(tmp_path))
        assert len(results) == 2

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "foo.py").write_text("def hello(): pass\n")
        (tmp_path / "bar.py").write_text("def hello(): pass\n")
        results = find_definition("hello", str(tmp_path))
        assert len(results) == 1
        assert "__pycache__" not in results[0].file

    def test_syntax_error_fallback(self, tmp_path):
        (tmp_path / "bad.py").write_text("def broken(\n")
        # should not crash, may use regex fallback
        results = find_definition("broken", str(tmp_path))
        # may or may not find it, but shouldn't crash
        assert isinstance(results, list)


class TestFindReferences:

    def test_finds_usage(self, tmp_path):
        (tmp_path / "foo.py").write_text(
            "def helper(): pass\n\ndef main():\n    helper()\n"
        )
        refs = find_references("helper", str(tmp_path))
        assert len(refs) >= 2  # definition + usage
        assert any("helper()" in r.context for r in refs)

    def test_caps_at_100(self, tmp_path):
        lines = "\n".join(f"x = foo_{i}" for i in range(200))
        (tmp_path / "big.py").write_text(lines)
        refs = find_references("foo", str(tmp_path))
        assert len(refs) <= 100


class TestFindCallers:

    def test_finds_call(self, tmp_path):
        (tmp_path / "foo.py").write_text(
            "def hello(): pass\n\ndef main():\n    hello()\n    x = hello()\n"
        )
        callers = find_callers("hello", str(tmp_path))
        assert len(callers) >= 2
        # should not include the definition
        assert not any("def hello" in c.context for c in callers)

    def test_skips_imports(self, tmp_path):
        (tmp_path / "foo.py").write_text(
            "from bar import hello\nhello()\n"
        )
        callers = find_callers("hello", str(tmp_path))
        # should skip the import, find the call
        assert len(callers) == 1
        assert callers[0].context == "hello()"

    def test_no_false_positives(self, tmp_path):
        (tmp_path / "foo.py").write_text("x = unhello + 1\n")
        callers = find_callers("hello", str(tmp_path))
        assert len(callers) == 0


class TestListSymbols:

    def test_lists_all(self, tmp_path):
        (tmp_path / "foo.py").write_text(
            "class Foo:\n    def bar(self): pass\n\ndef baz(): pass\n"
        )
        symbols = list_symbols(str(tmp_path / "foo.py"))
        names = [s.name for s in symbols]
        assert "Foo" in names
        assert "bar" in names
        assert "baz" in names

    def test_sorted_by_line(self, tmp_path):
        (tmp_path / "foo.py").write_text(
            "def a(): pass\ndef b(): pass\ndef c(): pass\n"
        )
        symbols = list_symbols(str(tmp_path / "foo.py"))
        lines = [s.line for s in symbols]
        assert lines == sorted(lines)

    def test_nonexistent_file(self):
        symbols = list_symbols("/nonexistent/file.py")
        assert symbols == []


class TestSymbol:

    def test_defaults(self):
        s = Symbol(name="foo", kind="function", file="bar.py", line=1)
        assert s.parent == ""
        assert s.col == 0


class TestReference:

    def test_defaults(self):
        r = Reference(file="foo.py", line=1)
        assert r.context == ""
