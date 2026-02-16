"""codegen.py - code generation utilities.

scaffold boilerplate, generate tests from function signatures,
implement stubs from context. template-based where possible,
oracle-powered for complex generation.

in the world: the blueprint. you sketch the shape, the details fill in.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GeneratedCode:
    """result of a code generation operation."""
    success: bool
    code: str = ""
    filepath: str = ""
    errors: list[str] = field(default_factory=list)


# ============================================================
# SCAFFOLD
# ============================================================

_TEMPLATES = {
    "ability": '''"""{{name}}.py - {{description}}."""

from keanu.abilities import Ability, ability


@ability
class {{class_name}}(Ability):

    name = "{{name}}"
    description = "{{description}}"
    keywords = [{{keywords}}]
    cast_line = "{{name}} activates..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        ctx = context or {}
        # TODO: implement
        return {"success": False, "result": "not implemented", "data": {}}
''',

    "test": '''"""tests for {{module}}."""

import pytest
{%imports%}


class Test{{class_name}}:

    def test_placeholder(self):
        assert True
''',

    "module": '''"""{{name}}.py - {{description}}."""

from dataclasses import dataclass, field


@dataclass
class {{class_name}}:
    """{{description}}."""
    pass
''',

    "cli_command": '''def cmd_{{name}}(args):
    """{{description}}."""
    # TODO: implement
    print("{{name}}: not implemented yet")
''',
}


def scaffold(template: str, variables: dict) -> GeneratedCode:
    """generate code from a template.

    templates use {{variable}} syntax. available templates:
    ability, test, module, cli_command.
    """
    if template not in _TEMPLATES:
        return GeneratedCode(
            success=False,
            errors=[f"unknown template: {template}. available: {', '.join(_TEMPLATES)}"],
        )

    code = _TEMPLATES[template]

    # handle class_name auto-generation
    if "class_name" not in variables and "name" in variables:
        variables["class_name"] = _to_class_name(variables["name"])

    # handle keywords formatting
    if "keywords" in variables and isinstance(variables["keywords"], list):
        variables["keywords"] = ", ".join(f'"{k}"' for k in variables["keywords"])

    # handle conditional imports
    imports = variables.pop("imports", "")
    code = code.replace("{%imports%}", imports)

    for key, value in variables.items():
        code = code.replace("{{" + key + "}}", str(value))

    return GeneratedCode(success=True, code=code)


# ============================================================
# TEST GENERATION
# ============================================================

def generate_tests(filepath: str) -> GeneratedCode:
    """generate test stubs from function signatures in a file.

    reads the file, finds all public functions and classes,
    generates test stubs for each. doesn't need the oracle.
    """
    path = Path(filepath)
    if not path.exists():
        return GeneratedCode(success=False, errors=[f"file not found: {filepath}"])

    try:
        source = path.read_text()
        tree = ast.parse(source)
    except SyntaxError as e:
        return GeneratedCode(success=False, errors=[f"syntax error: {e}"])
    except (OSError, UnicodeDecodeError) as e:
        return GeneratedCode(success=False, errors=[str(e)])

    module_name = path.stem
    rel_import = _file_to_import(filepath)

    # collect public functions and classes
    functions = []
    classes = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                functions.append(node)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                classes.append(node)

    if not functions and not classes:
        return GeneratedCode(success=True, code=f"# no public symbols found in {filepath}\n")

    # build the test file
    lines = [f'"""tests for {module_name}."""', ""]

    # imports
    import_names = []
    for f in functions:
        import_names.append(f.name)
    for c in classes:
        import_names.append(c.name)

    if rel_import and import_names:
        lines.append(f"from {rel_import} import (")
        for name in import_names:
            lines.append(f"    {name},")
        lines.append(")")
    lines.append("")
    lines.append("")

    # generate test stubs for functions
    for func in functions:
        test_name = f"test_{func.name}"
        params = _get_params(func)
        lines.append(f"class Test{_to_class_name(func.name)}:")
        lines.append("")
        lines.append(f"    def {test_name}(self):")

        if params:
            # generate a call with placeholder args
            args = ", ".join(_param_placeholder(p) for p in params)
            lines.append(f"        result = {func.name}({args})")
            lines.append("        assert result is not None")
        else:
            lines.append(f"        result = {func.name}()")
            lines.append("        assert result is not None")

        lines.append("")
        lines.append("")

    # generate test stubs for classes
    for cls in classes:
        lines.append(f"class Test{cls.name}:")
        lines.append("")

        # test instantiation
        init = _find_init(cls)
        if init:
            params = _get_params(init)
            if params:
                args = ", ".join(_param_placeholder(p) for p in params)
                lines.append(f"    def test_create(self):")
                lines.append(f"        obj = {cls.name}({args})")
                lines.append("        assert obj is not None")
            else:
                lines.append(f"    def test_create(self):")
                lines.append(f"        obj = {cls.name}()")
                lines.append("        assert obj is not None")
        else:
            lines.append(f"    def test_create(self):")
            lines.append(f"        obj = {cls.name}()")
            lines.append("        assert obj is not None")

        # test public methods
        for node in ast.iter_child_nodes(cls):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                params = _get_params(node)
                lines.append("")
                lines.append(f"    def test_{node.name}(self):")
                lines.append(f"        # TODO: test {cls.name}.{node.name}")
                lines.append("        assert True")

        lines.append("")
        lines.append("")

    return GeneratedCode(success=True, code="\n".join(lines))


# ============================================================
# IMPLEMENT STUBS
# ============================================================

def find_stubs(filepath: str) -> list[dict]:
    """find TODO/stub/NotImplementedError in a file."""
    path = Path(filepath)
    if not path.exists():
        return []

    try:
        lines = path.read_text().split("\n")
    except (OSError, UnicodeDecodeError):
        return []

    stubs = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if any(marker in stripped for marker in [
            "TODO:", "FIXME:", "raise NotImplementedError",
            "pass  # TODO", "...  # TODO",
        ]):
            stubs.append({
                "line": i,
                "text": stripped[:120],
                "file": filepath,
            })

    return stubs


# ============================================================
# HELPERS
# ============================================================

def _to_class_name(name: str) -> str:
    """convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in name.replace("-", "_").split("_"))


