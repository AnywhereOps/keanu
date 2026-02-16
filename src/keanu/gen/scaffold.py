"""scaffold.py - project scaffolding templates.

generate common project structures: Python package, CLI tool,
web API, library. each template creates the right files with
the right structure.

in the world: the blueprint. you describe what you want to build,
and the foundation appears.
"""

import re
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScaffoldFile:
    """a file to create during scaffolding."""
    path: str
    content: str
    executable: bool = False


@dataclass
class ScaffoldResult:
    """result of a scaffold operation."""
    files_created: list[str] = field(default_factory=list)
    directories_created: list[str] = field(default_factory=list)
    template: str = ""
    name: str = ""


# ============================================================
# TEMPLATES
# ============================================================

def python_package(name: str, description: str = "",
                   author: str = "") -> list[ScaffoldFile]:
    """generate a Python package scaffold."""
    safe_name = re.sub(r'[^a-z0-9_]', '_', name.lower())

    files = [
        ScaffoldFile(
            path="pyproject.toml",
            content=f"""[project]
name = "{name}"
version = "0.1.0"
description = "{description or name}"
requires-python = ">=3.10"
{f'authors = [{{name = "{author}"}}]' if author else ''}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"
""",
        ),
        ScaffoldFile(
            path=f"src/{safe_name}/__init__.py",
            content=f'"""{safe_name}: {description or name}."""\n\n__version__ = "0.1.0"\n',
        ),
        ScaffoldFile(
            path=f"src/{safe_name}/main.py",
            content=f'"""{safe_name} main module."""\n\n\ndef main():\n    print("{name} running")\n',
        ),
        ScaffoldFile(
            path="tests/__init__.py",
            content="",
        ),
        ScaffoldFile(
            path=f"tests/test_{safe_name}.py",
            content=f'"""tests for {safe_name}."""\n\n\ndef test_import():\n    import {safe_name}\n    assert {safe_name}.__version__\n',
        ),
        ScaffoldFile(
            path=".gitignore",
            content="__pycache__/\n*.pyc\n*.egg-info/\ndist/\nbuild/\n.venv/\n.env\n",
        ),
        ScaffoldFile(
            path="README.md",
            content=f"# {name}\n\n{description or ''}\n",
        ),
    ]

    return files


def cli_tool(name: str, description: str = "",
             author: str = "") -> list[ScaffoldFile]:
    """generate a CLI tool scaffold."""
    safe_name = re.sub(r'[^a-z0-9_]', '_', name.lower())

    files = python_package(name, description, author)

    # override main.py with CLI entry point
    for f in files:
        if f.path.endswith("main.py"):
            f.content = f'''"""{safe_name} CLI."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="{name}",
        description="{description or name}",
    )
    parser.add_argument("command", nargs="?", default="help")
    args = parser.parse_args()

    if args.command == "help":
        parser.print_help()
    else:
        print(f"{{args.command}}: not implemented yet")


if __name__ == "__main__":
    main()
'''

    # add pyproject scripts entry
    for f in files:
        if f.path == "pyproject.toml":
            f.content = f.content.rstrip() + f"""

[project.scripts]
{name} = "{safe_name}.main:main"
"""

    return files


def web_api(name: str, description: str = "",
            framework: str = "flask") -> list[ScaffoldFile]:
    """generate a web API scaffold."""
    safe_name = re.sub(r'[^a-z0-9_]', '_', name.lower())

    files = python_package(name, description)

    # add framework-specific app file
    if framework == "flask":
        app_content = f'''"""{safe_name} web API."""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({{"status": "ok", "service": "{name}"}})


@app.route("/")
def index():
    return jsonify({{"message": "welcome to {name}"}})


def create_app():
    return app


if __name__ == "__main__":
    app.run(debug=True)
'''
    elif framework == "fastapi":
        app_content = f'''"""{safe_name} web API."""

from fastapi import FastAPI

app = FastAPI(title="{name}", description="{description or name}")


@app.get("/health")
async def health():
    return {{"status": "ok", "service": "{name}"}}


@app.get("/")
async def index():
    return {{"message": "welcome to {name}"}}
'''
    else:
        app_content = f'"""{safe_name} web API."""\n\n# add your framework here\n'

    for f in files:
        if f.path.endswith("main.py"):
            f.content = app_content

    # add Dockerfile
    files.append(ScaffoldFile(
        path="Dockerfile",
        content=f"""FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8000
CMD ["python", "-m", "{safe_name}.main"]
""",
    ))

    return files


def library(name: str, description: str = "",
            author: str = "") -> list[ScaffoldFile]:
    """generate a library scaffold with docs structure."""
    safe_name = re.sub(r'[^a-z0-9_]', '_', name.lower())

    files = python_package(name, description, author)

    # add docs
    files.append(ScaffoldFile(
        path="docs/index.md",
        content=f"# {name}\n\n{description or ''}\n\n## Installation\n\n```\npip install {name}\n```\n",
    ))

    # add LICENSE
    files.append(ScaffoldFile(
        path="LICENSE",
        content=f"MIT License\n\nCopyright (c) {time.strftime('%Y')} {author or name}\n",
    ))

    # add CHANGELOG
    files.append(ScaffoldFile(
        path="CHANGELOG.md",
        content=f"# Changelog\n\n## 0.1.0\n\n- Initial release\n",
    ))

    return files


# ============================================================
# SCAFFOLD ENGINE
# ============================================================

TEMPLATES = {
    "package": python_package,
    "cli": cli_tool,
    "api": web_api,
    "library": library,
}


def list_templates() -> list[dict]:
    """list available scaffold templates."""
    return [
        {"name": "package", "description": "Python package with tests"},
        {"name": "cli", "description": "CLI tool with argparse entry point"},
        {"name": "api", "description": "Web API (Flask or FastAPI)"},
        {"name": "library", "description": "Library with docs and changelog"},
    ]


def scaffold(template: str, name: str, output_dir: str = ".",
             description: str = "", author: str = "",
             dry_run: bool = False, **kwargs) -> ScaffoldResult:
    """run a scaffold template and create files."""
    if template not in TEMPLATES:
        raise ValueError(f"unknown template: {template}. available: {', '.join(TEMPLATES)}")

    func = TEMPLATES[template]
    files = func(name, description=description, author=author, **kwargs)

    result = ScaffoldResult(template=template, name=name)
    root = Path(output_dir)

    for sf in files:
        path = root / sf.path
        if dry_run:
            result.files_created.append(str(path))
            continue

        # create parent directories
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            result.directories_created.append(str(path.parent))

        path.write_text(sf.content)
        result.files_created.append(str(path))

        if sf.executable:
            path.chmod(path.stat().st_mode | 0o111)

    return result
