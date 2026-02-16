"""tests for CI monitoring."""

from unittest.mock import patch

from keanu.data.ci import (
    run_tests, detect_flaky, log_run, get_history, health_summary,
    _parse_pytest_output, TestRun, FlakyTest,
)


class TestParseOutput:

    def test_all_passed(self):
        output = "100 passed in 5.23s"
        run = _parse_pytest_output(output)
        assert run.passed == 100
        assert run.failed == 0
        assert run.green

    def test_some_failed(self):
        output = "95 passed, 5 failed in 6.00s"
        run = _parse_pytest_output(output)
        assert run.passed == 95
        assert run.failed == 5
        assert not run.green

    def test_with_errors(self):
        output = "90 passed, 3 failed, 2 error in 4.50s"
        run = _parse_pytest_output(output)
        assert run.passed == 90
        assert run.failed == 3
        assert run.errors == 2

    def test_with_skipped(self):
        output = "100 passed, 5 skipped in 3.00s"
        run = _parse_pytest_output(output)
        assert run.passed == 100
        assert run.skipped == 5

    def test_extracts_failures(self):
        output = "FAILED tests/test_foo.py::test_bar\n3 passed, 1 failed in 1.00s"
        run = _parse_pytest_output(output)
        assert len(run.failures) >= 1
        assert "test_bar" in run.failures[0]["test"]

    def test_extracts_error_messages(self):
        output = "tests/test_foo.py::test_bar - AssertionError: 1 != 2\n1 failed in 0.50s"
        run = _parse_pytest_output(output)
        assert len(run.failures) >= 1
        assert "AssertionError" in run.failures[0]["error"]


class TestTestRun:

    def test_total(self):
        r = TestRun(timestamp=0, passed=10, failed=2, errors=1)
        assert r.total == 13

    def test_success_rate(self):
        r = TestRun(timestamp=0, passed=9, failed=1)
        assert r.success_rate == 0.9

    def test_green(self):
        r = TestRun(timestamp=0, passed=10, failed=0, errors=0)
        assert r.green

    def test_not_green(self):
        r = TestRun(timestamp=0, passed=10, failed=1)
        assert not r.green


class TestFlakyTest:

    def test_flakiness(self):
        ft = FlakyTest(name="test_x", pass_count=7, fail_count=3)
        assert abs(ft.flakiness - 0.3) < 0.01

    def test_not_flaky(self):
        ft = FlakyTest(name="test_x", pass_count=10, fail_count=0)
        assert ft.flakiness == 0.0

    def test_always_fails(self):
        ft = FlakyTest(name="test_x", pass_count=0, fail_count=10)
        assert ft.flakiness == 0.0


class TestDetectFlaky:

    def test_detects_intermittent(self):
        runs = [
            TestRun(timestamp=1, passed=10, failed=1,
                    failures=[{"test": "test_x", "error": ""}]),
            TestRun(timestamp=2, passed=11, failed=0, failures=[]),
            TestRun(timestamp=3, passed=10, failed=1,
                    failures=[{"test": "test_x", "error": ""}]),
        ]
        flaky = detect_flaky(runs)
        assert len(flaky) == 1
        assert flaky[0].name == "test_x"
        assert flaky[0].fail_count == 2
        assert flaky[0].pass_count == 1

    def test_no_flaky(self):
        runs = [
            TestRun(timestamp=1, passed=10, failed=0, failures=[]),
            TestRun(timestamp=2, passed=10, failed=0, failures=[]),
        ]
        flaky = detect_flaky(runs)
        assert flaky == []


class TestCILog:

    def test_log_and_read(self, tmp_path):
        log_file = tmp_path / "ci_log.jsonl"
        with patch("keanu.data.ci._CI_LOG", log_file):
            run = TestRun(timestamp=1.0, passed=10, failed=0, commit="abc")
            log_run(run)
            history = get_history()
        assert len(history) == 1
        assert history[0]["passed"] == 10
        assert history[0]["commit"] == "abc"

    def test_empty_history(self, tmp_path):
        log_file = tmp_path / "ci_log.jsonl"
        with patch("keanu.data.ci._CI_LOG", log_file):
            history = get_history()
        assert history == []


class TestHealthSummary:

    def test_all_green(self):
        history = [
            {"passed": 10, "failed": 0, "errors": 0, "duration_s": 5.0, "failure_names": []},
            {"passed": 10, "failed": 0, "errors": 0, "duration_s": 5.0, "failure_names": []},
        ]
        summary = health_summary(history)
        assert summary["status"] == "green"
        assert summary["success_rate"] == 1.0

    def test_some_red(self):
        history = [
            {"passed": 10, "failed": 0, "errors": 0, "duration_s": 5.0, "failure_names": []},
            {"passed": 9, "failed": 1, "errors": 0, "duration_s": 5.0, "failure_names": ["test_x"]},
        ]
        summary = health_summary(history)
        assert summary["status"] == "yellow"

    def test_all_red(self):
        history = [
            {"passed": 9, "failed": 1, "errors": 0, "duration_s": 5.0, "failure_names": ["test_x"]},
        ]
        summary = health_summary(history)
        assert summary["status"] == "red"

    def test_empty_history(self):
        summary = health_summary([])
        assert summary["status"] == "no data"

    def test_top_failures(self):
        history = [
            {"passed": 9, "failed": 1, "errors": 0, "duration_s": 5.0, "failure_names": ["test_x"]},
            {"passed": 9, "failed": 1, "errors": 0, "duration_s": 5.0, "failure_names": ["test_x"]},
            {"passed": 9, "failed": 1, "errors": 0, "duration_s": 5.0, "failure_names": ["test_y"]},
        ]
        summary = health_summary(history)
        assert summary["top_failures"][0]["test"] == "test_x"
        assert summary["top_failures"][0]["count"] == 2
