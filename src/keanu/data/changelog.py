"""changelog.py - changelog generation from git history.

generates changelogs from git commits. groups by type (feat, fix, chore),
extracts breaking changes, links PRs, creates release notes.

in the world: the record keeper. every change told in a story
that makes sense to humans, not just git log.
"""

import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CommitInfo:
    """parsed git commit."""
    hash: str
    short_hash: str
    subject: str
    body: str = ""
    author: str = ""
    date: str = ""
    commit_type: str = ""       # feat, fix, chore, docs, refactor, test, style, perf, ci, build
    scope: str = ""
    breaking: bool = False
    pr_number: str = ""

    def __post_init__(self):
        self._parse_conventional()

    def _parse_conventional(self):
        """parse conventional commit format: type(scope): subject."""
        match = re.match(r'^(\w+)(?:\(([^)]+)\))?(!?):\s*(.+)', self.subject)
        if match:
            self.commit_type = match.group(1).lower()
            self.scope = match.group(2) or ""
            if match.group(3) == "!":
                self.breaking = True
            self.subject = match.group(4)
        else:
            self.commit_type = _guess_type(self.subject)

        # check for PR references
        pr_match = re.search(r'#(\d+)', self.subject)
        if pr_match:
            self.pr_number = pr_match.group(1)

        # check for BREAKING CHANGE in body
        if "BREAKING CHANGE" in self.body or "BREAKING-CHANGE" in self.body:
            self.breaking = True


def _guess_type(subject: str) -> str:
    """guess commit type from subject when not using conventional format."""
    s = subject.lower()
    if any(w in s for w in ["fix", "bug", "patch", "repair", "resolve"]):
        return "fix"
    if any(w in s for w in ["add", "feat", "feature", "implement", "new"]):
        return "feat"
    if any(w in s for w in ["doc", "readme", "comment"]):
        return "docs"
    if any(w in s for w in ["test", "spec", "coverage"]):
        return "test"
    if any(w in s for w in ["refactor", "rename", "move", "extract", "clean"]):
        return "refactor"
    if any(w in s for w in ["style", "format", "lint"]):
        return "style"
    if any(w in s for w in ["perf", "speed", "fast", "optim"]):
        return "perf"
    if any(w in s for w in ["ci", "pipeline", "workflow", "deploy"]):
        return "ci"
    if any(w in s for w in ["build", "dep", "upgrade", "bump"]):
        return "build"
    return "chore"


# ============================================================
# GIT LOG PARSING
# ============================================================

def get_commits(root: str = ".", since: str = "", until: str = "",
                limit: int = 100) -> list[CommitInfo]:
    """get git commits, parsed into structured format."""
    cmd = ["git", "log", f"--max-count={limit}",
           "--format=%H%n%h%n%s%n%b%n%an%n%ai%n---END---"]

    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=root)
        if r.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, OSError):
        return []

    commits = []
    entries = r.stdout.split("---END---\n")

    for entry in entries:
        lines = entry.strip().split("\n")
        if len(lines) < 5:
            continue

        full_hash = lines[0]
        short_hash = lines[1]
        subject = lines[2]
        author = lines[-2] if len(lines) >= 6 else ""
        date = lines[-1] if len(lines) >= 6 else ""
        body = "\n".join(lines[3:-2]) if len(lines) > 6 else ""

        commits.append(CommitInfo(
            hash=full_hash,
            short_hash=short_hash,
            subject=subject,
            body=body.strip(),
            author=author,
            date=date,
        ))

    return commits


def get_tags(root: str = ".") -> list[dict]:
    """get git tags sorted by date."""
    try:
        r = subprocess.run(
            ["git", "tag", "--sort=-creatordate", "--format=%(refname:short) %(creatordate:short)"],
            capture_output=True, text=True, timeout=10, cwd=root,
        )
        if r.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, OSError):
        return []

    tags = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(None, 1)
        tags.append({
            "name": parts[0],
            "date": parts[1] if len(parts) > 1 else "",
        })

    return tags


# ============================================================
# CHANGELOG GENERATION
# ============================================================

TYPE_LABELS = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "docs": "Documentation",
    "refactor": "Refactoring",
    "test": "Tests",
    "style": "Style",
    "perf": "Performance",
    "ci": "CI/CD",
    "build": "Build",
    "chore": "Chores",
}

TYPE_ORDER = ["feat", "fix", "perf", "refactor", "docs", "test", "style", "ci", "build", "chore"]


def generate_changelog(root: str = ".", since: str = "", until: str = "",
                        limit: int = 100, title: str = "") -> str:
    """generate a markdown changelog from git history."""
    commits = get_commits(root, since=since, until=until, limit=limit)
    if not commits:
        return "No commits found.\n"

    # group by type
    groups: dict[str, list[CommitInfo]] = {}
    breaking = []

    for c in commits:
        groups.setdefault(c.commit_type, []).append(c)
        if c.breaking:
            breaking.append(c)

    # build markdown
    lines = []

    if title:
        lines.append(f"# {title}")
    else:
        lines.append("# Changelog")
    lines.append("")

    if breaking:
        lines.append("## BREAKING CHANGES")
        lines.append("")
        for c in breaking:
            scope = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {scope}{c.subject} ({c.short_hash})")
        lines.append("")

    for commit_type in TYPE_ORDER:
        if commit_type not in groups:
            continue
        label = TYPE_LABELS.get(commit_type, commit_type.capitalize())
        lines.append(f"## {label}")
        lines.append("")
        for c in groups[commit_type]:
            scope = f"**{c.scope}**: " if c.scope else ""
            pr = f" (#{c.pr_number})" if c.pr_number else ""
            lines.append(f"- {scope}{c.subject}{pr} ({c.short_hash})")
        lines.append("")

    return "\n".join(lines)


def generate_release_notes(root: str = ".", from_tag: str = "",
                            to_tag: str = "HEAD") -> str:
    """generate release notes between two tags."""
    since = ""
    if from_tag:
        # get date of the tag
        try:
            r = subprocess.run(
                ["git", "log", "-1", "--format=%ai", from_tag],
                capture_output=True, text=True, timeout=10, cwd=root,
            )
            if r.returncode == 0:
                since = r.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            pass

    title = f"Release {to_tag}" if to_tag != "HEAD" else "Unreleased Changes"
    return generate_changelog(root, since=since, title=title)


def commits_since_tag(root: str = ".") -> list[CommitInfo]:
    """get commits since the last tag."""
    tags = get_tags(root)
    if not tags:
        return get_commits(root, limit=50)

    last_tag = tags[0]["name"]
    try:
        r = subprocess.run(
            ["git", "log", f"{last_tag}..HEAD", "--format=%H%n%h%n%s%n%b%n%an%n%ai%n---END---"],
            capture_output=True, text=True, timeout=30, cwd=root,
        )
        if r.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, OSError):
        return []

    commits = []
    entries = r.stdout.split("---END---\n")
    for entry in entries:
        lines = entry.strip().split("\n")
        if len(lines) < 5:
            continue
        commits.append(CommitInfo(
            hash=lines[0],
            short_hash=lines[1],
            subject=lines[2],
            body="\n".join(lines[3:-2]).strip() if len(lines) > 6 else "",
            author=lines[-2] if len(lines) >= 6 else "",
            date=lines[-1] if len(lines) >= 6 else "",
        ))

    return commits
