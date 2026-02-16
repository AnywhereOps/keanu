"""tests for AST-based code transformations."""

from keanu.analysis.transform import (
    add_import, remove_import, unused_imports,
    rename_function, rename_variable,
    extract_function,
    add_decorator, remove_decorator,
    add_type_hints,
    list_functions, list_classes,
)


class TestAddImport:

    def test_add_plain_import(self):
        source = "x = 1\n"
        result = add_import(source, "os")
        assert "import os\n" in result
        assert "x = 1" in result

    def test_add_from_import(self):
        source = "x = 1\n"
        result = add_import(source, "os.path", ["join", "exists"])
        assert "from os.path import join, exists" in result

    def test_dedup_plain_import(self):
        source = "import os\nx = 1\n"
        result = add_import(source, "os")
        assert result == source

    def test_dedup_from_import(self):
        source = "from os.path import join\n"
        result = add_import(source, "os.path", ["join"])
        assert result == source

    def test_merge_from_import(self):
        source = "from os.path import join\n"
        result = add_import(source, "os.path", ["join", "exists"])
        assert "exists" in result
        assert "join" in result

    def test_after_existing_imports(self):
        source = "import sys\nimport os\n\nx = 1\n"
        result = add_import(source, "json")
        lines = result.splitlines()
        json_idx = next(i for i, l in enumerate(lines) if "import json" in l)
        os_idx = next(i for i, l in enumerate(lines) if "import os" in l)
        assert json_idx > os_idx

    def test_after_docstring(self):
        source = '"""module doc."""\n\nx = 1\n'
        result = add_import(source, "os")
        assert result.index("import os") > result.index('"""')


class TestRemoveImport:

    def test_remove_plain_import(self):
        source = "import os\nimport sys\nx = 1\n"
        result = remove_import(source, "os")
        assert "import os" not in result
        assert "import sys" in result

    def test_remove_from_import(self):
        source = "from os.path import join\nx = 1\n"
        result = remove_import(source, "os.path")
        assert "from os.path" not in result

    def test_remove_single_name(self):
        source = "from os.path import join, exists\n"
        result = remove_import(source, "os.path", "join")
        assert "join" not in result
        assert "exists" in result

    def test_remove_only_name_removes_line(self):
        source = "from os.path import join\nx = 1\n"
        result = remove_import(source, "os.path", "join")
        assert "from os.path" not in result
        assert "x = 1" in result

    def test_remove_nonexistent(self):
        source = "import os\n"
        result = remove_import(source, "json")
        assert result == source


class TestRenameFunction:

    def test_rename_def_and_calls(self):
        source = "def foo():\n    pass\n\nfoo()\n"
        result = rename_function(source, "foo", "bar")
        assert "def bar():" in result
        assert "bar()" in result
        assert "foo" not in result

    def test_rename_with_args(self):
        source = "def compute(x, y):\n    return x + y\n\nresult = compute(1, 2)\n"
        result = rename_function(source, "compute", "add")
        assert "def add(x, y):" in result
        assert "add(1, 2)" in result

    def test_rename_leaves_other_functions(self):
        source = "def foo():\n    pass\ndef bar():\n    pass\n"
        result = rename_function(source, "foo", "baz")
        assert "def baz():" in result
        assert "def bar():" in result


class TestRenameVariable:

    def test_rename_assignment_and_usage(self):
        source = "count = 0\ncount += 1\nprint(count)\n"
        result = rename_variable(source, "count", "total")
        assert "total" in result
        assert "count" not in result

    def test_rename_function_arg(self):
        source = "def foo(x):\n    return x + 1\n"
        result = rename_variable(source, "x", "value")
        assert "value" in result
        assert "(value)" in result or "value)" in result


class TestExtractFunction:

    def test_basic_extract(self):
        source = "def main():\n    x = 1\n    y = 2\n    z = x + y\n    print(z)\n"
        result = extract_function(source, 3, 4, "compute")
        assert "def compute" in result
        assert "compute(" in result

    def test_invalid_range(self):
        source = "x = 1\n"
        result = extract_function(source, 5, 10, "nope")
        assert result == source

    def test_preserves_before_and_after(self):
        source = "a = 1\nb = 2\nc = 3\nd = 4\n"
        result = extract_function(source, 2, 3, "mid")
        assert "a = 1" in result
        assert "d = 4" in result


