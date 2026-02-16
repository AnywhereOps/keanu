"""tests for the self-correction loop."""

from keanu.hero.autocorrect import (
    check_after_edit, CorrectionPlan, CorrectionResult,
    _suggest_fix, should_correct, summarize,
)


class TestCorrectionPlan:

    def test_defaults(self):
        p = CorrectionPlan()
        assert p.lint
        assert p.test
        assert not p.typecheck
        assert p.max_attempts == 3


class TestCorrectionResult:

    def test_defaults(self):
        r = CorrectionResult(phase="lint", passed=True)
        assert r.attempts == 0
        assert r.errors == []


class TestSuggestFix:

    def test_unused_import(self):
        fix = _suggest_fix("lint", "F401 unused import os", [])
        assert fix is not None
        assert "import" in fix

    def test_line_too_long(self):
        fix = _suggest_fix("lint", "E501 line too long (120 > 88)", [])
        assert fix is not None

    def test_import_error(self):
        fix = _suggest_fix("test", "ImportError: cannot import name foo", [])
        assert fix is not None
        assert "import" in fix

    def test_type_error(self):
        fix = _suggest_fix("test", "TypeError: expected str got int", [])
        assert fix is not None

    def test_no_suggestion(self):
        fix = _suggest_fix("lint", "some unknown error", [])
        assert fix is None


class TestShouldCorrect:

    def test_after_write(self):
        assert should_correct("write", {"success": True})

    def test_after_edit(self):
        assert should_correct("edit", {"success": True})

    def test_not_after_read(self):
        assert not should_correct("read", {"success": True})

    def test_not_after_failed_edit(self):
        assert not should_correct("edit", {"success": False})


class TestCheckAfterEdit:

    def _make_executor(self, results):
        """create an executor that returns preset results."""
        call_count = {"lint": 0, "test": 0, "typecheck": 0}

        def executor(phase, plan):
            idx = call_count.get(phase, 0)
            call_count[phase] = idx + 1
            phase_results = results.get(phase, [{"success": True}])
            return phase_results[min(idx, len(phase_results) - 1)]

        return executor

    def test_all_pass(self):
        executor = self._make_executor({
            "lint": [{"success": True, "result": "clean"}],
            "test": [{"success": True, "result": "all passed"}],
        })
        results = check_after_edit(["foo.py"], executor=executor)
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_lint_fails_then_passes(self):
        executor = self._make_executor({
            "lint": [
                {"success": False, "error": "F401 unused import os"},
                {"success": True, "result": "clean"},
            ],
            "test": [{"success": True}],
        })
        results = check_after_edit(["foo.py"], executor=executor)
        lint_result = results[0]
        assert lint_result.passed
        assert lint_result.attempts == 2

    def test_test_fails_all_attempts(self):
        executor = self._make_executor({
            "lint": [{"success": True}],
            "test": [
                {"success": False, "error": "AssertionError"},
                {"success": False, "error": "AssertionError"},
                {"success": False, "error": "AssertionError"},
            ],
        })
        results = check_after_edit(["foo.py"], executor=executor)
        test_result = results[1]
        assert not test_result.passed
        assert test_result.attempts == 3

    def test_skip_typecheck_by_default(self):
        executor = self._make_executor({
            "lint": [{"success": True}],
            "test": [{"success": True}],
        })
        results = check_after_edit(["foo.py"], executor=executor)
        phases = [r.phase for r in results]
        assert "typecheck" not in phases

    def test_include_typecheck(self):
        executor = self._make_executor({
            "lint": [{"success": True}],
            "test": [{"success": True}],
            "typecheck": [{"success": True}],
        })
        plan = CorrectionPlan(typecheck=True)
        results = check_after_edit(["foo.py"], plan=plan, executor=executor)
        phases = [r.phase for r in results]
        assert "typecheck" in phases

    def test_custom_max_attempts(self):
        executor = self._make_executor({
            "lint": [{"success": False, "error": "fail"}] * 5,
            "test": [{"success": True}],
        })
        plan = CorrectionPlan(max_attempts=5)
        results = check_after_edit(["foo.py"], plan=plan, executor=executor)
        assert results[0].attempts == 5


class TestSummarize:

    def test_all_pass(self):
        results = [
            CorrectionResult(phase="lint", passed=True, attempts=1),
            CorrectionResult(phase="test", passed=True, attempts=1),
        ]
        s = summarize(results)
        assert "lint: ok" in s
        assert "test: ok" in s

    def test_with_failure(self):
        results = [
            CorrectionResult(phase="lint", passed=True, attempts=1),
            CorrectionResult(phase="test", passed=False, attempts=3),
        ]
        s = summarize(results)
        assert "test: failed" in s
        assert "3 attempts" in s

    def test_empty(self):
        assert summarize([]) == "no checks run"
