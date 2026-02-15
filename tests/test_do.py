"""Tests for hero/do.py - the general-purpose agentic loop."""

import json
import pytest
from unittest.mock import patch, MagicMock

from keanu.hero.do import AgentLoop, LoopResult, Step, _build_system, run


# ============================================================
# HELPERS
# ============================================================

def make_feel_result(response, should_pause=False):
    """Build a mock FeelResult."""
    mock = MagicMock()
    mock.response = response
    mock.should_pause = should_pause
    return mock


def json_response(thinking="ok", action="none", args=None, done=False, answer=""):
    """Build a JSON string like the LLM would return."""
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
# _parse_response
# ============================================================

class TestParseResponse:

    def setup_method(self):
        with patch("keanu.hero.do.Feel"):
            self.loop = AgentLoop()

    def test_valid_json(self):
        result = self.loop._parse_response('{"action": "read", "done": false}')
        assert result["action"] == "read"

    def test_json_in_markdown_fence(self):
        text = '```json\n{"action": "read", "done": false}\n```'
        result = self.loop._parse_response(text)
        assert result["action"] == "read"

    def test_json_with_surrounding_text(self):
        text = 'Here is my response:\n{"action": "ls", "args": {"path": "."}, "done": false}\nDone.'
        result = self.loop._parse_response(text)
        assert result["action"] == "ls"

    def test_invalid_json(self):
        assert self.loop._parse_response("not json at all") is None

    def test_empty_string(self):
        assert self.loop._parse_response("") is None

    def test_no_braces(self):
        assert self.loop._parse_response("just some text") is None


# ============================================================
# AgentLoop.run
# ============================================================

class TestAgentLoopRun:

    @patch("keanu.hero.do.Feel")
    def test_done_on_first_turn(self, MockFeel):
        loop = AgentLoop()
        loop.feel.felt_call.return_value = make_feel_result(
            json_response(thinking="easy", done=True, answer="42")
        )

        result = loop.run("what is 6*7?")

        assert result.ok
        assert result.status == "done"
        assert result.answer == "42"
        assert len(result.steps) == 1
        assert result.steps[0].action == "done"

    @patch("keanu.hero.do.Feel")
    def test_pause_on_black(self, MockFeel):
        loop = AgentLoop()
        loop.feel.felt_call.return_value = make_feel_result(
            "", should_pause=True
        )

        result = loop.run("do something")

        assert not result.ok
        assert result.status == "paused"
        assert "black" in result.error.lower()

    @patch("keanu.hero.do.Feel")
    def test_max_turns(self, MockFeel):
        loop = AgentLoop(max_turns=3)
        # always return "think" with no action
        loop.feel.felt_call.return_value = make_feel_result(
            json_response(thinking="hmm", action="think")
        )

        result = loop.run("impossible task")

        assert result.status == "max_turns"
        assert len(result.steps) == 3

    @patch("keanu.hero.do.Feel")
    def test_unknown_ability(self, MockFeel):
        loop = AgentLoop()
        # first call: try a fake ability
        # second call: done
        loop.feel.felt_call.side_effect = [
            make_feel_result(json_response(action="fireball", args={"target": "bug"})),
            make_feel_result(json_response(done=True, answer="gave up")),
        ]

        result = loop.run("cast fireball")

        assert result.ok
        assert len(result.steps) == 2
        assert result.steps[0].action == "fireball"
        assert not result.steps[0].ok
        assert "unknown" in result.steps[0].result.lower()

    @patch("keanu.hero.do.Feel")
    @patch("keanu.hero.do._REGISTRY")
    def test_ability_execution(self, mock_registry, MockFeel):
        mock_ab = MagicMock()
        mock_ab.execute.return_value = {
            "success": True,
            "result": "found 3 files",
            "data": {},
        }
        mock_registry.get.return_value = mock_ab

        loop = AgentLoop()
        loop.feel.felt_call.side_effect = [
            make_feel_result(json_response(action="search", args={"pattern": "*.py"})),
            make_feel_result(json_response(done=True, answer="found them")),
        ]

        result = loop.run("find python files")

        assert result.ok
        assert result.steps[0].action == "search"
        assert result.steps[0].ok
        assert "3 files" in result.steps[0].result

    @patch("keanu.hero.do.Feel")
    @patch("keanu.hero.do._REGISTRY")
    def test_ability_exception(self, mock_registry, MockFeel):
        mock_ab = MagicMock()
        mock_ab.execute.side_effect = RuntimeError("disk full")
        mock_registry.get.return_value = mock_ab

        loop = AgentLoop()
        loop.feel.felt_call.side_effect = [
            make_feel_result(json_response(action="write", args={"file_path": "x"})),
            make_feel_result(json_response(done=True, answer="failed")),
        ]

        result = loop.run("write a file")

        assert result.steps[0].action == "write"
        assert not result.steps[0].ok
        assert "disk full" in result.steps[0].result

    @patch("keanu.hero.do.Feel")
    def test_unparseable_response_retries(self, MockFeel):
        loop = AgentLoop(max_turns=3)
        loop.feel.felt_call.side_effect = [
            make_feel_result("this is not json"),
            make_feel_result(json_response(done=True, answer="got it")),
        ]

        result = loop.run("do a thing")

        assert result.ok
        assert len(result.steps) == 2
        assert result.steps[0].action == "think"  # unparseable -> "think" step


# ============================================================
# run() convenience function
# ============================================================

class TestRunConvenience:

    @patch("keanu.hero.do.Feel")
    def test_run_function(self, MockFeel):
        MockFeel.return_value.felt_call.return_value = make_feel_result(
            json_response(done=True, answer="done")
        )
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
