"""session.py - working memory for the agent loop.

short-term memory that lives for one session. tracks decisions made,
files touched, errors seen, approaches tried. different from memberberry
(long-term). this is the agent's scratch pad.

in the world: what you remember from today. not what you know from years.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Decision:
    """a decision made during this session."""
    what: str
    why: str
    turn: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class Attempt:
    """something the agent tried."""
    action: str
    target: str
    result: str   # "ok", "failed", "partial"
    detail: str = ""
    turn: int = 0


@dataclass
class Session:
    """working memory for one agent session.

    tracks everything the agent has done, decided, and learned this session.
    lives in memory only. no persistence. dies when the loop ends.
    """
    task: str = ""
    files_read: dict = field(default_factory=dict)      # path -> turn last read
    files_written: dict = field(default_factory=dict)    # path -> turn last written
    decisions: list = field(default_factory=list)        # Decision objects
    attempts: list = field(default_factory=list)         # Attempt objects
    errors_seen: list = field(default_factory=list)      # error strings
    context_notes: list = field(default_factory=list)    # free-form notes
    _action_history: list = field(default_factory=list)  # (action, target, turn) per turn
    _result_cache: dict = field(default_factory=dict)    # (action, target) -> last result text

    def note_read(self, path: str, turn: int = 0):
        """record that a file was read."""
        self.files_read[path] = turn

    def note_write(self, path: str, turn: int = 0):
        """record that a file was written."""
        self.files_written[path] = turn

    def note_decision(self, what: str, why: str, turn: int = 0):
        """record a decision made."""
        self.decisions.append(Decision(what=what, why=why, turn=turn))

    def note_attempt(self, action: str, target: str, result: str,
                     detail: str = "", turn: int = 0):
        """record something the agent tried."""
        self.attempts.append(Attempt(
            action=action, target=target, result=result,
            detail=detail, turn=turn,
        ))

    def note_error(self, error: str):
        """record an error seen this session."""
        if error not in self.errors_seen:
            self.errors_seen.append(error)

    def note(self, text: str):
        """add a free-form note."""
        self.context_notes.append(text)

    def note_action(self, action: str, target: str, turn: int = 0):
        """record an action for consecutive-action detection."""
        self._action_history.append((action, target, turn))

    def consecutive_count(self, action: str, target: str) -> int:
        """how many times in a row has this (action, target) been most recent?"""
        count = 0
        for a, t, _ in reversed(self._action_history):
            if a == action and t == target:
                count += 1
            else:
                break
        return count

    def note_action_result(self, action: str, target: str, result: str):
        """cache the result of an action for potential replay."""
        self._result_cache[(action, target)] = result

    def last_result_for(self, action: str, target: str) -> Optional[str]:
        """get the cached result from the last time this (action, target) ran."""
        return self._result_cache.get((action, target))

    def was_tried(self, action: str, target: str) -> Optional[Attempt]:
        """check if an approach was already tried. returns the attempt or None."""
        for a in self.attempts:
            if a.action == action and a.target == target:
                return a
        return None

    def failed_attempts_for(self, target: str) -> list[Attempt]:
        """get all failed attempts for a target."""
        return [a for a in self.attempts if a.target == target and a.result == "failed"]

    def files_touched(self) -> list[str]:
        """all files that were read or written."""
        all_files = set(self.files_read.keys()) | set(self.files_written.keys())
        return sorted(all_files)

    def summary(self) -> str:
        """one-paragraph summary of this session."""
        parts = []
        if self.task:
            parts.append(f"task: {self.task}")
        if self.files_read:
            parts.append(f"read {len(self.files_read)} files")
        if self.files_written:
            parts.append(f"wrote {len(self.files_written)} files")
        if self.decisions:
            parts.append(f"{len(self.decisions)} decisions made")
        if self.attempts:
            ok = sum(1 for a in self.attempts if a.result == "ok")
            fail = sum(1 for a in self.attempts if a.result == "failed")
            parts.append(f"{ok} succeeded, {fail} failed")
        if self.errors_seen:
            parts.append(f"{len(self.errors_seen)} unique errors")
        return ". ".join(parts) + "." if parts else "empty session."

    def context_for_prompt(self) -> str:
        """build context string to inject into the agent's prompt.

        gives the agent awareness of what it's already done this session
        so it doesn't repeat itself or forget what it learned.
        """
        lines = []

        if self.decisions:
            lines.append("Decisions so far:")
            for d in self.decisions[-5:]:  # last 5
                lines.append(f"  - {d.what} (because: {d.why})")

        failed = [a for a in self.attempts if a.result == "failed"]
        if failed:
            lines.append("Failed attempts (avoid repeating):")
            for a in failed[-5:]:
                detail = f": {a.detail}" if a.detail else ""
                lines.append(f"  - {a.action} on {a.target}{detail}")

        if self.errors_seen:
            lines.append("Errors encountered:")
            for e in self.errors_seen[-3:]:
                lines.append(f"  - {e[:100]}")

        if self.context_notes:
            lines.append("Notes:")
            for n in self.context_notes[-3:]:
                lines.append(f"  - {n}")

        return "\n".join(lines)
