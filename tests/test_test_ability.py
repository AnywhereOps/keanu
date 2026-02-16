"""Tests for the test runner ability."""

import subprocess
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from keanu.abilities.hands.test import (
    TestAbility, _run_pytest, _parse_failures, _parse_summary,
    _op_run, _op_discover, _op_targeted, _op_coverage,
)


# ============================================================
# REGISTRATION
# ============================================================

class TestTestRegistration:

    def test_registered(self):
        from keanu.abilities import _REGISTRY
        assert "test" in _REGISTRY

    def test_can_handle_returns_false(self):
        ab = TestAbility()
        can, conf = ab.can_handle("run tests")
        assert can is False

    def test_has_cast_line(self):
        ab = TestAbility()
        assert ab.cast_line.endswith("...")


# ============================================================
# _run_pytest helper
# ============================================================

class TestRunPytest:

    @patch("keanu.abilities.hands.test.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="5 passed", stderr=""
        )
        rc, stdout, stderr = _run_pytest("-v")
        assert rc == 0
        assert "5 passed" in stdout

    @patch("keanu.abilities.hands.test.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="FAILED tests/test_foo.py::test_bar", stderr=""
        )
        rc, stdout, stderr = _run_pytest()
        assert rc == 1

    @patch("keanu.abilities.hands.test.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=120)
        rc, stdout, stderr = _run_pytest()
        assert rc == -1
        assert "timed out" in stderr

    @patch("keanu.abilities.hands.test.subprocess.run")
    def test_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        rc, stdout, stderr = _run_pytest()
        assert rc == -1
        assert "not found" in stderr


# ============================================================
# PARSERS
# ============================================================

class TestParsers:

    def test_parse_failures_from_output(self):
        output = """
FAILED tests/test_foo.py::test_bar - AssertionError: expected 1, got 2
FAILED tests/test_baz.py::test_qux - TypeError: wrong type
"""
        failures = _parse_failures(output, "")
        assert len(failures) == 2
        assert failures[0]["file"] == "tests/test_foo.py"
        assert failures[0]["test"] == "test_bar"
        assert "AssertionError" in failures[0]["error"]
        assert failures[1]["test"] == "test_qux"

    def test_parse_failures_with_errors(self):
        output = "ERROR tests/test_foo.py::test_bar - ImportError: no module"
        failures = _parse_failures(output, "")
        assert len(failures) == 1
        assert failures[0]["error"] == "ImportError: no module"

    def test_parse_failures_empty(self):
        failures = _parse_failures("5 passed in 1.23s", "")
        assert failures == []

    def test_parse_summary(self):
        output = "========= 5 passed, 2 failed in 3.45s ========="
        summary = _parse_summary(output)
        assert "5 passed" in summary
        assert "2 failed" in summary

    def test_parse_summary_empty(self):
        assert _parse_summary("no summary here") == ""


# ============================================================
# RUN
# ============================================================

class TestOpRun:

    @patch("keanu.abilities.hands.test._run_pytest")
    def test_success(self, mock_run):
        mock_run.return_value = (0, "5 passed\n========= 5 passed in 1.0s =========", "")
        result = _op_run({})
        assert result["success"] is True
        assert result["data"]["failure_count"] == 0

    @patch("keanu.abilities.hands.test._run_pytest")
    def test_with_failures(self, mock_run):
        mock_run.return_value = (
            1,
            "FAILED tests/test_foo.py::test_bar - assert 1 == 2\n========= 1 failed =========",
            "",
        )
        result = _op_run({})
        assert result["success"] is False
        assert result["data"]["failure_count"] == 1
        assert result["data"]["failures"][0]["test"] == "test_bar"

    @patch("keanu.abilities.hands.test._run_pytest")
    def test_with_target(self, mock_run):
        mock_run.return_value = (0, "1 passed", "")
        _op_run({"target": "tests/test_foo.py"})
        args = mock_run.call_args[0]
        assert "tests/test_foo.py" in args

    @patch("keanu.abilities.hands.test._run_pytest")
    def test_truncates_long_output(self, mock_run):
        mock_run.return_value = (0, "x" * 10000, "")
        result = _op_run({})
        assert "truncated" in result["result"]


# ============================================================
# DISCOVER
# ============================================================

class TestOpDiscover:

    @patch("keanu.abilities.hands.test._run_pytest")
    def test_discover(self, mock_run):
        mock_run.return_value = (
            0,
            "tests/test_foo.py::test_bar\ntests/test_foo.py::test_baz\n\n2 tests collected",
            "",
        )
        result = _op_discover({})
        assert result["success"] is True
        assert result["data"]["count"] == 2

    @patch("keanu.abilities.hands.test._run_pytest")
    def test_discover_empty(self, mock_run):
        mock_run.return_value = (0, "", "")
        result = _op_discover({})
        assert "no tests found" in result["result"]


# ============================================================
# TARGETED
# ============================================================

class TestOpTargeted:

    def test_no_files(self):
        result = _op_targeted({})
        assert result["success"] is False

    @patch("keanu.abilities.hands.test._op_run")
    def test_test_file_runs_directly(self, mock_run, tmp_path):
        mock_run.return_value = {"success": True, "result": "ok", "data": {}}
        # create the test file so Path.exists() works
        test_file = tmp_path / "test_foo.py"
        test_file.write_text("def test_x(): pass")
        _op_targeted({"files": [str(test_file)]})
        called_ctx = mock_run.call_args[0][0]
        assert str(test_file) in called_ctx["target"]


# ============================================================
# COVERAGE
# ============================================================

class TestOpCoverage:

    @patch("keanu.abilities.hands.test._run_pytest")
    def test_coverage(self, mock_run):
        mock_run.return_value = (0, "TOTAL 85%\n========= 5 passed =========", "")
        result = _op_coverage({})
        assert result["success"] is True
        assert "85%" in result["result"]


# ============================================================
# EXECUTE DISPATCH
# ============================================================

class TestTestExecute:

    @patch("keanu.abilities.hands.test._run_pytest")
    def test_dispatches_run(self, mock_run):
        mock_run.return_value = (0, "5 passed\n========= 5 passed =========", "")
        ab = TestAbility()
        result = ab.execute("", {"op": "run"})
        assert result["success"] is True

    def test_unknown_op(self):
        ab = TestAbility()
        result = ab.execute("", {"op": "benchmark"})
        assert result["success"] is False
        assert "Unknown test op" in result["result"]

    @patch("keanu.abilities.hands.test._run_pytest")
    def test_default_op_is_run(self, mock_run):
        mock_run.return_value = (0, "5 passed", "")
        ab = TestAbility()
        result = ab.execute("", {})
        assert result["success"] is True
