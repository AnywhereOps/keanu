"""tests for speak.py - the communicator."""

import json
from unittest.mock import patch, MagicMock

from keanu.hero.speak import speak, SpeakResult, AUDIENCES


class TestSpeakResult:

    def test_ok_with_translation(self):
        r = SpeakResult(original="hi", audience="friend", translation="hey")
        assert r.ok

    def test_not_ok_empty(self):
        r = SpeakResult(original="hi", audience="friend")
        assert not r.ok

    def test_not_ok_with_error(self):
        r = SpeakResult(original="hi", audience="friend", translation="hey", error="boom")
        assert not r.ok


class TestSpeak:

    def test_speak_translates(self):
        oracle_response = json.dumps({
            "translation": "it reads your text with three colored glasses",
            "key_shifts": ["removed jargon", "used analogy"],
        })

        with patch("keanu.hero.speak.call_oracle", return_value=oracle_response):
            with patch("keanu.hero.speak.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = speak("the helix scanner uses three-primary color theory", audience="friend")

        assert result.ok
        assert "colored glasses" in result.translation
        assert len(result.key_shifts) == 2

    def test_speak_uses_audience_description(self):
        oracle_response = json.dumps({"translation": "ok", "key_shifts": []})

        with patch("keanu.hero.speak.call_oracle", return_value=oracle_response) as mock_oracle:
            with patch("keanu.hero.speak.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                speak("technical stuff", audience="executive")

        system_prompt = mock_oracle.call_args[0][1]
        assert "decision maker" in system_prompt

    def test_speak_custom_audience(self):
        oracle_response = json.dumps({"translation": "ok", "key_shifts": []})

        with patch("keanu.hero.speak.call_oracle", return_value=oracle_response) as mock_oracle:
            with patch("keanu.hero.speak.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.check.return_value = MagicMock(should_pause=False)
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                speak("code stuff", audience="a product manager who hates technical detail")

        system_prompt = mock_oracle.call_args[0][1]
        assert "product manager" in system_prompt

    def test_speak_handles_connection_error(self):
        with patch("keanu.hero.speak.call_oracle", side_effect=ConnectionError("down")):
            with patch("keanu.hero.speak.Feel") as mock_feel_cls:
                mock_feel = MagicMock()
                mock_feel.stats.return_value = {}
                mock_feel_cls.return_value = mock_feel

                result = speak("anything")

        assert not result.ok
        assert "down" in result.error

    def test_audiences_dict_has_expected_keys(self):
        assert "friend" in AUDIENCES
        assert "executive" in AUDIENCES
        assert "architect" in AUDIENCES
        assert "5-year-old" in AUDIENCES
