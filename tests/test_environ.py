"""tests for environment detection."""

import os
import sys
from unittest.mock import patch

from keanu.abilities.world.environ import (
    detect_python, detect_virtualenv, detect_docker, detect_ci,
    detect_shell, detect_tools, detect_project_root,
    detect_environment, format_environment,
    Environment,
)


class TestDetectPython:

    def test_returns_version(self):
        version, path = detect_python()
        assert version.count(".") == 2
        assert "python" in path.lower() or "Python" in path


class TestDetectVirtualenv:

    def test_detects_venv(self):
        with patch.dict(os.environ, {"VIRTUAL_ENV": "/path/to/venv"}):
            path, vtype = detect_virtualenv()
            assert vtype == "venv"
            assert path == "/path/to/venv"

    def test_detects_conda(self):
        env = {"CONDA_DEFAULT_ENV": "myenv", "CONDA_PREFIX": "/opt/conda/envs/myenv"}
        with patch.dict(os.environ, env, clear=False):
            # clear VIRTUAL_ENV to not match first
            with patch.dict(os.environ, {"VIRTUAL_ENV": ""}, clear=False):
                path, vtype = detect_virtualenv()
                # may detect venv if sys.prefix != sys.base_prefix
                assert vtype in ("conda", "venv")

    def test_no_venv(self):
        with patch.dict(os.environ, {"VIRTUAL_ENV": "", "CONDA_DEFAULT_ENV": "",
                                      "POETRY_ACTIVE": "", "PIPENV_ACTIVE": ""}, clear=False):
            with patch.object(sys, "prefix", sys.base_prefix):
                _, vtype = detect_virtualenv()
                assert vtype == "none"


class TestDetectDocker:

    def test_not_in_docker(self):
        # We're probably not in docker during tests
        # Just verify it returns a bool
        result = detect_docker()
        assert isinstance(result, bool)


class TestDetectCI:

    def test_github_actions(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            is_ci, system = detect_ci()
            assert is_ci
            assert system == "github_actions"

    def test_gitlab(self):
        with patch.dict(os.environ, {"GITLAB_CI": "true"}):
            is_ci, system = detect_ci()
            assert is_ci
            assert system == "gitlab"

    def test_generic_ci(self):
        with patch.dict(os.environ, {"CI": "true"}):
            is_ci, system = detect_ci()
            assert is_ci

    def test_no_ci(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI",
                           "TRAVIS", "JENKINS_URL")}
        with patch.dict(os.environ, env, clear=True):
            is_ci, _ = detect_ci()
            assert not is_ci


class TestDetectShell:

    def test_returns_shell(self):
        shell = detect_shell()
        # on macOS/Linux, should return something
        if os.environ.get("SHELL"):
            assert shell  # bash, zsh, etc.


class TestDetectTools:

    def test_finds_some_tools(self):
        tools = detect_tools()
        # git should be available in most dev environments
        assert isinstance(tools, dict)
        if "git" in tools:
            assert "git" in tools["git"].lower() or "version" in tools["git"].lower()


class TestDetectProjectRoot:

    def test_finds_git(self, tmp_path):
        (tmp_path / ".git").mkdir()
        root = detect_project_root(str(tmp_path))
        assert root == str(tmp_path)

    def test_finds_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        root = detect_project_root(str(tmp_path))
        assert root == str(tmp_path)

    def test_walks_up(self, tmp_path):
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "src" / "pkg"
        sub.mkdir(parents=True)
        root = detect_project_root(str(sub))
        assert root == str(tmp_path)

    def test_fallback(self, tmp_path):
        sub = tmp_path / "nowhere"
        sub.mkdir()
        root = detect_project_root(str(sub))
        assert root  # should return something


class TestEnvironment:

    def test_to_dict(self):
        env = Environment(python_version="3.12.0", os_name="Darwin")
        d = env.to_dict()
        assert d["python_version"] == "3.12.0"
        assert d["os_name"] == "Darwin"


class TestDetectEnvironment:

    def test_returns_environment(self):
        env = detect_environment(include_tools=False)
        assert env.python_version
        assert env.os_name
        assert env.python_path

    def test_with_tools(self):
        env = detect_environment(include_tools=True)
        assert isinstance(env.tools, dict)


class TestFormatEnvironment:

    def test_format(self):
        env = Environment(
            python_version="3.12.0",
            python_path="/usr/bin/python3",
            os_name="Darwin",
            arch="arm64",
            shell="zsh",
            tools={"git": "git version 2.40"},
        )
        text = format_environment(env)
        assert "Python: 3.12.0" in text
        assert "Darwin" in text
        assert "git" in text
