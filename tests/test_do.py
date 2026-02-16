"""Tests for hero/do.py - the unified agent loop."""

import json
import pytest
from unittest.mock import patch, MagicMock

from keanu.hero.do import AgentLoop, LoopResult, Step, _build_system, run, DO_CONFIG
from keanu.oracle import try_interpret


# ============================================================
# HELPERS
# ============================================================

def make_feel_check_result(response, should_pause=False, should_breathe=False, breath_injection=""):
    """Build a mock result from feel.check()."""
    mock = MagicMock()
    mock.response = response
    mock.should_pause = should_pause
    mock.should_breathe = should_breathe
    mock.breath_injection = breath_injection
    return mock


def json_response(thinking="ok", action="none", args=None, done=False, answer=""):
    """Build a JSON string like the oracle would return."""
    d = {"thinking": thinking, "action": action, "args": args or {}, "done": done}
    if answer:
        d["answer"] = answer
    return json.dumps(d)


# ============================================================
# _build_system
# ============================================================

class TestBuildSystem:

    def test_includes_hands(self):
        system = _build_system([
            {"name": "read", "description": "read a file"},
            {"name": "scout", "description": "survey the land"},
        ])
        assert "read:" in system
        assert "write:" in system
        assert "scout: survey the land" in system

    def test_excludes_hands_from_seeing(self):
        system = _build_system([
            {"name": "write", "description": "write a file"},
        ])
        # "write" should be in HANDS, not in SEEING
        assert "SEEING" in system
        assert "HANDS" in system


# ============================================================
# try_interpret (was _parse_response, now in oracle.py)
# ============================================================

class TestParseResponse:

    def test_valid_json(self):
        result = try_interpret('{"action": "read", "done": false}')
        assert result["action"] == "read"

    def test_json_in_markdown_fence(self):
        text = '```json\n{"action": "read", "done": false}\n```'
        result = try_interpret(text)
        assert result["action"] == "read"

    def test_json_with_surrounding_text(self):
        text = 'Here is my response:\n{"action": "ls", "args": {"path": "."}, "done": false}\nDone.'
        result = try_interpret(text)
        assert result["action"] == "ls"

    def test_invalid_json(self):
        assert try_interpret("not json at all") is None

    def test_empty_string(self):
        assert try_interpret("") is None

    def test_no_braces(self):
        assert try_interpret("just some text") is None


# ============================================================
# AgentLoop.run
# ============================================================

