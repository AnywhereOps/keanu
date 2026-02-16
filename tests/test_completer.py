"""tests for REPL tab completion."""

import readline
from unittest.mock import patch

from keanu.hero.completer import (
    KeanuCompleter, load_history, save_history, search_history,
    setup_readline,
)


class TestKeanuCompleter:

    def test_slash_commands(self):
        c = KeanuCompleter()
        with patch.object(readline, 'get_line_buffer', return_value="/he"):
            matches = c._get_matches("/he", "/he")
        assert "/help " in matches

    def test_mode_completion(self):
        c = KeanuCompleter()
        with patch.object(readline, 'get_line_buffer', return_value="/mode cr"):
            matches = c._get_matches("/mode cr", "cr")
        assert "craft " in matches

    def test_complete_returns_none_past_end(self):
        c = KeanuCompleter()
        # state > 0 without calling state=0 first should return None
        c.matches = ["foo"]
        assert c.complete("f", 1) is None

    def test_ability_completion(self):
        c = KeanuCompleter()
        c._abilities = ["read", "write", "search"]
        with patch.object(readline, 'get_line_buffer', return_value="rea"):
            matches = c._get_matches("rea", "rea")
        assert "read " in matches

    def test_legend_completion(self):
        c = KeanuCompleter()
        c._legends = ["creator", "friend", "architect"]
        with patch.object(readline, 'get_line_buffer', return_value="/legend cr"):
            matches = c._get_matches("/legend cr", "cr")
        assert "creator " in matches


class TestHistory:

    def test_load_save(self, tmp_path):
        history_file = tmp_path / "history"
        with patch("keanu.hero.completer._HISTORY_FILE", history_file):
            readline.clear_history()
            readline.add_history("test command")
            save_history()
            readline.clear_history()
            load_history()
            assert readline.get_current_history_length() >= 1

    def test_search(self):
        readline.clear_history()
        readline.add_history("read file.py")
        readline.add_history("write output.txt")
        readline.add_history("read another.py")
        results = search_history("read")
        assert len(results) >= 1
        assert any("read" in r for r in results)

    def test_search_empty(self):
        readline.clear_history()
        results = search_history("nonexistent")
        assert results == []


class TestSetup:

    def test_returns_completer(self, tmp_path):
        history_file = tmp_path / "history"
        with patch("keanu.hero.completer._HISTORY_FILE", history_file):
            completer = setup_readline()
        assert isinstance(completer, KeanuCompleter)
