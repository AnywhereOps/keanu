"""sessions.py - REPL session save and restore.

save the current REPL session state (mode, legend, history, context)
and restore it later. pick up where you left off.

in the world: the bookmark. close the book, come back tomorrow,
open to the same page.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_SESSIONS_DIR = keanu_home() / "sessions"


@dataclass
class SessionState:
    """snapshot of a REPL session."""
    name: str = ""
    mode: str = "do"
    legend: str = "creator"
    model: str = ""
    history: list[dict] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "mode": self.mode,
            "legend": self.legend,
            "model": self.model,
            "history": self.history[-100:],  # cap at 100 messages
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(
            name=data.get("name", ""),
            mode=data.get("mode", "do"),
            legend=data.get("legend", "creator"),
            model=data.get("model", ""),
            history=data.get("history", []),
            context=data.get("context", {}),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
        )


# ============================================================
# SAVE / RESTORE
# ============================================================

def save_session(state: SessionState, name: str = "") -> str:
    """save a session to disk. returns the session name."""
    if name:
        state.name = name
    if not state.name:
        state.name = f"session_{int(time.time())}"

    state.updated_at = time.time()

    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = _SESSIONS_DIR / f"{state.name}.json"
    path.write_text(json.dumps(state.to_dict(), indent=2) + "\n")
    return state.name


def load_session(name: str) -> SessionState:
    """load a session from disk."""
    path = _SESSIONS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"session not found: {name}")

    data = json.loads(path.read_text())
    return SessionState.from_dict(data)


def delete_session(name: str) -> bool:
    """delete a saved session."""
    path = _SESSIONS_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def list_sessions() -> list[dict]:
    """list all saved sessions with metadata."""
    if not _SESSIONS_DIR.is_dir():
        return []

    sessions = []
    for path in sorted(_SESSIONS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            sessions.append({
                "name": data.get("name", path.stem),
                "mode": data.get("mode", "do"),
                "legend": data.get("legend", "creator"),
                "messages": len(data.get("history", [])),
                "created_at": data.get("created_at", 0),
                "updated_at": data.get("updated_at", 0),
            })
        except (json.JSONDecodeError, OSError):
            pass

    return sorted(sessions, key=lambda s: -s.get("updated_at", 0))


def get_latest_session() -> SessionState | None:
    """get the most recently updated session."""
    sessions = list_sessions()
    if not sessions:
        return None
    return load_session(sessions[0]["name"])


def auto_save(state: SessionState) -> str:
    """auto-save the current session. uses 'autosave' name."""
    return save_session(state, name="autosave")


def auto_restore() -> SessionState | None:
    """restore the auto-saved session if it exists."""
    try:
        return load_session("autosave")
    except FileNotFoundError:
        return None
