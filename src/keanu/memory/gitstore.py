"""gitstore.py - git-backed log sink.

the hands that catch what the river carries. every log entry lands
in month-sharded JSONL under ~/memberberries/. one git commit per
session, not one per line.

in the world: the riverbank. append-only. nothing washes away.

storage layout:
    ~/memberberries/
        keanu/logs/2026-02.jsonl
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from keanu.paths import SHARED_DIR
from keanu.io import append_jsonl

# importance by log level. debug is background noise, error is a scar.
LOG_IMPORTANCE = {"debug": 1, "info": 3, "warn": 5, "error": 8}

# one hero for now. forge comes later.
DEFAULT_HERO = "wanderer"


class GitStore:
    """git-backed JSONL sink. append_log() writes, flush() commits."""

    def __init__(self, namespace: str = "keanu", repo_dir: Path = None):
        self.namespace = namespace
        self.repo_dir = repo_dir or SHARED_DIR
        self._session_hero = DEFAULT_HERO
        self._session_started = datetime.now().isoformat()
        self._log_count = 0
        self._ensure_repo()

    def _ensure_repo(self):
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        git_dir = self.repo_dir / ".git"
        if not git_dir.exists():
            self._git("init")

    def _git(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + list(args),
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
            check=check,
        )

    def _has_remote(self) -> bool:
        result = self._git("remote", check=False)
        return bool(result.stdout.strip())

    def _commit_and_push(self, message: str):
        self._git("add", "-A")
        result = self._git("diff", "--cached", "--quiet", check=False)
        if result.returncode != 0:
            self._git("commit", "-m", message)
            if self._has_remote():
                self._git("push", check=False)

    def _log_shard_path(self) -> Path:
        """where log entries go. month-sharded under namespace."""
        month = datetime.now().strftime("%Y-%m")
        return self.repo_dir / self.namespace / "logs" / f"{month}.jsonl"

    def append_log(self, subsystem: str, level: str, message: str, attrs: dict = None):
        """fast path. append-only, no dedup, no git commit.
        call flush() when the session ends."""
        entry = {
            "content": message,
            "memory_type": "log",
            "tags": [subsystem, level],
            "importance": LOG_IMPORTANCE.get(level, 3),
            "source": "log",
            "context": f"{subsystem}.{level}",
            "created_at": datetime.now().isoformat(),
            "id": f"{subsystem}-{datetime.now().strftime('%H%M%S%f')[:10]}",
            "session_hero": self._session_hero,
            "session_started": self._session_started,
        }
        if attrs:
            entry["attrs"] = attrs
        append_jsonl(self._log_shard_path(), entry)
        self._log_count += 1

    def flush(self):
        """batch commit all buffered log entries. one commit per session, not one per line."""
        if self._log_count > 0:
            self._commit_and_push(f"log: {self._session_hero} ({self._log_count} entries)")
            self._log_count = 0

    def sync(self):
        """pull latest from remote."""
        if self._has_remote():
            self._git("pull", "--rebase", check=False)
