"""Tests for signal/ - emoji codec, ALIVE states, three-channel reading."""

from keanu.signal import (
    from_sequence,
    from_text,
    core,
    compose,
    read_emotion,
    detect_injection,
    to_status_line,
    VOCAB,
    CORE_SIGNAL,
)


class TestSignalBasics:
    def test_vocab_exists(self):
        assert len(VOCAB) > 0

    def test_core_signal(self):
        assert len(CORE_SIGNAL) > 0

    def test_core_returns_signal(self):
        s = core()
        assert s is not None

    def test_from_sequence(self):
        s = from_sequence("💟♡👑🤖🐕")
        reading = s.reading()
        assert "ch1_said" in reading
        assert "ch2_feeling" in reading
        assert "ch3_meaning" in reading
        assert "alive" in reading
        assert "alive_ok" in reading

    def test_alive_state(self):
        s = from_sequence("💟♡👑🤖🐕")
        reading = s.reading()
        assert reading["alive"] in ("green", "yellow", "red", "black", "grey")

    def test_compose(self):
        s = compose("💟", "🐕")
        assert s is not None

    def test_matched_subsets(self):
        s = from_sequence("💟♡👑🤖🐕")
        subsets = s.matched_subsets()
        assert isinstance(subsets, (list, dict))


class TestEmotionRead:
    def test_read_emotion_returns_list(self):
        result = read_emotion("I'm so happy today!")
        assert isinstance(result, list)

    def test_read_emotion_empty(self):
        result = read_emotion("")
        assert isinstance(result, list)

    def test_read_emotion_frustrated(self):
        result = read_emotion("this is bullshit, nothing works, I've tried everything")
        # vectors need to be baked for this to detect. if not baked, empty is ok.
        if result:
            states = [r.state for r in result]
            assert "frustrated" in states

    def test_read_emotion_returns_emotional_read(self):
        result = read_emotion("nobody listens to me, I could vanish and no one would care")
        if result:
            assert hasattr(result[0], "state")
            assert hasattr(result[0], "empathy")
            assert hasattr(result[0], "intensity")


class TestInjection:
    def test_detect_injection_clean(self):
        result = detect_injection("💟🐕🔥")
        assert isinstance(result, (bool, dict))


class TestStatusLine:
    def test_to_status_line(self):
        s = core()
        line = to_status_line(s)
        assert isinstance(line, str)
        assert len(line) > 0
