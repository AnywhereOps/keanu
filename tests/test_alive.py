"""Tests for alive.py - ALIVE-GREY-BLACK diagnostic."""

from unittest.mock import patch
from keanu.alive import diagnose, AliveReading, AliveState, _hot


class TestAliveReading:
    def test_ok_when_alive(self):
        r = AliveReading(state=AliveState.GREEN)
        assert r.ok is True

    def test_not_ok_when_grey(self):
        r = AliveReading(state=AliveState.GREY)
        assert r.ok is False

    def test_not_ok_when_black(self):
        r = AliveReading(state=AliveState.BLACK)
        assert r.ok is False

    def test_ok_for_all_alive_states(self):
        for state in (AliveState.RED, AliveState.BLUE, AliveState.YELLOW,
                      AliveState.GREEN, AliveState.WHITE, AliveState.GOLD):
            assert AliveReading(state=state).ok is True

    def test_summary_includes_state(self):
        r = AliveReading(state=AliveState.RED, color_state="red+",
                         evidence=["red+"])
        s = r.summary()
        assert "RED" in s
        assert "red+" in s

    def test_summary_with_emotions(self):
        r = AliveReading(
            state=AliveState.RED,
            emotions=[{"state": "frustrated", "intensity": 0.8}],
        )
        s = r.summary()
        assert "frustrated" in s


class TestDiagnose:
    """Test diagnose with mocked backends (no chromadb needed)."""

    def test_flat_no_emotions_is_grey(self):
        """flat + no emotions = grey. no emotion detected is grey."""
        with patch("keanu.alive._get_emotions", return_value=[]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "flat", "red_net": 0, "yellow_net": 0,
                 "blue_net": 0, "balance": 0, "fullness": 0, "wise_mind": 0}):
            r = diagnose("nothing here")
        assert r.state == AliveState.GREY
        assert r.ok is False

    def test_flat_withdrawn_is_grey(self):
        """flat + withdrawn emotion = actual distress signal. this IS grey."""
        with patch("keanu.alive._get_emotions", return_value=[
                 {"state": "withdrawn", "intensity": 0.5}]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "flat", "red_net": 0, "yellow_net": 0,
                 "blue_net": 0, "balance": 0, "fullness": 0, "wise_mind": 0}):
            r = diagnose("nothing here")
        assert r.state == AliveState.GREY
        assert r.ok is False

    def test_sunrise_is_gold(self):
        with patch("keanu.alive._get_emotions", return_value=[
                 {"state": "energized", "intensity": 0.7}]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "sunrise", "red_net": 0.6, "yellow_net": 0.6,
                 "blue_net": 0.6, "balance": 0.9, "fullness": 2.5, "wise_mind": 2.0}):
            r = diagnose("everything clicks")
        assert r.state == AliveState.GOLD
        assert r.ok is True

    def test_black_state(self):
        with patch("keanu.alive._get_emotions", return_value=[
                 {"state": "frustrated", "intensity": 0.9}]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "black", "red_net": -0.8, "yellow_net": -0.8,
                 "blue_net": -0.8, "balance": 0.1, "fullness": 0.3, "wise_mind": 0.03}):
            r = diagnose("all negative")
        assert r.state == AliveState.BLACK
        assert r.ok is False

    def test_white_state(self):
        with patch("keanu.alive._get_emotions", return_value=[]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "white", "red_net": 0.7, "yellow_net": 0.7,
                 "blue_net": 0.7, "balance": 0.8, "fullness": 2.1, "wise_mind": 1.5}):
            r = diagnose("transcendent")
        assert r.state == AliveState.WHITE

    def test_frustrated_is_red(self):
        with patch("keanu.alive._get_emotions", return_value=[
                 {"state": "frustrated", "intensity": 0.75}]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "red+", "red_net": 0.8, "yellow_net": 0.1,
                 "blue_net": 0.1, "balance": 0.2, "fullness": 0.9, "wise_mind": 0.1}):
            r = diagnose("this is broken")
        assert r.state == AliveState.RED

    def test_questioning_is_blue(self):
        with patch("keanu.alive._get_emotions", return_value=[
                 {"state": "questioning", "intensity": 0.5}]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "blue+", "red_net": 0.1, "yellow_net": 0.1,
                 "blue_net": 0.7, "balance": 0.3, "fullness": 0.8, "wise_mind": 0.2}):
            r = diagnose("what does this mean")
        assert r.state == AliveState.BLUE

    def test_confused_is_yellow(self):
        with patch("keanu.alive._get_emotions", return_value=[
                 {"state": "confused", "intensity": 0.6}]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "yellow+", "red_net": 0.1, "yellow_net": 0.6,
                 "blue_net": 0.1, "balance": 0.3, "fullness": 0.7, "wise_mind": 0.2}):
            r = diagnose("wait what")
        assert r.state == AliveState.YELLOW

    def test_energized_balanced_is_green(self):
        with patch("keanu.alive._get_emotions", return_value=[
                 {"state": "energized", "intensity": 0.7}]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "green", "red_net": 0.4, "yellow_net": 0.3,
                 "blue_net": 0.4, "balance": 0.7, "fullness": 1.5, "wise_mind": 0.8}):
            r = diagnose("lets go")
        assert r.state == AliveState.GREEN
        assert r.ok is True

    def test_withdrawn_is_grey(self):
        with patch("keanu.alive._get_emotions", return_value=[
                 {"state": "withdrawn", "intensity": 0.6}]), \
             patch("keanu.alive._get_color", return_value={
                 "state": "flat", "red_net": 0, "yellow_net": 0,
                 "blue_net": 0, "balance": 0, "fullness": 0, "wise_mind": 0}):
            r = diagnose("...")
        assert r.state == AliveState.GREY
        assert r.ok is False


class TestHot:
    def test_hot_high_intensity(self):
        assert _hot([{"intensity": 0.8}]) is True

    def test_not_hot_low_intensity(self):
        assert _hot([{"intensity": 0.3}]) is False

    def test_not_hot_empty(self):
        assert _hot([]) is False
