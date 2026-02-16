"""templates.py - lightweight template engine for code generation.

renders templates with {{var}} substitution, manages user and built-in
templates, validates context. used by forge, codegen, scaffold, docgen.

in the world: templates are molds. pour context in, shaped code comes out.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import ensure_dir, keanu_home

TEMPLATES_DIR = keanu_home() / "templates"
_VAR_RE = re.compile(r"\{\{(\w+)(?:\|([^}]*))?\}\}")


@dataclass
class TemplateVar:
    """a single template variable."""
    name: str
    description: str = ""
    default: str = ""
    required: bool = True


@dataclass
class Template:
    """a renderable template with metadata."""
    name: str
    content: str
    variables: list[TemplateVar] = field(default_factory=list)
    language: str = "python"
    category: str = "general"


def render(template: Template, context: dict) -> str:
    """substitute {{var}} and {{var|default}} in template content."""
    def _replace(match):
        var_name = match.group(1)
        inline_default = match.group(2)
        if var_name in context:
            return str(context[var_name])
        if inline_default is not None:
            return inline_default
        # check TemplateVar defaults
        for v in template.variables:
            if v.name == var_name and v.default:
                return v.default
        return match.group(0)

    return _VAR_RE.sub(_replace, template.content)


def validate_context(template: Template, context: dict) -> tuple[bool, list[str]]:
    """check that all required vars are present. returns (ok, missing_names)."""
    missing = []
    for v in template.variables:
        if v.required and v.name not in context and not v.default:
            missing.append(v.name)
    return (len(missing) == 0, missing)


def _template_path(name: str) -> Path:
    """path for a user template."""
    return TEMPLATES_DIR / f"{name}.json"


def save_template(template: Template) -> None:
    """persist a template to ~/.keanu/templates/."""
    ensure_dir(TEMPLATES_DIR)
    data = {
        "name": template.name,
        "content": template.content,
        "variables": [
            {"name": v.name, "description": v.description,
             "default": v.default, "required": v.required}
            for v in template.variables
        ],
        "language": template.language,
        "category": template.category,
    }
    _template_path(template.name).write_text(json.dumps(data, indent=2) + "\n")


def load_template(name: str) -> Template:
    """load a user template from ~/.keanu/templates/."""
    path = _template_path(name)
    if not path.exists():
        raise FileNotFoundError(f"template not found: {name}")
    data = json.loads(path.read_text())
    variables = [TemplateVar(**v) for v in data.get("variables", [])]
    return Template(
        name=data["name"],
        content=data["content"],
        variables=variables,
        language=data.get("language", "python"),
        category=data.get("category", "general"),
    )


def delete_template(name: str) -> bool:
    """remove a user template. returns True if it existed."""
    path = _template_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


def list_templates(category: str = "", language: str = "") -> list[Template]:
    """list user templates, optionally filtered by category or language."""
    if not TEMPLATES_DIR.exists():
        return []
    results = []
    for f in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            t = load_template(f.stem)
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            continue
        if category and t.category != category:
            continue
        if language and t.language != language:
            continue
        results.append(t)
    return results


# ============================================================
# BUILT-IN TEMPLATES
# ============================================================

BUILTIN_TEMPLATES: dict[str, Template] = {}


def _builtin(name: str, content: str, variables: list[TemplateVar],
             language: str = "python", category: str = "general") -> None:
    """register a built-in template."""
    BUILTIN_TEMPLATES[name] = Template(
        name=name, content=content, variables=variables,
        language=language, category=category,
    )


_builtin("python_function", '''\
def {{name}}({{params|}}):
    """{{docstring|todo: add docstring.}}"""
    {{body|pass}}
''', [
    TemplateVar("name", "function name", required=True),
    TemplateVar("params", "parameter list", default=""),
    TemplateVar("docstring", "docstring text", default="todo: add docstring."),
    TemplateVar("body", "function body", default="pass"),
], category="code")

_builtin("python_class", '''\
class {{name}}:
    """{{docstring|todo: add docstring.}}"""

    def __init__(self{{init_params|}}):
        {{init_body|pass}}

    {{methods|pass}}
''', [
    TemplateVar("name", "class name", required=True),
    TemplateVar("docstring", "class docstring", default="todo: add docstring."),
    TemplateVar("init_params", "init parameters after self", default=""),
    TemplateVar("init_body", "init body", default="pass"),
    TemplateVar("methods", "additional methods", default="pass"),
], category="code")

_builtin("python_test", '''\
"""tests for {{module}}.{{name|}}"""

import pytest


class Test{{class_name}}:

    def test_{{test_name|basic}}(self):
        {{body|assert True}}
''', [
    TemplateVar("module", "module under test", required=True),
    TemplateVar("name", "what is being tested", default=""),
    TemplateVar("class_name", "test class name", required=True),
    TemplateVar("test_name", "first test method name", default="basic"),
    TemplateVar("body", "test body", default="assert True"),
], category="test")

_builtin("python_dataclass", '''\
from dataclasses import dataclass{{extra_imports|}}


@dataclass
class {{name}}:
    """{{docstring|todo: add docstring.}}"""
    {{fields|pass}}
''', [
    TemplateVar("name", "dataclass name", required=True),
    TemplateVar("docstring", "class docstring", default="todo: add docstring."),
    TemplateVar("fields", "field definitions", default="pass"),
    TemplateVar("extra_imports", "additional imports", default=""),
], category="code")

_builtin("fastapi_endpoint", '''\
from fastapi import APIRouter{{extra_imports|}}

router = APIRouter()


@router.{{method|get}}("{{path}}")
async def {{name}}({{params|}}):
    """{{docstring|todo: add docstring.}}"""
    {{body|return {"status": "ok"}}}
''', [
    TemplateVar("name", "handler function name", required=True),
    TemplateVar("path", "route path", required=True),
    TemplateVar("method", "HTTP method", default="get"),
    TemplateVar("params", "handler parameters", default=""),
    TemplateVar("docstring", "endpoint docstring", default="todo: add docstring."),
    TemplateVar("body", "handler body", default='return {"status": "ok"}'),
    TemplateVar("extra_imports", "additional imports", default=""),
], category="web")

_builtin("cli_command", '''\
import argparse


def {{name}}(args):
    """{{docstring|todo: add docstring.}}"""
    {{body|print("done")}}


def build_parser():
    parser = argparse.ArgumentParser(description="{{description|a cli command}}")
    {{arguments|pass}}
    return parser


if __name__ == "__main__":
    parser = build_parser()
    {{name}}(parser.parse_args())
''', [
    TemplateVar("name", "command function name", required=True),
    TemplateVar("docstring", "command docstring", default="todo: add docstring."),
    TemplateVar("description", "argparse description", default="a cli command"),
    TemplateVar("body", "command body", default='print("done")'),
    TemplateVar("arguments", "argparse argument definitions", default="pass"),
], category="cli")


# ============================================================
# HIGH-LEVEL API
# ============================================================

def get_template(name: str) -> Template:
    """user templates first, then built-ins."""
    try:
        return load_template(name)
    except FileNotFoundError:
        pass
    if name in BUILTIN_TEMPLATES:
        return BUILTIN_TEMPLATES[name]
    raise FileNotFoundError(f"template not found: {name}")


def render_to_file(template_name: str, context: dict, output_path: str) -> str:
    """render a template and write to disk. returns rendered content."""
    t = get_template(template_name)
    content = render(t, context)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)
    return content


def from_file(path: str) -> Template:
    """parse a template file with metadata header.

    first line: # template: name=X language=Y category=Z vars=a,b,c
    remaining lines: template content.
    """
    text = Path(path).read_text()
    lines = text.split("\n")

    if not lines or not lines[0].startswith("# template:"):
        raise ValueError("first line must be: # template: name=X ...")

    header = lines[0][len("# template:"):].strip()
    meta = {}
    for pair in header.split():
        if "=" in pair:
            k, v = pair.split("=", 1)
            meta[k] = v

    name = meta.get("name", "unnamed")
    language = meta.get("language", "python")
    category = meta.get("category", "general")

    variables = []
    for var_name in meta.get("vars", "").split(","):
        var_name = var_name.strip()
        if var_name:
            variables.append(TemplateVar(name=var_name))

    content = "\n".join(lines[1:])
    return Template(
        name=name, content=content, variables=variables,
        language=language, category=category,
    )
