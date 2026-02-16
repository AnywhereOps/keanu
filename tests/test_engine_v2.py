"""tests for the six lens convergence engine."""

import json
from unittest.mock import patch, MagicMock

from keanu.converge.engine import (
    run, _develop_lens, _get_graph_context,
    LENSES, LensReading, ConvergeResult,
)
from keanu.converge.graph import DualityGraph


class TestLensReading:

    def test_defaults(self):
        r = LensReading(lens="roots+", name="test", axis="roots", pole="+")
        assert r.turns == 0
        assert r.score == 0.0
        assert not r.black

    def test_content(self):
        r = LensReading(
            lens="roots+", name="test", axis="roots", pole="+",
            turns=3, content="wisdom here", score=7.5,
        )
        assert r.turns == 3
        assert "wisdom" in r.content


class TestConvergeResult:

    def test_ok_with_synthesis(self):
        r = ConvergeResult(question="test", synthesis="the truth")
        assert r.ok

    def test_not_ok_empty(self):
        r = ConvergeResult(question="test")
        assert not r.ok

    def test_not_ok_with_error(self):
        r = ConvergeResult(question="test", synthesis="truth", error="boom")
        assert not r.ok


class TestLenses:

    def test_six_lenses_exist(self):
        assert len(LENSES) == 6

    def test_all_axes_covered(self):
        axes = {l["axis"] for l in LENSES}
        assert axes == {"roots", "threshold", "dreaming"}

    def test_all_poles_covered(self):
        poles = {(l["axis"], l["pole"]) for l in LENSES}
        assert len(poles) == 6

    def test_lens_ids(self):
        ids = {l["id"] for l in LENSES}
        assert ids == {
            "roots+", "roots-",
            "threshold+", "threshold-",
            "dreaming+", "dreaming-",
        }


class TestDevelopLens:

    def test_lens_reaches_done(self):
        responses = [
            "History teaches us that X. There's more.",
            "Also, Y happened in the past. DONE",
        ]
        call_count = [0]
        def fake_oracle(*args, **kwargs):
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            return responses[idx]

        mock_feel = MagicMock()
        mock_feel.check.return_value = MagicMock(should_pause=False)

        with patch("keanu.converge.engine.call_oracle", side_effect=fake_oracle):
            reading = _develop_lens(
                LENSES[0], "test question", "", mock_feel,
            )

        assert reading.turns == 2
        assert reading.score == 5.0
        assert "History" in reading.content
        assert "DONE" in reading.content

    def test_lens_stops_on_black(self):
        mock_feel = MagicMock()
        mock_feel.check.return_value = MagicMock(should_pause=True)

        with patch("keanu.converge.engine.call_oracle", return_value="dark"):
            reading = _develop_lens(
                LENSES[0], "test", "", mock_feel,
            )

        assert reading.black
        assert reading.turns == 0

    def test_lens_stops_on_max_turns(self):
        mock_feel = MagicMock()
        mock_feel.check.return_value = MagicMock(should_pause=False)

        with patch("keanu.converge.engine.call_oracle", return_value="more"):
            reading = _develop_lens(
                LENSES[0], "test", "", mock_feel, max_turns=3,
            )

        assert reading.turns == 3
        assert reading.score == 7.5

    def test_lens_handles_connection_error(self):
        mock_feel = MagicMock()

        with patch("keanu.converge.engine.call_oracle", side_effect=ConnectionError("down")):
            reading = _develop_lens(
                LENSES[0], "test", "", mock_feel,
            )

        assert reading.turns == 0


class TestGraphContext:

    def test_returns_context_string(self):
        graph = DualityGraph()
        ctx = _get_graph_context("What is consciousness?", graph)
        assert isinstance(ctx, str)

    def test_empty_on_no_match(self):
        graph = DualityGraph()
        ctx = _get_graph_context("xyzzy12345", graph)
        # may or may not match, just check it doesn't crash
        assert isinstance(ctx, str)


class TestRun:

    def _mock_oracle_sequence(self, responses):
        call_count = [0]
        def fake(*args, **kwargs):
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            return responses[idx]
        return fake

    def test_full_pipeline(self):
        # 6 lenses x 1 turn each (all say DONE immediately) + 1 synthesis
        lens_response = "Full perspective here. DONE"
        synth_response = json.dumps({
            "synthesis": "all six lenses agree on this",
            "one_line": "the truth",
            "tensions": ["one tension"],
            "what_changes": "everything",
        })
        responses = [lens_response] * 6 + [synth_response]

        with patch("keanu.converge.engine.call_oracle",
                   side_effect=self._mock_oracle_sequence(responses)):
            with patch("keanu.converge.engine.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = run("Is AI conscious?")

        assert result.ok
        assert len(result.readings) == 6
        assert result.one_line == "the truth"
        assert len(result.tensions) == 1
        assert result.what_changes == "everything"

    def test_handles_oracle_down(self):
        with patch("keanu.converge.engine.call_oracle",
                   side_effect=ConnectionError("offline")):
            with patch("keanu.converge.engine.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = run("anything")

        assert not result.ok
        assert len(result.readings) == 6
        # all readings should have 0 turns (connection failed)
        assert all(r.turns == 0 for r in result.readings)

    def test_multi_turn_lens(self):
        # first lens takes 3 turns, rest say DONE immediately
        lens_responses = [
            "first thought", "second thought", "third thought. DONE",
        ]
        quick_response = "quick. DONE"
        synth_response = json.dumps({
            "synthesis": "converged",
            "one_line": "truth",
        })
        all_responses = lens_responses + [quick_response] * 5 + [synth_response]

        with patch("keanu.converge.engine.call_oracle",
                   side_effect=self._mock_oracle_sequence(all_responses)):
            with patch("keanu.converge.engine.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = run("test", max_turns=5)

        assert result.ok
        assert result.readings[0].turns == 3
        assert result.readings[0].score == 7.5
        assert result.readings[1].turns == 1

    def test_graph_context_included(self):
        result_graph = []
        with patch("keanu.converge.engine.call_oracle", return_value="DONE"):
            with patch("keanu.converge.engine.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                with patch("keanu.converge.engine._synthesize",
                          return_value={"synthesis": "ok", "one_line": "ok"}):
                    result = run("consciousness and free will")

        assert isinstance(result.graph_context, list)
