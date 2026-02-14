"""
gitstore.py - Git-backed memberberry storage.

Wraps MemberberryStore. Same interface, adds git ops.
JSONL append-only, month-sharded, namespace per agent.
Tombstones for forget. COEF DNS dedup.

Storage layout:
    ~/memberberries/
        drew/2026-02.jsonl
        claude-keanu/2026-02.jsonl
        shared/2026-02.jsonl
"""

import json
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from dataclasses import asdict

from .memberberry import (
    Memory,
    Plan,
    MemberberryStore,
    SHARED_DIR,
)


class GitStore(MemberberryStore):
    """MemberberryStore + git. Reads from all namespaces, writes to one."""

    def __init__(self, namespace: str = "drew", repo_dir: Path = None):
        super().__init__()
        self.namespace = namespace
        self.repo_dir = repo_dir or SHARED_DIR
        self._ensure_repo()
        self._sync()
        self._shared_memories: list[dict] = self._load_all_shared()

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

    def _sync(self):
        if self._has_remote():
            self._git("pull", "--rebase", check=False)

    def _commit_and_push(self, message: str):
        self._git("add", "-A")
        result = self._git("diff", "--cached", "--quiet", check=False)
        if result.returncode != 0:
            self._git("commit", "-m", message)
            if self._has_remote():
                self._git("push", check=False)

    def _shard_path(self, namespace: str = None) -> Path:
        ns = namespace or self.namespace
        month = datetime.now().strftime("%Y-%m")
        return self.repo_dir / ns / f"{month}.jsonl"

    def _load_all_shared(self) -> list[dict]:
        all_memories = []
        for jsonl_file in self.repo_dir.rglob("*.jsonl"):
            all_memories.extend(self._load_jsonl(jsonl_file))
        return all_memories

    def _is_shared_duplicate(self, content: str) -> bool:
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        for m in self._shared_memories:
            if hashlib.sha256(m.get("content", "").encode()).hexdigest()[:16] == content_hash:
                return True
        return False

    # -- Overrides --

    def remember(self, memory: Memory) -> str:
        """Store to JSONL in namespace dir + git commit."""
        if self._is_shared_duplicate(memory.content):
            for m in self._shared_memories:
                if hashlib.sha256(m.get("content", "").encode()).hexdigest()[:16] == \
                   hashlib.sha256(memory.content.encode()).hexdigest()[:16]:
                    return m.get("id", memory.id)
            return memory.id

        record = asdict(memory)
        record["visibility"] = "shared"
        record["namespace"] = self.namespace

        shard = self._shard_path()
        self._append_jsonl(shard, record)
        self._shared_memories.append(record)
        self._commit_and_push(f"remember: {memory.memory_type} - {memory.content[:60]}")
        return memory.id

    def recall(self, query: str = "", tags: list = None,
               memory_type: str = None, limit: int = None) -> list[dict]:
        """Recall from all namespaces (git pull first)."""
        self._sync()
        self._shared_memories = self._load_all_shared()

        limit = limit or self.config.get("max_recall", 10)
        candidates = []

        for m_dict in self._shared_memories:
            clean = {k: v for k, v in m_dict.items() if not k.startswith("_")}
            try:
                m = Memory(**{k: v for k, v in clean.items()
                            if k in Memory.__dataclass_fields__})
            except TypeError:
                continue

            if memory_type and m.memory_type != memory_type:
                continue

            score = m.relevance_score(query_tags=tags, query_text=query)
            candidates.append((score, m_dict))

        candidates.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, m_dict in candidates[:limit]:
            m_dict["_relevance_score"] = score
            results.append(m_dict)

        return results

    def deprioritize(self, memory_id: str) -> bool:
        """Lower importance to 1. Nothing is ever deleted. Append update to shard."""
        for m in self._shared_memories:
            if m.get("id") == memory_id:
                m["importance"] = 1
                update = {"id": memory_id, "importance": 1, "_update": True,
                          "_updated_at": datetime.now().isoformat()}
                shard = self._shard_path()
                self._append_jsonl(shard, update)
                self._commit_and_push(f"deprioritize: {memory_id}")
                return True
        return False

    def sync(self):
        """Pull latest from remote."""
        self._sync()
        self._shared_memories = self._load_all_shared()

    def stats(self) -> dict:
        """Stats across local + shared."""
        local = super().stats()
        shared_type_counts = {}
        for m in self._shared_memories:
            t = m.get("memory_type", "unknown")
            shared_type_counts[t] = shared_type_counts.get(t, 0) + 1

        namespaces = set()
        for m in self._shared_memories:
            namespaces.add(m.get("namespace", "unknown"))

        local["shared_memories"] = len(self._shared_memories)
        local["shared_by_type"] = shared_type_counts
        local["namespaces"] = sorted(namespaces)
        return local
