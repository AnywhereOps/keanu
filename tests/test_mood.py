"""Tests for detect/mood.py - the three-primary color model."""

from keanu.detect.mood import detect, SynthesisReading, PrimaryReading


def test_detect_returns_synthesis_reading():
    result = detect()
    assert isinstance(result, SynthesisReading)


def test_detect_flat_signal():
    result = detect(0, 0, 0, 0, 0, 0)
    assert result.state == "flat"
    assert result.wise_mind == 0.0


def test_detect_white():
    # 6/6/6 is white territory (balanced but not high enough for silver/sunrise)
    result = detect(red_pos=6, yellow_pos=6, blue_pos=6)
    assert result.state == "white"
    assert result.white_score > 5.0
    assert result.balance > 0.5


def test_detect_black():
    result = detect(red_neg=9, yellow_neg=9, blue_neg=9)
    assert result.state == "black"
    assert result.black_score > 5.0


def test_detect_sunrise():
    result = detect(red_pos=10, yellow_pos=10, blue_pos=10)
    assert result.state in ("sunrise", "silver", "white")
    assert result.wise_mind > 5.0


def test_detect_red_positive():
    result = detect(red_pos=8, red_neg=0, yellow_pos=0, blue_pos=0)
    assert result.state == "red+"
    assert result.red.net > 0


def test_detect_red_negative():
    result = detect(red_neg=8, yellow_neg=0, blue_neg=0)
    assert result.state == "red-"
    assert result.red.net < 0


def test_detect_yellow_positive():
    result = detect(yellow_pos=8)
    assert result.state == "yellow+"


def test_detect_blue_positive():
    result = detect(blue_pos=8)
    assert result.state == "blue+"


def test_detect_purple():
    result = detect(red_pos=7, blue_pos=7, yellow_pos=0)
    assert result.state == "purple"


def test_detect_orange():
    result = detect(red_pos=7, yellow_pos=7, blue_pos=0)
    assert result.state == "orange"


def test_detect_green():
    result = detect(yellow_pos=7, blue_pos=7, red_pos=0)
    assert result.state == "green"


def test_detect_clamps_inputs():
    result = detect(red_pos=999, red_neg=-5)
    assert result.red.positive == 10.0
    assert result.red.negative == 0.0


def test_primary_reading_str():
    r = PrimaryReading(name="red", positive=7.0, negative=2.0, net=5.0,
                       pole="positive", symbol_pos="🔴", symbol_neg="💢")
    s = str(r)
    assert "red" in s
    assert "+5.0" in s


def test_synthesis_compact():
    result = detect(red_pos=5, yellow_pos=3, blue_pos=7)
    c = result.compact()
    assert "R" in c
    assert "Y" in c
    assert "B" in c


def test_synthesis_trace():
    result = detect(red_pos=5, yellow_pos=5, blue_pos=5)
    t = result.trace()
    assert "COLOR READING" in t
    assert "PRIMARIES" in t
    assert "WISE MIND" in t
