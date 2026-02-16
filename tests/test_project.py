"""Tests for the project model detector."""

import json
import pytest
from pathlib import Path

from keanu.analysis.project import detect, ProjectModel, _detect_ci


class TestPythonProject:

    def test_detects_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "myapp"\nversion = "1.0.0"\n'
        )
        model = detect(str(tmp_path))
        assert model.kind == "python"
        assert model.name == "myapp"
        assert model.version == "1.0.0"

    def test_test_command_pytest(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        model = detect(str(tmp_path))
        assert "pytest" in model.test_command

    def test_test_command_makefile(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "Makefile").write_text("test:\n\tpytest\n")
        model = detect(str(tmp_path))
        assert model.test_command == "make test"

    def test_test_command_tox(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "tox.ini").write_text("[tox]\n")
        model = detect(str(tmp_path))
        assert model.test_command == "tox"

    def test_detects_ruff(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\n\n'
            '[dependency-groups]\ndev = [\n"ruff>=0.1",\n]\n'
        )
        model = detect(str(tmp_path))
        assert "ruff" in model.lint_command
        assert "ruff" in model.format_command

    def test_detects_entry_points(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        src = tmp_path / "src" / "myapp"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "cli.py").write_text("def main(): pass\n")
        model = detect(str(tmp_path))
        assert any("cli.py" in e for e in model.entry_points)

    def test_setup_py_fallback(self, tmp_path):
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")
        model = detect(str(tmp_path))
        assert model.kind == "python"

    def test_summary(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
        model = detect(str(tmp_path))
        s = model.summary()
        assert "myapp" in s
        assert "python" in s


class TestNodeProject:

    def test_detects_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "name": "my-app",
            "version": "2.0.0",
            "scripts": {"test": "jest", "build": "tsc"},
            "dependencies": {"express": "^4.0"},
            "devDependencies": {"jest": "^29.0"},
        }))
        model = detect(str(tmp_path))
        assert model.kind == "node"
        assert model.name == "my-app"
        assert model.version == "2.0.0"
        assert model.test_command == "npm test"
        assert model.build_command == "npm run build"
        assert "express" in model.dependencies
        assert "jest" in model.dev_dependencies

    def test_detects_entry_point(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "name": "x", "main": "index.js",
        }))
        model = detect(str(tmp_path))
        assert "index.js" in model.entry_points

    def test_bin_entry_points(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "name": "x", "bin": {"cli": "./bin/cli.js"},
        }))
        model = detect(str(tmp_path))
        assert "./bin/cli.js" in model.entry_points


class TestGoProject:

    def test_detects_go_mod(self, tmp_path):
        (tmp_path / "go.mod").write_text("module github.com/foo/bar\n\ngo 1.21\n")
        model = detect(str(tmp_path))
        assert model.kind == "go"
        assert model.name == "github.com/foo/bar"
        assert model.test_command == "go test ./..."

    def test_detects_main_go(self, tmp_path):
        (tmp_path / "go.mod").write_text("module foo\n")
        (tmp_path / "main.go").write_text("package main\n")
        model = detect(str(tmp_path))
        assert "main.go" in model.entry_points


class TestRustProject:

    def test_detects_cargo_toml(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "mylib"\nversion = "0.1.0"\n'
        )
        model = detect(str(tmp_path))
        assert model.kind == "rust"
        assert model.name == "mylib"
        assert model.test_command == "cargo test"

    def test_detects_main_rs(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "x"\n')
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.rs").write_text("fn main() {}\n")
        model = detect(str(tmp_path))
        assert "src/main.rs" in model.entry_points


class TestUnknown:

    def test_unknown_project(self, tmp_path):
        model = detect(str(tmp_path))
        assert model.kind == "unknown"


class TestCI:

    def test_detects_makefile(self, tmp_path):
        (tmp_path / "Makefile").write_text("all:\n\techo hi\n")
        ci = _detect_ci(tmp_path)
        assert "Makefile" in ci

    def test_detects_dockerfile(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
        ci = _detect_ci(tmp_path)
        assert "Dockerfile" in ci

    def test_detects_github_actions(self, tmp_path):
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text("on: push\n")
        ci = _detect_ci(tmp_path)
        assert any("ci.yml" in c for c in ci)


class TestKeanuProject:
    """test against the actual keanu project."""

    def test_detects_keanu(self):
        model = detect(".")
        assert model.kind == "python"
        assert model.name == "keanu"
        assert model.test_command  # has a test command (tox, pytest, or make test)
        assert len(model.entry_points) > 0
