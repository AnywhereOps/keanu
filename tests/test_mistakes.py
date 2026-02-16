"""Tests for the mistake memory system."""

import time
import pytest
from pathlib import Path

from keanu.infra.mistakes import (
    log_mistake, check_before, get_patterns, get_mistakes,
    clear_stale, stats, _classify, _summarize_args, _args_overlap,
    DECAY_DAYS,
)


@pytest.fixture(autouse=True)
def isolated_mistakes(tmp_path, monkeypatch):
    """point mistakes to a temp file for every test."""
    fake_file = tmp_path / "mistakes.jsonl"
    monkeypatch.setattr("keanu.infra.mistakes.MISTAKES_FILE", fake_file)
    return fake_file


class TestLogMistake:

    def test_basic_log(self):
        log_mistake("edit", {"file_path": "foo.py"}, "old_string not found")
        mistakes = get_mistakes()
        assert len(mistakes) == 1
        assert mistakes[0]["action"] == "edit"
        assert "not found" in mistakes[0]["error"]

    def test_auto_classifies(self):
        log_mistake("edit", {}, "old_string not found in foo.py")
        m = get_mistakes()[0]
        assert m["category"] == "stale_reference"

    def test_manual_category(self):
        log_mistake("run", {}, "boom", category="custom")
        m = get_mistakes()[0]
        assert m["category"] == "custom"

    def test_truncates_long_errors(self):
        log_mistake("run", {}, "x" * 1000)
        m = get_mistakes()[0]
        assert len(m["error"]) <= 500

    def test_multiple_logs(self):
        log_mistake("edit", {}, "error 1")
        log_mistake("run", {}, "error 2")
        log_mistake("write", {}, "error 3")
        assert len(get_mistakes()) == 3


class TestCheckBefore:

    def test_finds_similar_mistake(self):
        log_mistake("edit", {"file_path": "foo.py"}, "not unique")
        warnings = check_before("edit", {"file_path": "foo.py"})
        assert len(warnings) == 1

    def test_ignores_different_action(self):
        log_mistake("run", {"command": "pytest"}, "timeout")
        warnings = check_before("edit", {"file_path": "foo.py"})
        assert len(warnings) == 0

    def test_returns_multiple(self):
        log_mistake("edit", {"file_path": "a.py"}, "error 1")
        log_mistake("edit", {"file_path": "a.py"}, "error 2")
        warnings = check_before("edit", {"file_path": "a.py"})
        assert len(warnings) == 2

    def test_max_five_results(self):
        for i in range(10):
            log_mistake("edit", {"file_path": "x.py"}, f"error {i}")
        warnings = check_before("edit", {"file_path": "x.py"})
        assert len(warnings) == 5


class TestGetPatterns:

    def test_empty(self):
        assert get_patterns() == []

    def test_groups_by_action_category(self):
        log_mistake("edit", {}, "old_string not found in x.py")
        log_mistake("edit", {}, "old_string not found in y.py")
        log_mistake("edit", {}, "old_string not found in z.py")
        patterns = get_patterns()
        assert len(patterns) >= 1
        top = patterns[0]
        assert top["action"] == "edit"
        assert top["count"] == 3
        assert top["forgeable"] is True

    def test_not_forgeable_under_three(self):
        log_mistake("run", {}, "timeout")
        log_mistake("run", {}, "timeout again")
        patterns = get_patterns()
        assert len(patterns) >= 1
        assert patterns[0]["forgeable"] is False


class TestClassify:

    def test_path_error(self):
        assert _classify("read", "No such file or directory") == "path"

    def test_timeout(self):
        assert _classify("run", "Command timed out (60s)") == "timeout"

    def test_ambiguous_edit(self):
        assert _classify("edit", "found 2 times (must be unique)") == "ambiguous_edit"

    def test_stale_reference(self):
        assert _classify("edit", "old_string not found in foo.py") == "stale_reference"

    def test_import_error(self):
        assert _classify("run", "ModuleNotFoundError: No module named 'foo'") == "import"

    def test_safety(self):
        assert _classify("run", "Command blocked: sudo rm -rf /") == "safety"

    def test_syntax(self):
        assert _classify("run", "SyntaxError: invalid syntax") == "syntax"

    def test_unknown(self):
        assert _classify("run", "something weird happened") == "unknown"


class TestClearStale:

    def test_clears_old_mistakes(self, isolated_mistakes, monkeypatch):
        # write a stale mistake manually
        from keanu.io import append_jsonl
        old_ts = int(time.time()) - (DECAY_DAYS + 1) * 86400
        append_jsonl(isolated_mistakes, {
            "ts": old_ts, "action": "edit", "args_summary": "",
            "error": "old", "context": "", "category": "unknown",
        })
        # write a fresh one
        log_mistake("edit", {}, "new")

        removed = clear_stale()
        assert removed == 1
        assert len(get_mistakes()) == 1
        assert get_mistakes()[0]["error"] == "new"


class TestStats:

    def test_empty_stats(self):
        s = stats()
        assert s["total"] == 0
        assert s["active"] == 0

    def test_populated_stats(self):
        log_mistake("edit", {}, "not found in x.py")
        log_mistake("edit", {}, "not found in y.py")
        log_mistake("edit", {}, "not found in z.py")
        log_mistake("run", {}, "timeout")
        s = stats()
        assert s["total"] == 4
        assert s["active"] == 4
        assert "edit" in s["by_action"]
        assert s["by_action"]["edit"] == 3
        assert s["patterns_forgeable"] >= 1


class TestHelpers:

    def test_summarize_args(self):
        s = _summarize_args({"file_path": "foo.py", "old_string": "hello"})
        assert "file_path=foo.py" in s
        assert "old_string=hello" in s

    def test_summarize_empty(self):
        assert _summarize_args({}) == ""

    def test_args_overlap_true(self):
        a = _summarize_args({"file_path": "foo.py"})
        b = _summarize_args({"file_path": "foo.py"})
        assert _args_overlap(a, b) is True

    def test_args_overlap_false(self):
        a = _summarize_args({"file_path": "foo.py"})
        b = _summarize_args({"command": "pytest"})
        assert _args_overlap(a, b) is False

    def test_args_overlap_empty(self):
        assert _args_overlap("", "something") is False
