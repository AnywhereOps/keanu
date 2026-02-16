"""cache.py - session-scoped caching for file reads and AST parses.

avoids re-reading and re-parsing files the agent has already seen.
invalidates on write. lives in memory, dies with the session.

in the world: you don't reopen a book every time you want to check a page
you already read. you remember what was there.
"""

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any


@dataclass
class CacheEntry:
    """a cached item."""
    key: str
    value: Any
    size: int = 0       # rough size in bytes
    hits: int = 0
    hash: str = ""      # content hash for invalidation


class FileCache:
    """session-scoped cache for file reads.

    caches file contents by path. invalidates when the file is written.
    tracks hit counts for diagnostics.
    """

    def __init__(self, max_entries: int = 500, max_size: int = 10_000_000):
        self._entries: dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self._max_size = max_size
        self._total_size = 0
        self._total_hits = 0
        self._total_misses = 0

    def get(self, path: str) -> Optional[str]:
        """get cached file content. returns None on miss."""
        entry = self._entries.get(path)
        if entry is None:
            self._total_misses += 1
            return None

        # check if file changed on disk
        try:
            current_hash = _file_hash(path)
            if current_hash != entry.hash:
                self.invalidate(path)
                self._total_misses += 1
                return None
        except OSError:
            self.invalidate(path)
            self._total_misses += 1
            return None

        entry.hits += 1
        self._total_hits += 1
        return entry.value

    def put(self, path: str, content: str):
        """cache file content."""
        size = len(content)

        # evict if we'd exceed limits
        if len(self._entries) >= self._max_entries:
            self._evict_lru()

        while self._total_size + size > self._max_size and self._entries:
            self._evict_lru()

        try:
            content_hash = _file_hash(path)
        except OSError:
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        self._entries[path] = CacheEntry(
            key=path, value=content, size=size,
            hash=content_hash,
        )
        self._total_size += size

    def invalidate(self, path: str):
        """remove a file from cache (after write/edit)."""
        entry = self._entries.pop(path, None)
        if entry:
            self._total_size -= entry.size

    def invalidate_all(self):
        """clear the entire cache."""
        self._entries.clear()
        self._total_size = 0

    def _evict_lru(self):
        """evict the least recently used entry (fewest hits)."""
        if not self._entries:
            return
        least_used = min(self._entries.values(), key=lambda e: e.hits)
        self.invalidate(least_used.key)

    def stats(self) -> dict:
        """cache statistics."""
        total_requests = self._total_hits + self._total_misses
        hit_rate = self._total_hits / total_requests if total_requests > 0 else 0.0
        return {
            "entries": len(self._entries),
            "size_bytes": self._total_size,
            "hits": self._total_hits,
            "misses": self._total_misses,
            "hit_rate": hit_rate,
        }

    def __contains__(self, path: str) -> bool:
        return path in self._entries


class ASTCache:
    """cache for parsed ASTs.

    avoids re-parsing files. invalidates when the file cache invalidates.
    """

    def __init__(self, file_cache: FileCache = None):
        self._file_cache = file_cache or FileCache()
        self._asts: dict[str, CacheEntry] = {}

    def get(self, path: str) -> Optional[ast.Module]:
        """get cached AST. returns None on miss."""
        entry = self._asts.get(path)
        if entry is None:
            return None

        # check if source changed
        if path not in self._file_cache:
            # file not in file cache means it may have changed
            self._asts.pop(path, None)
            return None

        entry.hits += 1
        return entry.value

    def put(self, path: str, tree: ast.Module):
        """cache a parsed AST."""
        self._asts[path] = CacheEntry(key=path, value=tree)

    def parse(self, path: str) -> Optional[ast.Module]:
        """parse a file, using cache if available."""
        cached = self.get(path)
        if cached is not None:
            return cached

        # try file cache first
        content = self._file_cache.get(path)
        if content is None:
            try:
                content = Path(path).read_text()
                self._file_cache.put(path, content)
            except (OSError, UnicodeDecodeError):
                return None

        try:
            tree = ast.parse(content)
            self.put(path, tree)
            return tree
        except SyntaxError:
            return None

    def invalidate(self, path: str):
        """remove a file's AST from cache."""
        self._asts.pop(path, None)
        self._file_cache.invalidate(path)


class SymbolCache:
    """cache for symbol lookups.

    caches find_definition results keyed by (name, root).
    invalidated when any file changes.
    """

    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._dirty = False

    def get(self, key: str) -> Optional[Any]:
        """get cached result."""
        if self._dirty:
            self._cache.clear()
            self._dirty = False
            return None
        return self._cache.get(key)

    def put(self, key: str, value: Any):
        """cache a result."""
        self._cache[key] = value

    def mark_dirty(self):
        """mark all entries as potentially stale."""
        self._dirty = True

    def clear(self):
        """clear all entries."""
        self._cache.clear()
        self._dirty = False


def _file_hash(path: str) -> str:
    """quick hash of file for change detection. uses mtime + size."""
    p = Path(path)
    stat = p.stat()
    key = f"{stat.st_mtime}:{stat.st_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
