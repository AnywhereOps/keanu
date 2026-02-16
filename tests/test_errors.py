"""Tests for the error parser."""

import pytest

from keanu.errors import parse, ParsedError


class TestPythonTraceback:

    def test_basic_traceback(self):
        text = """Traceback (most recent call last):
  File "src/keanu/oracle.py", line 42, in call_oracle
    result = _reach_cloud(prompt, system, leg, use_model)
  File "src/keanu/oracle.py", line 95, in _reach_cloud
    response.raise_for_status()
ConnectionError: no response from creator"""
        err = parse(text)
        assert err.category == "connection"
        assert err.file == "src/keanu/oracle.py"
        assert err.line == 95
        assert err.function == "_reach_cloud"
        assert "no response" in err.message
        assert len(err.traceback) == 2

    def test_import_error(self):
        text = """Traceback (most recent call last):
  File "src/keanu/cli.py", line 5, in <module>
    from keanu.scan.helix import run
ModuleNotFoundError: No module named 'chromadb'"""
        err = parse(text)
        assert err.category == "import"
        assert "chromadb" in err.message
        assert err.file == "src/keanu/cli.py"
        assert "install" in err.suggestion.lower()

    def test_syntax_error(self):
        text = """Traceback (most recent call last):
  File "test.py", line 10
    def foo(
          ^
SyntaxError: unexpected EOF while parsing"""
        err = parse(text)
        assert err.category == "syntax"
        assert "unexpected EOF" in err.message

    def test_type_error(self):
        text = """Traceback (most recent call last):
  File "src/keanu/hero/do.py", line 334, in run
    response = call_oracle(prompt, system, legend=legend)
TypeError: call_oracle() got an unexpected keyword argument 'system'"""
        err = parse(text)
        assert err.category == "type"
        assert "unexpected keyword" in err.message
        assert err.line == 334

    def test_key_error(self):
        text = """Traceback (most recent call last):
  File "src/keanu/hero/do.py", line 352, in run
    thinking = parsed["thinking"]
KeyError: 'thinking'"""
        err = parse(text)
        assert err.category == "key"

    def test_assertion_error(self):
        text = """Traceback (most recent call last):
  File "tests/test_abilities.py", line 29, in test_all_abilities_registered
    assert expected.issubset(names)
AssertionError: assert {'git'} <= {'read', 'write'}"""
        err = parse(text)
        assert err.category == "assertion"

    def test_summary(self):
        text = """Traceback (most recent call last):
  File "foo.py", line 10, in bar
    x = 1/0
ZeroDivisionError: division by zero"""
        err = parse(text)
        s = err.summary()
        assert "foo.py:10" in s
        assert "division by zero" in s

    def test_location(self):
        err = ParsedError(file="foo.py", line=42)
        assert err.location == "foo.py:42"

    def test_location_no_line(self):
        err = ParsedError(file="foo.py")
        assert err.location == "foo.py"

    def test_location_empty(self):
        err = ParsedError()
        assert err.location == ""


class TestPytestFailure:

    def test_basic_failure(self):
        text = """FAILED tests/test_abilities.py::TestHands::test_read_execute - AssertionError: assert False
short test summary info
FAILED tests/test_abilities.py::TestHands::test_read_execute"""
        err = parse(text)
        assert err.file == "tests/test_abilities.py"
        assert err.function == "test_read_execute"

    def test_assertion_detail(self):
        text = """tests/test_foo.py::TestBar::test_baz FAILED
E       assert 42 == 43
E        +  where 42 = len([1, 2, 3])
FAILED tests/test_foo.py::TestBar::test_baz"""
        err = parse(text)
        assert "42 == 43" in err.message
        assert err.category == "assertion"

    def test_error_in_test(self):
        text = """tests/test_foo.py::test_something FAILED
E       TypeError: 'NoneType' object is not callable
FAILED tests/test_foo.py::test_something"""
        err = parse(text)
        assert err.category == "type"
        assert "NoneType" in err.message


class TestJSError:

    def test_basic_js_error(self):
        text = """TypeError: Cannot read properties of undefined (reading 'map')
    at renderList (/app/src/components/List.js:42:15)
    at Object.<anonymous> (/app/src/App.js:10:5)"""
        err = parse(text)
        assert err.category == "type"
        assert "Cannot read properties" in err.message
        assert err.file == "/app/src/components/List.js"
        assert err.line == 42
        assert err.function == "renderList"
        assert len(err.traceback) == 2

    def test_reference_error(self):
        text = """ReferenceError: foo is not defined
    at main (/app/index.js:5:1)"""
        err = parse(text)
        assert err.category == "name"
        assert "foo is not defined" in err.message

    def test_syntax_error_js(self):
        text = """SyntaxError: Unexpected token '}'
    at Module._compile (node:internal/modules/cjs/loader:1126:14)
    at /app/src/server.js:22:3"""
        err = parse(text)
        assert err.category == "syntax"


class TestGoPanic:

    def test_basic_panic(self):
        text = """panic: runtime error: index out of range [5] with length 3

goroutine 1 [running]:
main.processItems(...)
        /app/main.go:42 +0x1a4
main.main()
        /app/main.go:15 +0x68"""
        err = parse(text)
        assert err.category == "panic"
        assert "index out of range" in err.message
        assert err.file == "/app/main.go"
        assert err.line == 42
        assert len(err.traceback) == 2


class TestGeneric:

    def test_permission_denied(self):
        err = parse("bash: /etc/passwd: Permission denied")
        assert err.category == "permission"

    def test_timeout(self):
        err = parse("Error: Connection timed out after 30000ms")
        assert err.category == "timeout"

    def test_command_not_found(self):
        err = parse("bash: ruff: command not found")
        assert err.category == "missing_tool"

    def test_empty_text(self):
        err = parse("")
        assert err.category == "unknown"

    def test_gibberish(self):
        err = parse("xyzzy plugh nothing useful here")
        assert err.category == "unknown"
        assert err.message  # should have something


class TestSuggestions:

    def test_import_suggestion(self):
        text = """Traceback (most recent call last):
  File "foo.py", line 1, in <module>
    import numpy
ModuleNotFoundError: No module named 'numpy'"""
        err = parse(text)
        assert "install" in err.suggestion.lower()

    def test_io_suggestion(self):
        text = """Traceback (most recent call last):
  File "foo.py", line 5, in load
    open("missing.txt")
FileNotFoundError: [Errno 2] No such file or directory: 'missing.txt'"""
        err = parse(text)
        assert "path" in err.suggestion.lower() or "file" in err.suggestion.lower()

    def test_syntax_suggestion(self):
        text = """Traceback (most recent call last):
  File "foo.py", line 10
    def foo(
          ^
SyntaxError: unexpected EOF"""
        err = parse(text)
        assert "syntax" in err.suggestion.lower()
