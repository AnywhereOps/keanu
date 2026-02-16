"""diff.py - structured diff analysis.

parse unified diffs, compute stats, detect patterns (renames, moves,
refactors). works with git diff output and raw unified diffs.

in the world: the microscope on change. not just what changed,
but why it changed and what it means.
"""

import re
from dataclasses import dataclass, field


@dataclass
class FileDiff:
    """diff for a single file."""
    path: str
    old_path: str = ""
    status: str = "modified"  # added, deleted, modified, renamed
    additions: int = 0
    deletions: int = 0
    hunks: list["Hunk"] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions

    @property
    def is_rename(self) -> bool:
        return self.status == "renamed"


@dataclass
class Hunk:
    """a single diff hunk."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header: str = ""
    lines: list[str] = field(default_factory=list)
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)


@dataclass
class DiffStats:
    """aggregate statistics for a diff."""
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    files_added: int = 0
    files_deleted: int = 0
    files_modified: int = 0
    files_renamed: int = 0

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions

    def summary(self) -> str:
        parts = [f"{self.files_changed} files changed"]
        if self.additions:
            parts.append(f"{self.additions} insertions(+)")
        if self.deletions:
            parts.append(f"{self.deletions} deletions(-)")
        return ", ".join(parts)


# ============================================================
# DIFF PARSING
# ============================================================

def parse_diff(diff_text: str) -> list[FileDiff]:
    """parse a unified diff into structured FileDiff objects."""
    files = []
    current_file = None
    current_hunk = None

    for line in diff_text.split("\n"):
        # new file header
        if line.startswith("diff --git"):
            if current_file:
                files.append(current_file)
            # extract paths
            match = re.match(r'diff --git a/(.+) b/(.+)', line)
            if match:
                old_path = match.group(1)
                new_path = match.group(2)
                current_file = FileDiff(path=new_path, old_path=old_path)
            else:
                current_file = FileDiff(path="unknown")
            current_hunk = None
            continue

        if current_file is None:
            continue

        # file status indicators
        if line.startswith("new file"):
            current_file.status = "added"
        elif line.startswith("deleted file"):
            current_file.status = "deleted"
        elif line.startswith("rename from"):
            current_file.status = "renamed"
            current_file.old_path = line.split("rename from ", 1)[1]
        elif line.startswith("rename to"):
            current_file.path = line.split("rename to ", 1)[1]

        # hunk header
        elif line.startswith("@@"):
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)', line)
            if match:
                current_hunk = Hunk(
                    old_start=int(match.group(1)),
                    old_count=int(match.group(2) or 1),
                    new_start=int(match.group(3)),
                    new_count=int(match.group(4) or 1),
                    header=match.group(5).strip(),
                )
                current_file.hunks.append(current_hunk)

        # diff lines
        elif current_hunk is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current_file.additions += 1
                current_hunk.added_lines.append(line[1:])
                current_hunk.lines.append(line)
            elif line.startswith("-") and not line.startswith("---"):
                current_file.deletions += 1
                current_hunk.removed_lines.append(line[1:])
                current_hunk.lines.append(line)
            elif line.startswith(" "):
                current_hunk.lines.append(line)

    if current_file:
        files.append(current_file)

    return files


def diff_stats(files: list[FileDiff]) -> DiffStats:
    """compute aggregate statistics from parsed diffs."""
    stats = DiffStats(files_changed=len(files))

    for f in files:
        stats.additions += f.additions
        stats.deletions += f.deletions

        if f.status == "added":
            stats.files_added += 1
        elif f.status == "deleted":
            stats.files_deleted += 1
        elif f.status == "renamed":
            stats.files_renamed += 1
        else:
            stats.files_modified += 1

    return stats


# ============================================================
# DIFF ANALYSIS
# ============================================================

def find_moved_code(files: list[FileDiff], min_lines: int = 3) -> list[dict]:
    """detect code that was moved between files.

    looks for blocks of removed lines in one file that appear
    as added lines in another file.
    """
    # collect all added and removed blocks
    removed_blocks: list[tuple[str, list[str]]] = []
    added_blocks: list[tuple[str, list[str]]] = []

    for f in files:
        for hunk in f.hunks:
            if len(hunk.removed_lines) >= min_lines:
                removed_blocks.append((f.path, hunk.removed_lines))
            if len(hunk.added_lines) >= min_lines:
                added_blocks.append((f.path, hunk.added_lines))

    moves = []
    for rm_file, rm_lines in removed_blocks:
        rm_set = set(line.strip() for line in rm_lines if line.strip())
        for add_file, add_lines in added_blocks:
            if rm_file == add_file:
                continue
            add_set = set(line.strip() for line in add_lines if line.strip())
            overlap = rm_set & add_set
            if len(overlap) >= min_lines:
                moves.append({
                    "from": rm_file,
                    "to": add_file,
                    "lines": len(overlap),
                })

    return moves


def classify_change(file_diff: FileDiff) -> str:
    """classify the type of change in a file diff.

    returns: new_feature, bug_fix, refactor, config, test, docs, style
    """
    path = file_diff.path.lower()

    if file_diff.status == "added":
        if "test" in path:
            return "test"
        return "new_feature"
    if file_diff.status == "deleted":
        return "removal"

    # look at the content
    added_text = " ".join(
        line for hunk in file_diff.hunks for line in hunk.added_lines
    ).lower()
    removed_text = " ".join(
        line for hunk in file_diff.hunks for line in hunk.removed_lines
    ).lower()

    if "test" in path:
        return "test"
    if path.endswith((".md", ".rst", ".txt")):
        return "docs"
    if path.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg")):
        return "config"

    # heuristic: if mostly additions with few deletions, likely new feature
    if file_diff.additions > 0 and file_diff.deletions == 0:
        return "new_feature"
    if file_diff.additions == 0 and file_diff.deletions > 0:
        return "removal"

    # if similar line count changed, likely refactor
    if abs(file_diff.additions - file_diff.deletions) < max(file_diff.additions, file_diff.deletions) * 0.3:
        return "refactor"

    if any(w in added_text for w in ["fix", "bug", "patch", "error", "exception"]):
        return "bug_fix"

    return "modification"


def format_diff_summary(files: list[FileDiff]) -> str:
    """format a human-readable diff summary."""
    stats = diff_stats(files)
    lines = [stats.summary(), ""]

    for f in files:
        status = {"added": "+", "deleted": "-", "modified": "M", "renamed": "R"}
        icon = status.get(f.status, "?")
        change_type = classify_change(f)
        lines.append(f"  [{icon}] {f.path} (+{f.additions}/-{f.deletions}) [{change_type}]")

    return "\n".join(lines)
