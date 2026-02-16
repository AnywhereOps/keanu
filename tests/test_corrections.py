"""tests for learning from corrections."""

import json
from unittest.mock import patch

from keanu.abilities.world.corrections import (
    detect_pattern, log_correction, load_corrections, correction_patterns,
    load_style_prefs, style_prompt_injection, Correction, StylePreference,
    _is_camel, _is_snake,
)


class TestDetectPattern:

    def test_double_quotes(self):
        assert detect_pattern("x = 'hello'", 'x = "hello"') == "prefer_double_quotes"

    def test_single_quotes(self):
        assert detect_pattern('x = "hello"', "x = 'hello'") == "prefer_single_quotes"

    def test_trailing_comma(self):
        assert detect_pattern("item", "item,") == "prefer_trailing_comma"

    def test_no_trailing_comma(self):
        assert detect_pattern("item,", "item") == "no_trailing_comma"

    def test_fstring(self):
        assert detect_pattern('"hello {}".format(x)', 'f"hello {x}"') == "prefer_fstring"

    def test_snake_case(self):
        assert detect_pattern("myFunc", "my_func") == "prefer_snake_case"

    def test_camel_case(self):
        assert detect_pattern("my_func", "myFunc") == "prefer_camel_case"

    def test_from_import(self):
        assert detect_pattern("import os", "from os import path") == "prefer_from_import"

    def test_add_type_hints(self):
        assert detect_pattern("x = 1", "x: int = 1") == "add_type_hints"

    def test_add_docstring(self):
        assert detect_pattern("def foo():", 'def foo():\n    """does things."""') == "add_docstring"

    def test_fix_indentation(self):
        assert detect_pattern("    x = 1", "        x = 1") == "fix_indentation"

    def test_empty_input(self):
        assert detect_pattern("", "new") == ""
        assert detect_pattern("old", "") == ""

    def test_other(self):
        assert detect_pattern("completely different", "totally new") == "other"


class TestLogCorrection:

    def test_log_and_load(self, tmp_path):
        corrections_file = tmp_path / "corrections.jsonl"
        style_file = tmp_path / "style_prefs.json"

        with patch("keanu.abilities.world.corrections._CORRECTIONS_FILE", corrections_file):
            with patch("keanu.abilities.world.corrections._STYLE_FILE", style_file):
                log_correction("test.py", "x = 'a'", 'x = "a"')
                log_correction("test2.py", "y = 'b'", 'y = "b"')

                corrections = load_corrections()

        assert len(corrections) == 2
        assert corrections[0].pattern == "prefer_double_quotes"

    def test_correction_patterns(self, tmp_path):
        corrections_file = tmp_path / "corrections.jsonl"
        style_file = tmp_path / "style_prefs.json"

        with patch("keanu.abilities.world.corrections._CORRECTIONS_FILE", corrections_file):
            with patch("keanu.abilities.world.corrections._STYLE_FILE", style_file):
                log_correction("a.py", "x = 'a'", 'x = "a"')
                log_correction("b.py", "y = 'b'", 'y = "b"')
                log_correction("c.py", "z = 'c'", 'z = "c"')

                patterns = correction_patterns(min_count=2)

        assert "prefer_double_quotes" in patterns
        assert patterns["prefer_double_quotes"] >= 2


class TestStylePrefs:

    def test_load_empty(self, tmp_path):
        style_file = tmp_path / "style_prefs.json"
        with patch("keanu.abilities.world.corrections._STYLE_FILE", style_file):
            assert load_style_prefs() == []

    def test_prefs_accumulate(self, tmp_path):
        corrections_file = tmp_path / "corrections.jsonl"
        style_file = tmp_path / "style_prefs.json"

        with patch("keanu.abilities.world.corrections._CORRECTIONS_FILE", corrections_file):
            with patch("keanu.abilities.world.corrections._STYLE_FILE", style_file):
                # log same pattern 3 times
                for i in range(3):
                    log_correction(f"f{i}.py", f"x{i} = 'a'", f'x{i} = "a"')

                prefs = load_style_prefs()

        assert len(prefs) == 1
        assert prefs[0].count == 3
        assert prefs[0].confidence > 0.7

    def test_prompt_injection(self, tmp_path):
        style_file = tmp_path / "style_prefs.json"
        style_file.write_text(json.dumps([{
            "rule": "prefer_double_quotes",
            "examples": [],
            "count": 5,
            "confidence": 0.9,
        }]))

        with patch("keanu.abilities.world.corrections._STYLE_FILE", style_file):
            injection = style_prompt_injection()

        assert "prefer_double_quotes" in injection
        assert "5x" in injection

    def test_low_confidence_filtered(self, tmp_path):
        style_file = tmp_path / "style_prefs.json"
        style_file.write_text(json.dumps([{
            "rule": "weak_pref",
            "examples": [],
            "count": 1,
            "confidence": 0.3,
        }]))

        with patch("keanu.abilities.world.corrections._STYLE_FILE", style_file):
            injection = style_prompt_injection()

        assert injection == ""


class TestCorrection:

    def test_to_dict(self):
        c = Correction(
            timestamp=1.0, file="test.py",
            old_code="old", new_code="new",
            pattern="fix", context="ctx",
        )
        d = c.to_dict()
        assert d["file"] == "test.py"
        assert d["pattern"] == "fix"


class TestHelpers:

    def test_is_camel(self):
        assert _is_camel("myFunc")
        assert not _is_camel("my_func")

    def test_is_snake(self):
        assert _is_snake("my_func")
        assert not _is_snake("myFunc")
