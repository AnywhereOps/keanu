"""tests for craft - the coder (unified loop with CRAFT_CONFIG)."""

import json
from unittest.mock import patch, MagicMock

from keanu.hero.craft import craft, CraftResult, CraftStep, HANDS


class TestCraftResult:

    def test_ok_when_done(self):
        r = CraftResult(task="test", status="done")
        assert r.ok

    def test_not_ok_when_paused(self):
        r = CraftResult(task="test", status="paused")
        assert not r.ok


class TestCraftStep:

    def test_step_defaults(self):
        s = CraftStep(turn=0, action="read", input_summary="file.py", result="contents")
        assert s.ok
        assert s.turn == 0


class TestCraft:

    def _mock_oracle_sequence(self, responses):
        """helper: oracle returns responses in sequence."""
        call_count = [0]
        def fake_oracle(*args, **kwargs):
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            return responses[idx]
        return fake_oracle

    def test_craft_reads_then_done(self):
        responses = [
            json.dumps({
                "thinking": "need to read the file first",
                "action": "read",
                "args": {"file_path": "test.py"},
                "done": False,
            }),
            json.dumps({
                "thinking": "file looks good, nothing to change",
                "action": "none",
                "args": {},
                "done": True,
                "answer": "no changes needed",
                "files_changed": [],
            }),
        ]

        mock_ability = MagicMock()
        mock_ability.execute.return_value = {
            "success": True,
            "result": "file contents here",
            "data": {},
        }

        with patch("keanu.hero.do.call_oracle", side_effect=self._mock_oracle_sequence(responses)):
            with patch("keanu.hero.do.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel
                with patch("keanu.hero.do._REGISTRY", {"read": mock_ability}):
                    result = craft("check test.py")

        assert result.ok
        assert len(result.steps) == 2

    def test_craft_rejects_non_hand_abilities(self):
        response = json.dumps({
            "thinking": "let me scan",
            "action": "scry",
            "args": {},
            "done": False,
        })
        done_response = json.dumps({
            "thinking": "ok done",
            "action": "none",
            "args": {},
            "done": True,
            "answer": "done",
        })

        with patch("keanu.hero.do.call_oracle", side_effect=self._mock_oracle_sequence([response, done_response])):
            with patch("keanu.hero.do.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = craft("do something", max_turns=5)

        assert any(not s.ok for s in result.steps)

    def test_craft_handles_connection_error(self):
        with patch("keanu.hero.do.call_oracle", side_effect=ConnectionError("offline")):
            with patch("keanu.hero.do.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = craft("anything")

        assert result.status == "paused"
        assert "offline" in result.error

    def test_hands_set(self):
        assert HANDS == {"read", "write", "edit", "search", "ls", "run", "git", "test", "lint", "format", "patch"}
