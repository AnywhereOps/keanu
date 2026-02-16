"""context.py - the agent's awareness of what it knows.

tracks which files the agent has read, how they relate to each other,
and what's most relevant right now. knows when context is getting full
and what to keep vs summarize.

in the world: the map you've been drawing as you walk. not the territory,
but your sketch of what you've seen so far.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FileContext:
    """what the agent knows about one file."""
    path: str
    size: int = 0           # chars
    lines: int = 0
    read_at_turn: int = 0
    modified: bool = False
    summary: str = ""       # compressed version when context is tight


@dataclass
class ContextManager:
    """tracks what the agent knows about the codebase this session.

    knows which files were read, their sizes, who imports who.
    can tell you what's most relevant right now and when you're
    running out of room.
    """
    files: dict = field(default_factory=dict)     # path -> FileContext
    import_graph: dict = field(default_factory=dict)  # path -> [paths it imports]
    reverse_graph: dict = field(default_factory=dict)  # path -> [paths that import it]
    token_budget: int = 100_000  # rough token budget
    tokens_used: int = 0

    def note_file(self, path: str, content: str = "", turn: int = 0):
        """record that the agent read a file."""
        fc = FileContext(
            path=path,
            size=len(content),
            lines=content.count("\n") + 1 if content else 0,
            read_at_turn=turn,
        )
        self.files[path] = fc
        self.tokens_used += len(content) // 4  # rough token estimate

    def note_modified(self, path: str):
        """mark a file as modified by the agent."""
        if path in self.files:
            self.files[path].modified = True

    def build_imports(self, root: str = "."):
        """build the import graph for files we've read.

        uses the deps module if available. lightweight, only maps
        files the agent has actually touched.
        """
        try:
            from keanu.analysis.deps import build_import_graph
            graph = build_import_graph(root)
            edges = graph.get("edges", [])
            for src, dst in edges:
                self.import_graph.setdefault(src, []).append(dst)
                self.reverse_graph.setdefault(dst, []).append(src)
        except Exception:
            pass

    def related_to(self, path: str) -> list[str]:
        """files related to this path (importers + imports).

        when you edit file A, these are the files that might break or
        that you might want to check.
        """
        related = set()
        # normalize path for matching
        norm = _normalize(path)
        for key in self.import_graph:
            if _normalize(key) == norm:
                related.update(self.import_graph[key])
        for key in self.reverse_graph:
            if _normalize(key) == norm:
                related.update(self.reverse_graph[key])
        # also check direct matches
        related.update(self.import_graph.get(path, []))
        related.update(self.reverse_graph.get(path, []))
        related.discard(path)
        related.discard(norm)
        return sorted(related)

    def importers_of(self, path: str) -> list[str]:
        """who imports this file? if you change it, these might break."""
        norm = _normalize(path)
        result = set()
        result.update(self.reverse_graph.get(path, []))
        result.update(self.reverse_graph.get(norm, []))
        return sorted(result)

    def budget_remaining(self) -> float:
        """fraction of token budget remaining (0.0 to 1.0)."""
        if self.token_budget <= 0:
            return 0.0
        return max(0.0, 1.0 - (self.tokens_used / self.token_budget))

    def is_tight(self) -> bool:
        """true when context budget is getting low (< 20% remaining)."""
        return self.budget_remaining() < 0.2

    def priority_files(self, n: int = 10) -> list[str]:
        """the most relevant files right now.

        modified files first, then most recently read.
        """
        modified = [(p, fc) for p, fc in self.files.items() if fc.modified]
        unmodified = [(p, fc) for p, fc in self.files.items() if not fc.modified]

        # sort each group by recency
        modified.sort(key=lambda x: x[1].read_at_turn, reverse=True)
        unmodified.sort(key=lambda x: x[1].read_at_turn, reverse=True)

        result = [p for p, _ in modified] + [p for p, _ in unmodified]
        return result[:n]

    def known_files(self) -> list[str]:
        """all files the agent has read."""
        return sorted(self.files.keys())

    def summary(self) -> str:
        """what does the agent know right now?"""
        total = len(self.files)
        modified = sum(1 for fc in self.files.values() if fc.modified)
        budget = f"{self.budget_remaining():.0%}"
        return (
            f"{total} files read ({modified} modified). "
            f"context budget: {budget} remaining."
        )

    def context_for_prompt(self) -> str:
        """build context string about what files the agent knows.

        injected into the prompt so the agent has awareness of its
        own knowledge state.
        """
        if not self.files:
            return ""

        lines = [f"[CONTEXT] {self.summary()}"]

        if self.is_tight():
            lines.append("[CONTEXT] Budget is tight. Consider summarizing older reads.")

        modified = [p for p, fc in self.files.items() if fc.modified]
        if modified:
            lines.append(f"[CONTEXT] Modified files: {', '.join(modified[:10])}")

        return "\n".join(lines)


def _normalize(path: str) -> str:
    """normalize a path for comparison."""
    return str(Path(path)).replace("\\", "/")
