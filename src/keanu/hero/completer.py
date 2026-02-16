"""completer.py - tab completion and history for the REPL.

provides readline-based tab completion for slash commands,
ability names, file paths, and mode names.

in the world: the quick fingers. type less, do more.
"""

import os
import readline
from pathlib import Path

from keanu.paths import keanu_home


_HISTORY_FILE = keanu_home() / "repl_history"
_MAX_HISTORY = 1000


# ============================================================
# COMPLETION
# ============================================================

class KeanuCompleter:
    """tab completer for the keanu REPL."""

    def __init__(self):
        self.matches: list[str] = []
        self._slash_commands = [
            "/help", "/quit", "/q", "/exit",
            "/abilities", "/mode", "/explore",
            "/craft", "/prove", "/do",
            "/model", "/legend",
            "/history", "/clear", "/cost",
            "/health", "/metrics",
        ]
        self._modes = ["do", "craft", "prove", "explore"]
        self._legends: list[str] = []
        self._abilities: list[str] = []

    def refresh_abilities(self):
        """refresh the list of abilities for completion."""
        try:
            from keanu.abilities import list_abilities
            self._abilities = [a["name"] for a in list_abilities()]
        except Exception:
            pass

    def refresh_legends(self):
        """refresh the list of legends for completion."""
        try:
            from keanu.legends import list_legends
            self._legends = list_legends()
        except Exception:
            pass

    def complete(self, text: str, state: int) -> str | None:
        """readline completion function."""
        if state == 0:
            line = readline.get_line_buffer()
            self.matches = self._get_matches(line, text)
        try:
            return self.matches[state]
        except IndexError:
            return None

    def _get_matches(self, line: str, text: str) -> list[str]:
        """get completion matches for the current input."""
        stripped = line.lstrip()

        # completing a slash command
        if stripped.startswith("/"):
            parts = stripped.split(None, 1)
            cmd = parts[0] if parts else ""

            # completing the command itself
            if len(parts) <= 1 and not stripped.endswith(" "):
                return [c + " " for c in self._slash_commands if c.startswith(text)]

            # completing argument to a command
            if cmd == "/mode":
                return [m + " " for m in self._modes if m.startswith(text)]
            elif cmd == "/legend":
                if not self._legends:
                    self.refresh_legends()
                return [l + " " for l in self._legends if l.startswith(text)]
            elif cmd == "/model":
                models = ["claude-opus-4-6", "claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001"]
                return [m + " " for m in models if m.startswith(text)]

        # completing a file path
        if text and (text.startswith("./") or text.startswith("/") or "/" in text or text.startswith("~")):
            return self._complete_path(text)

        # completing an ability name (for general tasks)
        if not self._abilities:
            self.refresh_abilities()
        ability_matches = [a + " " for a in self._abilities if a.startswith(text)]
        if ability_matches:
            return ability_matches

        return []

    def _complete_path(self, text: str) -> list[str]:
        """complete file paths."""
        expanded = os.path.expanduser(text)
        if os.path.isdir(expanded):
            dirpath = expanded
            prefix = ""
        else:
            dirpath = os.path.dirname(expanded) or "."
            prefix = os.path.basename(expanded)

        try:
            entries = os.listdir(dirpath)
        except OSError:
            return []

        matches = []
        for entry in entries:
            if entry.startswith(".") and not prefix.startswith("."):
                continue
            if entry.startswith(prefix):
                full = os.path.join(dirpath, entry)
                display = os.path.join(os.path.dirname(text) if "/" in text else "", entry)
                if os.path.isdir(full):
                    matches.append(display + "/")
                else:
                    matches.append(display + " ")

        return matches


# ============================================================
# HISTORY
# ============================================================

def load_history():
    """load REPL history from file."""
    _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        if _HISTORY_FILE.exists():
            readline.read_history_file(str(_HISTORY_FILE))
    except (OSError, FileNotFoundError):
        pass


def save_history():
    """save REPL history to file."""
    try:
        readline.set_history_length(_MAX_HISTORY)
        readline.write_history_file(str(_HISTORY_FILE))
    except OSError:
        pass


def search_history(query: str, limit: int = 20) -> list[str]:
    """search REPL history for matching entries."""
    matches = []
    n = readline.get_current_history_length()
    for i in range(n, 0, -1):
        item = readline.get_history_item(i)
        if item and query.lower() in item.lower():
            if item not in matches:
                matches.append(item)
            if len(matches) >= limit:
                break
    return matches


def clear_history():
    """clear REPL history."""
    readline.clear_history()
    try:
        _HISTORY_FILE.unlink(missing_ok=True)
    except OSError:
        pass


# ============================================================
# SETUP
# ============================================================

def setup_readline():
    """configure readline for the keanu REPL."""
    completer = KeanuCompleter()

    readline.set_completer(completer.complete)
    readline.set_completer_delims(" \t\n")
    readline.parse_and_bind("tab: complete")

    # macOS uses libedit, not GNU readline
    if "libedit" in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")

    load_history()
    return completer