def _file_to_import(filepath: str) -> str:
    """convert a filepath to a Python import path."""
    path = Path(filepath)

    # try to find src/ or the package root
    parts = list(path.parts)
    if "src" in parts:
        idx = parts.index("src")
        parts = parts[idx + 1:]
    elif parts and parts[-1].endswith(".py"):
        # just use the relative parts
        pass

    # remove .py extension
    module = ".".join(parts)
    if module.endswith(".py"):
        module = module[:-3]

    return module


def _get_params(func) -> list[dict]:
    """extract parameters from a function node, skipping self/cls."""
    params = []
    for arg in func.args.args:
        if arg.arg in ("self", "cls"):
            continue
        annotation = ""
        if arg.annotation:
            annotation = ast.dump(arg.annotation) if isinstance(arg.annotation, ast.AST) else ""
        params.append({"name": arg.arg, "annotation": annotation})
    return params


def _param_placeholder(param: dict) -> str:
    """generate a placeholder value for a parameter."""
    name = param["name"]
    ann = param.get("annotation", "")

    if "str" in ann.lower():
        return f'"{name}_value"'
    if "int" in ann.lower() or "float" in ann.lower():
        return "0"
    if "bool" in ann.lower():
        return "True"
    if "list" in ann.lower():
        return "[]"
    if "dict" in ann.lower():
        return "{}"
    if "path" in name.lower() or "file" in name.lower():
        return f'"{name}.txt"'
    return f'"{name}"'


def _find_init(cls) -> Optional[ast.FunctionDef]:
    """find __init__ method in a class."""
    for node in ast.iter_child_nodes(cls):
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            return node
    return None
