"""tests for first-run experience."""

import os
from unittest.mock import patch

from keanu.abilities.world.firstrun import (
    check_python_version, check_anthropic_key, check_ollama,
    check_chromadb, check_rich, check_keanu_home, check_llm_available,
    check_setup, is_first_run, mark_setup_done, run_setup_wizard,
    format_status, get_quickstart, SetupStatus, Dependency,
)


class TestDependencyChecks:

    def test_python_version(self):
        dep = check_python_version()
        assert dep.available  # we're running 3.10+
        assert dep.required
        assert "Python" in dep.message

    def test_anthropic_key_present(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-1234567890"}):
            dep = check_anthropic_key()
            assert dep.available
            assert dep.message == "found"

    def test_anthropic_key_missing(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            dep = check_anthropic_key()
            assert not dep.available

    def test_ollama_not_installed(self):
        with patch("shutil.which", return_value=None):
            dep = check_ollama()
            assert not dep.available
            assert "not installed" in dep.message

    def test_chromadb_available(self):
        dep = check_chromadb()
        # chromadb may or may not be installed, just check structure
        assert dep.name == "chromadb"
        assert not dep.required

    def test_rich_available(self):
        dep = check_rich()
        assert dep.name == "rich"
        # rich is likely installed in dev
        assert isinstance(dep.available, bool)

    def test_keanu_home(self, tmp_path):
        with patch("keanu.abilities.world.firstrun.keanu_home", return_value=tmp_path / "keanu"):
            dep = check_keanu_home()
            assert dep.available
            assert dep.required

    def test_llm_with_api_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-1234567890"}):
            dep = check_llm_available()
            assert dep.available

    def test_llm_nothing(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            with patch("shutil.which", return_value=None):
                dep = check_llm_available()
                assert not dep.available


class TestSetupStatus:

    def test_all_required_met(self):
        status = SetupStatus(
            dependencies=[
                Dependency("python", True, True, "ok"),
                Dependency("home", True, True, "ok"),
            ],
            ready=True,
        )
        assert len(status.missing_required) == 0
        assert status.ready

    def test_missing_required(self):
        status = SetupStatus(
            dependencies=[
                Dependency("python", False, True, "bad"),
            ],
        )
        assert len(status.missing_required) == 1
        assert not status.ready

    def test_missing_optional(self):
        status = SetupStatus(
            dependencies=[
                Dependency("chromadb", False, False, "not installed"),
            ],
            ready=True,
        )
        assert len(status.missing_optional) == 1
        assert status.ready


class TestCheckSetup:

    def test_returns_status(self, tmp_path):
        with patch("keanu.abilities.world.firstrun.keanu_home", return_value=tmp_path / "keanu"):
            with patch("keanu.abilities.world.firstrun._SETUP_DONE_FILE", tmp_path / ".done"):
                status = check_setup()
                assert isinstance(status, SetupStatus)
                assert len(status.dependencies) >= 5


class TestFirstRun:

    def test_is_first_run(self, tmp_path):
        with patch("keanu.abilities.world.firstrun._SETUP_DONE_FILE", tmp_path / ".done"):
            assert is_first_run()

    def test_not_first_run(self, tmp_path):
        done_file = tmp_path / ".done"
        done_file.write_text("done\n")
        with patch("keanu.abilities.world.firstrun._SETUP_DONE_FILE", done_file):
            assert not is_first_run()

    def test_mark_setup_done(self, tmp_path):
        done_file = tmp_path / ".done"
        with patch("keanu.abilities.world.firstrun._SETUP_DONE_FILE", done_file):
            mark_setup_done()
            assert done_file.exists()


class TestSetupWizard:

    def test_wizard_marks_done(self, tmp_path):
        done_file = tmp_path / ".done"
        with patch("keanu.abilities.world.firstrun._SETUP_DONE_FILE", done_file):
            with patch("keanu.abilities.world.firstrun.keanu_home", return_value=tmp_path / "keanu"):
                status = run_setup_wizard()
                if status.ready:
                    assert done_file.exists()


class TestFormatting:

    def test_format_status(self):
        status = SetupStatus(
            dependencies=[
                Dependency("python", True, True, "Python 3.12"),
                Dependency("chromadb", False, False, "not installed", "pip install chromadb"),
            ],
            ready=True,
        )
        text = format_status(status)
        assert "python" in text
        assert "chromadb" in text
        assert "pip install chromadb" in text

    def test_format_not_ready(self):
        status = SetupStatus(
            dependencies=[
                Dependency("python", False, True, "too old"),
            ],
            ready=False,
        )
        text = format_status(status)
        assert "missing required" in text

    def test_quickstart(self, tmp_path):
        with patch("keanu.abilities.world.firstrun.keanu_home", return_value=tmp_path / "keanu"):
            with patch("keanu.abilities.world.firstrun._SETUP_DONE_FILE", tmp_path / ".done"):
                text = get_quickstart()
                assert "keanu" in text