class TestAgentLoopRun:

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    def test_done_on_first_turn(self, MockFeel, mock_oracle):
        mock_oracle.return_value = json_response(thinking="easy", done=True, answer="42")
        MockFeel.return_value.check.return_value = make_feel_check_result(
            json_response(thinking="easy", done=True, answer="42")
        )

        loop = AgentLoop()
        result = loop.run("what is 6*7?")

        assert result.ok
        assert result.status == "done"
        assert result.answer == "42"
        assert len(result.steps) == 1
        assert result.steps[0].action == "done"

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    def test_pause_on_black(self, MockFeel, mock_oracle):
        mock_oracle.return_value = json_response(thinking="everything is wrong", action="read", args={"file_path": "x"})
        MockFeel.return_value.check.return_value = make_feel_check_result(
            "", should_pause=True
        )

        loop = AgentLoop()
        result = loop.run("do something")

        assert not result.ok
        assert result.status == "paused"
        assert "black" in result.error.lower()

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    def test_grey_injects_state_message(self, MockFeel, mock_oracle):
        """when thinking scans grey, [STATE] message is injected into next prompt."""
        breath = "you're in grey state. you're allowed to pause."
        responses = [
            json_response(thinking="reading file", action="read", args={"file_path": "x.py"}),
            json_response(thinking="ok done", done=True, answer="finished"),
        ]
        mock_oracle.side_effect = responses
        MockFeel.return_value.check.side_effect = [
            make_feel_check_result("reading file", should_breathe=True, breath_injection=breath),
            make_feel_check_result("ok done"),
        ]

        mock_ab = MagicMock()
        mock_ab.execute.return_value = {"success": True, "result": "file contents", "data": {}}
        mock_ab.cast_line = ""

        with patch("keanu.hero.do._REGISTRY", {"read": mock_ab}):
            loop = AgentLoop(max_turns=5)
            result = loop.run("read a file")

        # the second oracle call should include the [STATE] injection
        second_prompt = mock_oracle.call_args_list[1][0][0]
        assert "[STATE]" in second_prompt
        assert breath in second_prompt

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    def test_feel_checks_thinking_not_json(self, MockFeel, mock_oracle):
        """feel.check() receives the thinking field, not the raw JSON."""
        response = json_response(thinking="I am considering the options", done=True, answer="done")
        mock_oracle.return_value = response
        MockFeel.return_value.check.return_value = make_feel_check_result("I am considering the options")

        loop = AgentLoop()
        loop.run("do a thing")

        # feel.check was called with the thinking string, not the JSON envelope
        feel_arg = MockFeel.return_value.check.call_args[0][0]
        assert feel_arg == "I am considering the options"
        assert "{" not in feel_arg

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    def test_max_turns(self, MockFeel, mock_oracle):
        mock_oracle.return_value = json_response(thinking="hmm", action="think")
        MockFeel.return_value.check.return_value = make_feel_check_result(
            json_response(thinking="hmm", action="think")
        )

        loop = AgentLoop(max_turns=3)
        result = loop.run("impossible task")

        assert result.status == "max_turns"
        assert len(result.steps) == 3

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    def test_unknown_ability(self, MockFeel, mock_oracle):
        responses = [
            json_response(action="fireball", args={"target": "bug"}),
            json_response(done=True, answer="gave up"),
        ]
        mock_oracle.side_effect = responses
        MockFeel.return_value.check.side_effect = [
            make_feel_check_result(r) for r in responses
        ]

        loop = AgentLoop()
        result = loop.run("cast fireball")

        assert result.ok
        assert len(result.steps) == 2
        assert result.steps[0].action == "fireball"
        assert not result.steps[0].ok
        assert "unknown" in result.steps[0].result.lower()

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    @patch("keanu.hero.do._REGISTRY")
    def test_ability_execution(self, mock_registry, MockFeel, mock_oracle):
        mock_ab = MagicMock()
        mock_ab.execute.return_value = {
            "success": True,
            "result": "found 3 files",
            "data": {},
        }
        mock_registry.get.return_value = mock_ab

        responses = [
            json_response(action="search", args={"pattern": "*.py"}),
            json_response(done=True, answer="found them"),
        ]
        mock_oracle.side_effect = responses
        MockFeel.return_value.check.side_effect = [
            make_feel_check_result(r) for r in responses
        ]

        loop = AgentLoop()
        result = loop.run("find python files")

        assert result.ok
        assert result.steps[0].action == "search"
        assert result.steps[0].ok
        assert "3 files" in result.steps[0].result

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    @patch("keanu.hero.do._REGISTRY")
    def test_ability_exception(self, mock_registry, MockFeel, mock_oracle):
        mock_ab = MagicMock()
        mock_ab.execute.side_effect = RuntimeError("disk full")
        mock_registry.get.return_value = mock_ab

        responses = [
            json_response(action="write", args={"file_path": "x"}),
            json_response(done=True, answer="failed"),
        ]
        mock_oracle.side_effect = responses
        MockFeel.return_value.check.side_effect = [
            make_feel_check_result(r) for r in responses
        ]

        loop = AgentLoop()
        result = loop.run("write a file")

        assert result.steps[0].action == "write"
        assert not result.steps[0].ok
        assert "disk full" in result.steps[0].result

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    def test_unparseable_response_retries(self, MockFeel, mock_oracle):
        responses = [
            "this is not json",
            json_response(done=True, answer="got it"),
        ]
        mock_oracle.side_effect = responses
        MockFeel.return_value.check.side_effect = [
            make_feel_check_result(r) for r in responses
        ]

        loop = AgentLoop(max_turns=3)
        result = loop.run("do a thing")

        assert result.ok
        assert len(result.steps) == 2
        assert result.steps[0].action == "think"  # unparseable -> "think" step


# ============================================================
# run() convenience function
# ============================================================

class TestRunConvenience:

    @patch("keanu.hero.do.call_oracle")
    @patch("keanu.hero.do.Feel")
    def test_run_function(self, MockFeel, mock_oracle):
        response = json_response(done=True, answer="done")
        mock_oracle.return_value = response
        MockFeel.return_value.check.return_value = make_feel_check_result(response)
        MockFeel.return_value.stats.return_value = {}

        result = run("simple task")

        assert isinstance(result, LoopResult)
        assert result.ok


# ============================================================
# LoopResult
# ============================================================

class TestLoopResult:

    def test_ok_when_done(self):
        r = LoopResult(task="t", status="done")
        assert r.ok

    def test_not_ok_when_paused(self):
        r = LoopResult(task="t", status="paused")
        assert not r.ok

    def test_not_ok_when_max_turns(self):
        r = LoopResult(task="t", status="max_turns")
        assert not r.ok