class TestAddDecorator:

    def test_add_decorator(self):
        source = "def foo():\n    pass\n"
        result = add_decorator(source, "foo", "@staticmethod")
        assert "@staticmethod" in result
        assert result.index("@staticmethod") < result.index("def foo")

    def test_add_without_at(self):
        source = "def foo():\n    pass\n"
        result = add_decorator(source, "foo", "staticmethod")
        assert "@staticmethod" in result

    def test_dedup_decorator(self):
        source = "@staticmethod\ndef foo():\n    pass\n"
        result = add_decorator(source, "foo", "staticmethod")
        assert result.count("@staticmethod") == 1

    def test_add_to_class(self):
        source = "class Foo:\n    pass\n"
        result = add_decorator(source, "Foo", "dataclass")
        assert "@dataclass" in result


class TestRemoveDecorator:

    def test_remove_decorator(self):
        source = "@staticmethod\ndef foo():\n    pass\n"
        result = remove_decorator(source, "foo", "staticmethod")
        assert "@staticmethod" not in result
        assert "def foo" in result

    def test_remove_nonexistent(self):
        source = "def foo():\n    pass\n"
        result = remove_decorator(source, "foo", "staticmethod")
        assert result == source

    def test_remove_one_of_many(self):
        source = "@property\n@staticmethod\ndef foo():\n    pass\n"
        result = remove_decorator(source, "foo", "staticmethod")
        assert "@property" in result
        assert "@staticmethod" not in result


class TestListFunctions:

    def test_basic(self):
        source = "def foo(x, y):\n    return x + y\n\ndef bar():\n    pass\n"
        funcs = list_functions(source)
        assert len(funcs) == 2
        assert funcs[0]["name"] == "foo"
        assert funcs[0]["args"] == ["x", "y"]
        assert funcs[1]["name"] == "bar"

    def test_with_decorators(self):
        source = "@property\ndef value(self):\n    return 1\n"
        funcs = list_functions(source)
        assert funcs[0]["decorators"] == ["property"]

    def test_with_return_type(self):
        source = "def foo() -> int:\n    return 1\n"
        funcs = list_functions(source)
        assert funcs[0]["returns"] == "int"

    def test_no_return_type(self):
        source = "def foo():\n    pass\n"
        funcs = list_functions(source)
        assert funcs[0]["returns"] is None


class TestListClasses:

    def test_basic(self):
        source = "class Foo:\n    def bar(self):\n        pass\n"
        classes = list_classes(source)
        assert len(classes) == 1
        assert classes[0]["name"] == "Foo"
        assert "bar" in classes[0]["methods"]

    def test_with_bases(self):
        source = "class Foo(Bar, Baz):\n    pass\n"
        classes = list_classes(source)
        assert classes[0]["bases"] == ["Bar", "Baz"]

    def test_with_decorator(self):
        source = "@dataclass\nclass Foo:\n    x: int = 0\n"
        classes = list_classes(source)
        assert classes[0]["decorators"] == ["dataclass"]


class TestUnusedImports:

    def test_find_unused(self):
        source = "import os\nimport sys\nprint(sys.argv)\n"
        unused = unused_imports(source)
        assert "os" in unused

    def test_all_used(self):
        source = "import os\nos.path.exists('.')\n"
        unused = unused_imports(source)
        assert len(unused) == 0

    def test_from_import_unused(self):
        source = "from os.path import join, exists\nprint(join('a', 'b'))\n"
        unused = unused_imports(source)
        assert any("exists" in u for u in unused)

    def test_no_imports(self):
        source = "x = 1\n"
        assert unused_imports(source) == []


class TestAddTypeHints:

    def test_int_literal(self):
        source = "x = 42\n"
        result = add_type_hints(source)
        assert "int" in result

    def test_str_literal(self):
        source = 'name = "hello"\n'
        result = add_type_hints(source)
        assert "str" in result

    def test_bool_literal(self):
        source = "flag = True\n"
        result = add_type_hints(source)
        assert "bool" in result

    def test_none_return(self):
        source = "def foo():\n    print('hi')\n"
        result = add_type_hints(source)
        assert "None" in result

    def test_leaves_existing_hints(self):
        source = "x: int = 42\n"
        result = add_type_hints(source)
        assert "int" in result

    def test_no_hint_for_complex(self):
        source = "x = some_function()\n"
        result = add_type_hints(source)
        # should not add a type hint for unknown call
        assert ": " not in result or "x = some_function()" in result
