"""tests for code generation utilities."""

from keanu.gen.codegen import (
    scaffold, generate_tests, find_stubs,
    _to_class_name, _file_to_import, _param_placeholder,
)


class TestScaffold:

    def test_ability_template(self):
        result = scaffold("ability", {
            "name": "greet",
            "description": "Say hello",
            "keywords": ["hello", "greet"],
        })
        assert result.success
        assert "class Greet" in result.code
        assert 'name = "greet"' in result.code
        assert '"hello"' in result.code

    def test_test_template(self):
        result = scaffold("test", {
            "module": "greet",
            "class_name": "Greet",
            "imports": "from keanu.greet import Greet",
        })
        assert result.success
        assert "class TestGreet" in result.code
        assert "from keanu.greet" in result.code

    def test_module_template(self):
        result = scaffold("module", {
            "name": "parser",
            "description": "Parse things",
        })
        assert result.success
        assert "class Parser" in result.code

    def test_cli_command_template(self):
        result = scaffold("cli_command", {
            "name": "deploy",
            "description": "Deploy the app",
        })
        assert result.success
        assert "def cmd_deploy" in result.code

    def test_unknown_template(self):
        result = scaffold("nonexistent", {})
        assert not result.success

    def test_auto_class_name(self):
        result = scaffold("module", {"name": "my_parser", "description": "x"})
        assert "MyParser" in result.code


class TestGenerateTests:

    def test_from_functions(self, tmp_path):
        f = tmp_path / "mymod.py"
        f.write_text("def add(a: int, b: int) -> int:\n    return a + b\n\ndef greet(name: str):\n    print(name)\n")

        result = generate_tests(str(f))

        assert result.success
        assert "test_add" in result.code
        assert "test_greet" in result.code

    def test_from_classes(self, tmp_path):
        f = tmp_path / "models.py"
        f.write_text("class User:\n    def __init__(self, name: str):\n        self.name = name\n\n    def greet(self):\n        return f'hi {self.name}'\n")

        result = generate_tests(str(f))

        assert result.success
        assert "TestUser" in result.code
        assert "test_create" in result.code
        assert "test_greet" in result.code

    def test_nonexistent_file(self):
        result = generate_tests("/nonexistent.py")
        assert not result.success

    def test_syntax_error_file(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def broken(:\n")

        result = generate_tests(str(f))
        assert not result.success

    def test_no_public_symbols(self, tmp_path):
        f = tmp_path / "private.py"
        f.write_text("_helper = 1\n\ndef _internal():\n    pass\n")

        result = generate_tests(str(f))
        assert result.success
        assert "no public symbols" in result.code

    def test_function_with_no_params(self, tmp_path):
        f = tmp_path / "simple.py"
        f.write_text("def hello():\n    return 'hi'\n")

        result = generate_tests(str(f))
        assert result.success
        assert "hello()" in result.code


class TestFindStubs:

    def test_finds_todos(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def foo():\n    # TODO: implement\n    pass\n")

        stubs = find_stubs(str(f))
        assert len(stubs) == 1
        assert "TODO" in stubs[0]["text"]

    def test_finds_not_implemented(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def foo():\n    raise NotImplementedError\n")

        stubs = find_stubs(str(f))
        assert len(stubs) == 1

    def test_nonexistent_file(self):
        assert find_stubs("/nonexistent.py") == []

    def test_no_stubs(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def foo():\n    return 1\n")

        assert find_stubs(str(f)) == []


class TestHelpers:

    def test_to_class_name(self):
        assert _to_class_name("my_func") == "MyFunc"
        assert _to_class_name("simple") == "Simple"
        assert _to_class_name("my-thing") == "MyThing"

    def test_file_to_import(self):
        result = _file_to_import("src/keanu/oracle.py")
        assert "keanu.oracle" in result

    def test_param_placeholder_str(self):
        p = _param_placeholder({"name": "text", "annotation": "Name(id='str')"})
        assert '"' in p

    def test_param_placeholder_int(self):
        p = _param_placeholder({"name": "count", "annotation": "Name(id='int')"})
        assert p == "0"

    def test_param_placeholder_default(self):
        p = _param_placeholder({"name": "x", "annotation": ""})
        assert '"' in p

    def test_param_placeholder_path(self):
        p = _param_placeholder({"name": "file_path", "annotation": ""})
        assert "file_path" in p
