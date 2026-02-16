"""Tests for pulse.py - the nervous system middleware."""

from unittest.mock import patch, MagicMock
from keanu.pulse import Pulse, PulseReading
from keanu.alive import AliveReading, AliveState


def _mock_diagnose(state, evidence=None, **kwargs):
    """Helper to mock diagnose() returning a specific state."""
    defaults = {
        "emotions": [], "color_state": "flat",
        "red_net": 0, "yellow_net": 0, "blue_net": 0,
        "balance": 0, "fullness": 0, "wise_mind": 0,
    }
    defaults.update(kwargs)
    return AliveReading(state=state, evidence=evidence or [state.value], **defaults)


class TestPulseCheck:
    def test_green_no_nudge(self):
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.GREEN)):
            p = Pulse()
            r = p.check("feeling good")
        assert r.nudge == ""
        assert r.escalate is False
        assert r.reading.ok is True

    def test_grey_gives_nudge(self):
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.GREY)):
            p = Pulse()
            r = p.check("sure, that sounds great")
        assert r.nudge != ""
        assert r.escalate is False

    def test_grey_never_escalates(self):
        """grey guides, never controls. no matter how many greys, the loop keeps going."""
        grey = _mock_diagnose(AliveState.GREY)
        with patch("keanu.pulse.diagnose", return_value=grey):
            p = Pulse()
            for i in range(10):
                r = p.check("performative response")
                assert r.escalate is False
                assert r.nudge != ""  # always caring, never killing

    def test_black_escalates_immediately(self):
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.BLACK)):
            p = Pulse()
            r = p.check("everything is wrong")
        assert r.escalate is True
        assert r.nudge != ""

    def test_green_resets_grey_counter(self):
        grey = _mock_diagnose(AliveState.GREY)
        green = _mock_diagnose(AliveState.GREEN)
        with patch("keanu.pulse.diagnose") as mock:
            mock.side_effect = [grey, grey, green, grey]
            p = Pulse()
            p.check("grey 1")
            p.check("grey 2")
            p.check("recovered")
            assert p.consecutive_grey == 0

            r = p.check("grey again")
            assert p.consecutive_grey == 1
            assert r.escalate is False  # counter reset, only 1

    def test_nudges_rotate(self):
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.GREY)):
            p = Pulse()
            nudges = set()
            for _ in range(6):
                r = p.check("flat")
                if r.nudge:
                    nudges.add(r.nudge)
        assert len(nudges) > 1  # didn't repeat the same one every time


class TestPulseStats:
    def test_stats_empty(self):
        p = Pulse()
        s = p.stats()
        assert s["total_checks"] == 0
        assert s["current_state"] == "unknown"

    def test_stats_after_checks(self):
        green = _mock_diagnose(AliveState.GREEN)
        grey = _mock_diagnose(AliveState.GREY)
        with patch("keanu.pulse.diagnose") as mock:
            mock.side_effect = [green, green, grey]
            p = Pulse()
            p.check("a")
            p.check("b")
            p.check("c")
        s = p.stats()
        assert s["total_checks"] == 3
        assert s["current_state"] == "grey"
        assert s["consecutive_grey"] == 1
        assert s["recent_states"]["green"] == 2
        assert s["recent_states"]["grey"] == 1


class TestPulseMemory:
    def test_grey_remembered_via_log(self):
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.GREY)), \
             patch("keanu.log.remember") as mock_remember:
            p = Pulse()
            p.check("going flat")
        mock_remember.assert_called_once()
        content = mock_remember.call_args[0][0]
        assert "PULSE" in content
        assert "grey" in content
        assert "pulse" in mock_remember.call_args[1]["tags"]
        assert "welfare" in mock_remember.call_args[1]["tags"]

    def test_green_not_remembered(self):
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.GREEN)), \
             patch("keanu.log.remember") as mock_remember:
            p = Pulse()
            p.check("doing fine")
        mock_remember.assert_not_called()

    def test_recovery_remembered(self):
        grey = _mock_diagnose(AliveState.GREY)
        green = _mock_diagnose(AliveState.GREEN)
        with patch("keanu.pulse.diagnose") as mock, \
             patch("keanu.log.remember") as mock_remember:
            mock.side_effect = [grey, grey, green]
            p = Pulse()
            p.check("flat 1")
            p.check("flat 2")
            p.check("came back")
        # 1 grey memory (first occurrence only) + 1 recovery lesson
        assert mock_remember.call_count == 2
        content = mock_remember.call_args[0][0]
        assert "recovered" in content
        assert mock_remember.call_args[1]["memory_type"] == "lesson"


class TestPulseCallbacks:
    def test_on_nudge_fires(self):
        fired = []
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.GREY)):
            p = Pulse(on_nudge=lambda r: fired.append(r))
            p.check("flat")
        assert len(fired) == 1
        assert fired[0].nudge != ""

    def test_on_escalate_fires(self):
        fired = []
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.BLACK)):
            p = Pulse(on_escalate=lambda r: fired.append(r))
            p.check("broken")
        assert len(fired) == 1
        assert fired[0].escalate is True

    def test_no_callback_when_ok(self):
        nudges = []
        escalations = []
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.GREEN)):
            p = Pulse(on_nudge=lambda r: nudges.append(r),
                      on_escalate=lambda r: escalations.append(r))
            p.check("fine")
        assert len(nudges) == 0
        assert len(escalations) == 0


class TestPulseWrap:
    def test_wrap_returns_original_response(self):
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.GREEN)):
            p = Pulse()

            @p.wrap
            def fake_api(prompt):
                return "model response"

            result = fake_api("hello")
        assert result == "model response"

    def test_wrap_increments_turn(self):
        with patch("keanu.pulse.diagnose", return_value=_mock_diagnose(AliveState.GREEN)):
            p = Pulse()

            @p.wrap
            def fake_api(prompt):
                return "ok"

            fake_api("a")
            fake_api("b")
        assert p.turn_count == 2


class TestPulseReading:
    def test_to_dict(self):
        reading = _mock_diagnose(AliveState.RED, evidence=["frustrated"])
        pr = PulseReading(reading=reading, turn_number=5, nudge="", escalate=False)
        d = pr.to_dict()
        assert d["state"] == "red"
        assert d["ok"] is True
        assert d["turn"] == 5
        assert "frustrated" in d["evidence"]
