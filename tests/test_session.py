"""tests for session working memory."""

from keanu.abilities.world.session import Session, Decision, Attempt


class TestDecision:

    def test_auto_timestamp(self):
        d = Decision(what="use dataclass", why="simpler")
        assert d.timestamp != ""

    def test_explicit_timestamp(self):
        d = Decision(what="x", why="y", timestamp="2025-01-01")
        assert d.timestamp == "2025-01-01"


class TestAttempt:

    def test_defaults(self):
        a = Attempt(action="edit", target="foo.py", result="ok")
        assert a.detail == ""
        assert a.turn == 0


class TestSession:

    def test_note_read(self):
        s = Session()
        s.note_read("foo.py", turn=1)
        assert "foo.py" in s.files_read
        assert s.files_read["foo.py"] == 1

    def test_note_write(self):
        s = Session()
        s.note_write("bar.py", turn=2)
        assert "bar.py" in s.files_written

    def test_note_decision(self):
        s = Session()
        s.note_decision("use ruff", "faster than flake8", turn=3)
        assert len(s.decisions) == 1
        assert s.decisions[0].what == "use ruff"

    def test_note_attempt(self):
        s = Session()
        s.note_attempt("edit", "foo.py", "failed", detail="old_string not found")
        assert len(s.attempts) == 1

    def test_note_error_dedup(self):
        s = Session()
        s.note_error("ImportError: no module named x")
        s.note_error("ImportError: no module named x")
        assert len(s.errors_seen) == 1

    def test_note_error_different(self):
        s = Session()
        s.note_error("error a")
        s.note_error("error b")
        assert len(s.errors_seen) == 2

    def test_note(self):
        s = Session()
        s.note("this file is auto-generated, don't edit")
        assert len(s.context_notes) == 1

    def test_was_tried_found(self):
        s = Session()
        s.note_attempt("edit", "foo.py", "failed")
        a = s.was_tried("edit", "foo.py")
        assert a is not None
        assert a.result == "failed"

    def test_was_tried_not_found(self):
        s = Session()
        assert s.was_tried("edit", "bar.py") is None

    def test_failed_attempts_for(self):
        s = Session()
        s.note_attempt("edit", "foo.py", "failed", detail="try 1")
        s.note_attempt("edit", "foo.py", "ok", detail="try 2")
        s.note_attempt("edit", "foo.py", "failed", detail="try 3")
        failed = s.failed_attempts_for("foo.py")
        assert len(failed) == 2

    def test_files_touched(self):
        s = Session()
        s.note_read("a.py")
        s.note_write("b.py")
        s.note_read("b.py")
        touched = s.files_touched()
        assert touched == ["a.py", "b.py"]

    def test_summary_empty(self):
        s = Session()
        assert "empty session" in s.summary()

    def test_summary_with_data(self):
        s = Session(task="fix bug")
        s.note_read("a.py")
        s.note_write("b.py")
        s.note_decision("x", "y")
        s.note_attempt("edit", "b.py", "ok")
        s.note_attempt("run", "test", "failed")
        summary = s.summary()
        assert "fix bug" in summary
        assert "read 1" in summary
        assert "wrote 1" in summary
        assert "1 succeeded" in summary
        assert "1 failed" in summary

    def test_context_for_prompt_empty(self):
        s = Session()
        assert s.context_for_prompt() == ""

    def test_context_for_prompt_with_decisions(self):
        s = Session()
        s.note_decision("use ruff", "it's faster")
        ctx = s.context_for_prompt()
        assert "use ruff" in ctx
        assert "faster" in ctx

    def test_context_for_prompt_with_failures(self):
        s = Session()
        s.note_attempt("edit", "foo.py", "failed", detail="not found")
        ctx = s.context_for_prompt()
        assert "Failed attempts" in ctx
        assert "foo.py" in ctx

    def test_context_for_prompt_with_errors(self):
        s = Session()
        s.note_error("TypeError: NoneType has no attribute")
        ctx = s.context_for_prompt()
        assert "Errors encountered" in ctx
        assert "TypeError" in ctx

    def test_context_limits_to_recent(self):
        s = Session()
        for i in range(10):
            s.note_decision(f"d{i}", f"reason {i}")
        ctx = s.context_for_prompt()
        # should only show last 5
        assert "d5" in ctx
        assert "d9" in ctx
        # d0 should be trimmed
        assert "d0" not in ctx


class TestConsecutiveTracking:

    def test_consecutive_count_single(self):
        s = Session()
        s.note_action("read", "foo.py", turn=0)
        assert s.consecutive_count("read", "foo.py") == 1

    def test_consecutive_count_multiple(self):
        s = Session()
        s.note_action("read", "foo.py", turn=0)
        s.note_action("read", "foo.py", turn=1)
        s.note_action("read", "foo.py", turn=2)
        assert s.consecutive_count("read", "foo.py") == 3

    def test_consecutive_count_broken_by_different_action(self):
        s = Session()
        s.note_action("read", "foo.py", turn=0)
        s.note_action("edit", "foo.py", turn=1)
        s.note_action("read", "foo.py", turn=2)
        assert s.consecutive_count("read", "foo.py") == 1

    def test_consecutive_count_broken_by_different_target(self):
        s = Session()
        s.note_action("read", "foo.py", turn=0)
        s.note_action("read", "bar.py", turn=1)
        s.note_action("read", "foo.py", turn=2)
        assert s.consecutive_count("read", "foo.py") == 1

    def test_consecutive_count_empty(self):
        s = Session()
        assert s.consecutive_count("read", "foo.py") == 0

    def test_result_cache(self):
        s = Session()
        s.note_action_result("read", "foo.py", "file contents here")
        assert s.last_result_for("read", "foo.py") == "file contents here"
        assert s.last_result_for("read", "bar.py") is None

    def test_result_cache_overwrites(self):
        s = Session()
        s.note_action_result("read", "foo.py", "version 1")
        s.note_action_result("read", "foo.py", "version 2")
        assert s.last_result_for("read", "foo.py") == "version 2"
