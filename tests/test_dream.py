"""tests for dream.py - the planner."""

import json
from unittest.mock import patch, MagicMock

from keanu.hero.dream import dream, DreamResult, DREAM_PROMPT


class TestDreamResult:

    def test_ok_with_phases(self):
        r = DreamResult(goal="test", phases=[{"name": "p1", "steps": []}], total_steps=0)
        assert r.ok

    def test_not_ok_empty(self):
        r = DreamResult(goal="test")
        assert not r.ok

    def test_not_ok_with_error(self):
        r = DreamResult(goal="test", phases=[{"name": "p1"}], error="boom")
        assert not r.ok


class TestDream:

    def test_dream_parses_oracle_response(self):
        oracle_response = json.dumps({
            "phases": [
                {
                    "name": "setup",
                    "steps": [
                        {"action": "create directory", "depends_on": None, "why": "need a place"},
                        {"action": "init project", "depends_on": "create directory", "why": "foundation"},
                    ]
                },
                {
                    "name": "build",
                    "steps": [
                        {"action": "write the code", "depends_on": None, "why": "the work"},
                    ]
                }
            ]
        })

        with patch("keanu.hero.dream.call_oracle", return_value=oracle_response):
            with patch("keanu.hero.dream.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = dream("build a REST API")

        assert result.ok
        assert len(result.phases) == 2
        assert result.total_steps == 3
        assert result.phases[0]["name"] == "setup"

    def test_dream_handles_connection_error(self):
        with patch("keanu.hero.dream.call_oracle", side_effect=ConnectionError("no oracle")):
            with patch("keanu.hero.dream.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = dream("anything")

        assert not result.ok
        assert "no oracle" in result.error

    def test_dream_handles_black_state(self):
        with patch("keanu.hero.dream.call_oracle", return_value="dark response"):
            with patch("keanu.hero.dream.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=True)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = dream("anything")

        assert not result.ok
        assert "black state" in result.error

    def test_dream_handles_bad_json(self):
        with patch("keanu.hero.dream.call_oracle", return_value="not json at all"):
            with patch("keanu.hero.dream.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = dream("anything")

        assert not result.ok

    def test_dream_passes_context(self):
        oracle_response = json.dumps({"phases": [{"name": "p1", "steps": []}]})

        with patch("keanu.hero.dream.call_oracle", return_value=oracle_response) as mock_oracle:
            with patch("keanu.hero.dream.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                dream("build API", context="we use FastAPI")

        call_args = mock_oracle.call_args
        assert "CONTEXT" in call_args[0][0]
        assert "FastAPI" in call_args[0][0]
