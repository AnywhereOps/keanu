"""tests for prove - the scientist (unified loop with PROVE_CONFIG)."""

import json
from unittest.mock import patch, MagicMock

from keanu.hero.prove import prove, ProveResult, ProveStep, EVIDENCE_TOOLS


class TestProveResult:

    def test_ok_with_verdict(self):
        r = ProveResult(task="test", status="done",
                        extras={"verdict": "supported", "confidence": 0.8})
        assert r.ok

    def test_not_ok_when_paused(self):
        r = ProveResult(task="test", status="paused")
        assert not r.ok

    def test_not_ok_with_error(self):
        r = ProveResult(task="test", status="error", error="boom")
        assert not r.ok


class TestProve:

    def _mock_oracle_sequence(self, responses):
        call_count = [0]
        def fake_oracle(*args, **kwargs):
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            return responses[idx]
        return fake_oracle

    def test_prove_gathers_evidence_then_verdicts(self):
        responses = [
            json.dumps({
                "thinking": "search for test files",
                "action": "search",
                "args": {"pattern": "test_", "glob": "*.py"},
                "done": False,
            }),
            json.dumps({
                "thinking": "weighing evidence",
                "action": "none",
                "args": {},
                "done": True,
                "verdict": "supported",
                "confidence": 0.85,
                "evidence_for": ["found 12 test files"],
                "evidence_against": [],
                "gaps": ["didn't check coverage percentage"],
                "summary": "tests exist for all major modules",
            }),
        ]

        mock_ability = MagicMock()
        mock_ability.execute.return_value = {
            "success": True,
            "result": "test_scan.py\ntest_detect.py\ntest_compress.py",
            "data": {},
        }

        with patch("keanu.hero.do.call_oracle", side_effect=self._mock_oracle_sequence(responses)):
            with patch("keanu.hero.do.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel
                with patch("keanu.hero.do._REGISTRY", {"search": mock_ability}):
                    result = prove("all modules have tests")

        assert result.ok
        assert result.extras["verdict"] == "supported"
        assert result.extras["confidence"] == 0.85
        assert len(result.extras["evidence_for"]) == 1
        assert len(result.extras["gaps"]) == 1

    def test_prove_handles_refuted(self):
        response = json.dumps({
            "thinking": "no evidence found",
            "action": "none",
            "args": {},
            "done": True,
            "verdict": "refuted",
            "confidence": 0.9,
            "evidence_for": [],
            "evidence_against": ["no test file found for module X"],
            "gaps": [],
            "summary": "module X has no tests",
        })

        with patch("keanu.hero.do.call_oracle", return_value=response):
            with patch("keanu.hero.do.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = prove("module X has tests")

        assert result.extras["verdict"] == "refuted"

    def test_prove_handles_connection_error(self):
        with patch("keanu.hero.do.call_oracle", side_effect=ConnectionError("down")):
            with patch("keanu.hero.do.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = prove("anything")

        assert not result.ok
        assert "down" in result.error

    def test_prove_rejects_non_evidence_tools(self):
        responses = [
            json.dumps({
                "thinking": "let me write a file",
                "action": "write",
                "args": {"file_path": "bad.py", "content": "evil"},
                "done": False,
            }),
            json.dumps({
                "thinking": "ok done",
                "action": "none",
                "args": {},
                "done": True,
                "verdict": "inconclusive",
                "confidence": 0.1,
                "evidence_for": [],
                "evidence_against": [],
                "gaps": ["couldn't gather evidence"],
                "summary": "blocked",
            }),
        ]

        with patch("keanu.hero.do.call_oracle", side_effect=self._mock_oracle_sequence(responses)):
            with patch("keanu.hero.do.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = prove("something", max_turns=5)

        assert any(not s.ok for s in result.steps)

    def test_evidence_tools_set(self):
        assert EVIDENCE_TOOLS == {"read", "search", "ls", "run", "recall"}
