"""Effort-aware TODO generator.

Scans a project for planning docs, filesystem state, and git history.
Categorizes gaps into cool/warm/hot effort levels and writes TODO.md.
"""

import os
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass, field


# Keywords that signal effort level from build plan descriptions
HOT_KEYWORDS = {"design", "build", "architect", "comprehensive", "engine", "pipeline", "end-to-end", "rewrite"}
WARM_KEYWORDS = {"port", "create", "write", "implement", "wire", "bridge", "connect", "update"}
COOL_KEYWORDS = {"stub", "config", "export", "rename", "fix", "add", "move", "remove", "clean"}


@dataclass
class Task:
    description: str
    effort: str  # "cool", "warm", "hot"
    source: str  # where this was detected from
    done: bool = False


@dataclass
class TodoScan:
    project_root: Path
    tasks: list = field(default_factory=list)

    def scan_all(self):
        """Run all scanners. Existing TODO is loaded first as the baseline."""
        # Load user-curated items first (these take priority in dedup)
        self.scan_existing_todo()
        existing_count = len(self.tasks)

        # Discover new tasks from project docs and filesystem
        self.scan_build_plan()
        self.scan_build_phases()
        self.scan_claude_md()
        self.scan_filesystem()
        self.scan_git_recent()
        self.deduplicate()

    def _file_exists_anywhere(self, filename: str) -> bool:
        """Check if a file exists anywhere in the project tree."""
        # Skip old package name references
        if "working_truth" in filename:
            # Map to current package name
            filename = filename.replace("working_truth", "keanu")

        # Direct path check
        if (self.project_root / filename).exists():
            return True

        # Check under src/keanu/
        if (self.project_root / "src" / "keanu" / filename).exists():
            return True

        # Bare filename: search recursively (exclude .venv, node_modules, .git)
        bare = Path(filename).name
        exclude_dirs = {".venv", "node_modules", ".git", "__pycache__", ".tox"}
        for match in self.project_root.rglob(bare):
            if not any(part in exclude_dirs for part in match.parts):
                return True
        return False

    def scan_build_plan(self):
        """Parse BUILD_PLAN.md for referenced files and tasks."""
        build_plan = self.project_root / "BUILD_PLAN.md"
        if not build_plan.exists():
            return

        content = build_plan.read_text()

        # Find file paths referenced in the plan (only actual file paths, not CLI commands)
        file_refs = re.findall(r'`([^`\s]+\.\w{1,4})`', content)
        seen_refs = set()
        for ref in file_refs:
            # Skip non-file references (CLI commands, URLs, etc.)
            if ref.startswith(("wt ", "uv ", "python", "pip", "http")):
                continue
            # Skip things that look like CLI usage examples (contain spaces)
            if " " in ref:
                continue
            # Skip old working_truth paths if the keanu equivalent exists
            normalized = ref.replace("src/working_truth/", "").replace("src/keanu/", "")
            if normalized in seen_refs:
                continue
            seen_refs.add(normalized)

            if not self._file_exists_anywhere(ref):
                effort = self._classify_effort(ref, content)
                self.tasks.append(Task(
                    description=f"Create `{ref}` (referenced in BUILD_PLAN.md)",
                    effort=effort,
                    source="build_plan",
                ))

    def scan_claude_md(self):
        """Parse CLAUDE.md for referenced files and structure."""
        claude_md = self.project_root / "CLAUDE.md"
        if not claude_md.exists():
            return

        content = claude_md.read_text()

        # Find file paths in the package structure section (tree-format lines)
        # Match lines like: │   ├── helix.py, └── protocol.py, etc.
        structure_refs = re.findall(r'[├└│─\s]+(\S+\.py)\s', content)
        for ref in structure_refs:
            # Skip generic/example filenames
            if ref in ("module.py",):
                continue
            if not self._file_exists_anywhere(ref):
                self.tasks.append(Task(
                    description=f"Create `{ref}` (referenced in CLAUDE.md package structure)",
                    effort=self._classify_effort(ref, content),
                    source="claude_md",
                ))

    def scan_filesystem(self):
        """Check for empty directories, missing test files, etc."""
        src_dir = self.project_root / "src"
        tests_dir = self.project_root / "tests"

        # Check for empty test directory
        if tests_dir.exists():
            test_files = list(tests_dir.glob("test_*.py"))
            if not test_files:
                self.tasks.append(Task(
                    description="Create test files in `tests/` (directory exists but is empty)",
                    effort="cool",
                    source="filesystem",
                ))
        elif not tests_dir.exists():
            self.tasks.append(Task(
                description="Create `tests/` directory with test stubs",
                effort="cool",
                source="filesystem",
            ))

        # Check for empty __init__.py files in subpackages
        if src_dir.exists():
            for init_file in src_dir.rglob("__init__.py"):
                content = init_file.read_text().strip()
                # Skip root __init__.py
                if init_file.parent.name in ("keanu", "working_truth"):
                    continue
                if len(content) < 10:  # basically empty
                    pkg_name = init_file.parent.name
                    self.tasks.append(Task(
                        description=f"Add `__all__` exports to `{pkg_name}/__init__.py`",
                        effort="cool",
                        source="filesystem",
                    ))

        # Check examples directory
        examples_dir = self.project_root / "examples"
        if not examples_dir.exists():
            self.tasks.append(Task(
                description="Create `examples/` directory with training data",
                effort="warm",
                source="filesystem",
            ))

        # Check README.md for staleness (references to old project names)
        readme = self.project_root / "README.md"
        if readme.exists():
            readme_content = readme.read_text().lower()
            project_name = self.project_root.name.lower()
            # Check if README mentions a different project name
            stale_names = {"silverado", "working_truth", "working-truth"}
            for name in stale_names:
                if name in readme_content and name != project_name:
                    self.tasks.append(Task(
                        description=f"Update README.md (still references '{name}')",
                        effort="hot",
                        source="filesystem",
                    ))
                    break

    def scan_build_phases(self):
        """Check BUILD_PLAN.md for incomplete phases and generate meta-tasks."""
        build_plan = self.project_root / "BUILD_PLAN.md"
        if not build_plan.exists():
            return

        content = build_plan.read_text()

        # Look for phase markers like "### Phase 7: Tests + Wiki"
        # and check if they contain unchecked items or "Done when:" criteria
        phases = re.findall(r'###\s+Phase\s+(\d+):\s+(.+?)(?:\n|$)', content)
        for phase_num, phase_name in phases:
            phase_name = phase_name.strip()
            # Check CLAUDE.md for [x] Phase N markers
            claude_md = self.project_root / "CLAUDE.md"
            if claude_md.exists():
                claude_content = claude_md.read_text()
                # Phase is marked done in CLAUDE.md if "- [x] Phase N" exists
                if re.search(rf'\[x\]\s*Phase\s*{phase_num}', claude_content):
                    continue

            # Phase not marked complete, add meta-task
            # Determine effort from phase description
            effort = self._classify_effort(phase_name, "")
            if "test" in phase_name.lower() or "wiki" in phase_name.lower():
                effort = "hot"
            self.tasks.append(Task(
                description=f"Complete Phase {phase_num}: {phase_name}",
                effort=effort,
                source="build_phases",
            ))

    def scan_existing_todo(self):
        """Parse existing TODO.md. Preserves completed items and user-checked items.

        On a full regeneration, unchecked items from auto-scanned sections are
        not re-imported (they'll be rediscovered by the scanners if still valid).
        Only completed [x] items are preserved as history.
        """
        todo_file = self.project_root / "TODO.md"
        if not todo_file.exists():
            return

        content = todo_file.read_text()
        current_section = None

        for line in content.splitlines():
            section_match = re.match(r'^## (COOL|WARM|HOT|DONE)', line, re.IGNORECASE)
            if section_match:
                current_section = section_match.group(1).lower()
                continue

            # Only preserve completed items (user marked [x])
            task_match = re.match(r'\s*-\s*\[x\]\s*(.*)', line)
            if task_match and current_section:
                self.tasks.append(Task(
                    description=task_match.group(1).strip(),
                    effort="done",
                    source="existing_todo",
                    done=True,
                ))

    def scan_git_recent(self):
        """Check git log for recent activity to inform what was just worked on."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10", "--no-decorate"],
                capture_output=True, text=True, cwd=self.project_root,
                timeout=5,
            )
            if result.returncode != 0:
                return

            # Check for uncommitted changes (potential in-progress work)
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=self.project_root,
                timeout=5,
            )
            if status.returncode == 0 and status.stdout.strip():
                changed_files = []
                for line in status.stdout.strip().splitlines():
                    # Parse git status porcelain format
                    filepath = line[3:].strip()
                    if " -> " in filepath:
                        filepath = filepath.split(" -> ")[1]
                    changed_files.append(filepath)

                if changed_files:
                    file_list = ", ".join(changed_files[:5])
                    suffix = f" (+{len(changed_files) - 5} more)" if len(changed_files) > 5 else ""
                    self.tasks.append(Task(
                        description=f"Review and commit uncommitted changes: {file_list}{suffix}",
                        effort="cool",
                        source="git",
                    ))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def deduplicate(self):
        """Remove duplicate tasks, preferring existing_todo source."""
        seen_keys = {}
        seen_files = {}  # track referenced filenames to avoid "create X" dupes
        deduped = []

        for task in self.tasks:
            # Normalize description for comparison
            key = re.sub(r'[`\s]+', ' ', task.description.lower()).strip()

            # Extract filename references for cross-matching
            file_match = re.search(r'`([^`]+)`', task.description)
            file_key = file_match.group(1).lower() if file_match else None
            # Normalize file key (strip path prefixes)
            if file_key:
                file_key = file_key.split("/")[-1]

            # Check for exact key match
            if key in seen_keys:
                if task.source == "existing_todo":
                    idx = deduped.index(seen_keys[key])
                    deduped[idx] = task
                    seen_keys[key] = task
                continue

            # Check for file-based match (e.g., "Create protocol.py" vs "Write signal/protocol.py")
            if file_key and file_key in seen_files:
                if task.source == "existing_todo":
                    idx = deduped.index(seen_files[file_key])
                    deduped[idx] = task
                    seen_files[file_key] = task
                    seen_keys[key] = task
                continue

            seen_keys[key] = task
            if file_key:
                seen_files[file_key] = task
            deduped.append(task)

        self.tasks = deduped

    def _classify_effort(self, text: str, context: str) -> str:
        """Classify a task description into cool/warm/hot."""
        text_lower = text.lower()
        context_lower = context.lower() if context else ""
        combined = text_lower + " " + context_lower

        # Check hot keywords first (most specific)
        for kw in HOT_KEYWORDS:
            if kw in text_lower:
                return "hot"

        # Check warm keywords
        for kw in WARM_KEYWORDS:
            if kw in text_lower:
                return "warm"

        # Check cool keywords
        for kw in COOL_KEYWORDS:
            if kw in text_lower:
                return "cool"

        # Heuristics based on file type/path
        if text_lower.endswith(".md"):
            return "warm"  # writing docs takes thought
        if "test" in text_lower:
            return "warm"
        if "__init__" in text_lower or "config" in text_lower:
            return "cool"

        return "warm"  # default to warm if uncertain

    def write_todo(self, output_path: Path = None):
        """Write tasks to TODO.md in cool/warm/hot format."""
        if output_path is None:
            output_path = self.project_root / "TODO.md"

        # Get project name from directory
        project_name = self.project_root.name.upper()

        cool = [t for t in self.tasks if t.effort == "cool" and not t.done]
        warm = [t for t in self.tasks if t.effort == "warm" and not t.done]
        hot = [t for t in self.tasks if t.effort == "hot" and not t.done]
        done = [t for t in self.tasks if t.done]

        lines = [f"# {project_name} TODO", ""]

        lines.append("## COOL (5-15 min)")
        for t in cool:
            lines.append(f"- [ ] {t.description}")
        if not cool:
            lines.append("(nothing here)")
        lines.append("")

        lines.append("## WARM (20-45 min)")
        for t in warm:
            lines.append(f"- [ ] {t.description}")
        if not warm:
            lines.append("(nothing here)")
        lines.append("")

        lines.append("## HOT (1-2 hours)")
        for t in hot:
            lines.append(f"- [ ] {t.description}")
        if not hot:
            lines.append("(nothing here)")
        lines.append("")

        lines.append("## DONE")
        for t in done:
            lines.append(f"- [x] {t.description}")
        lines.append("")

        output_path.write_text("\n".join(lines))
        return cool, warm, hot, done

    def print_summary(self, cool, warm, hot, done):
        """Print a summary to terminal."""
        total = len(cool) + len(warm) + len(hot)
        print(f"\nTODO: {total} tasks remaining, {len(done)} done")
        print(f"  COOL ({len(cool)}): {', '.join(t.description[:40] for t in cool[:3])}")
        print(f"  WARM ({len(warm)}): {', '.join(t.description[:40] for t in warm[:3])}")
        print(f"  HOT  ({len(hot)}): {', '.join(t.description[:40] for t in hot[:3])}")
        if done:
            print(f"  DONE ({len(done)})")
        print()


def generate_todo(project_root: str = "."):
    """Main entry point: scan project and write TODO.md."""
    root = Path(project_root).resolve()
    scan = TodoScan(project_root=root)
    scan.scan_all()
    cool, warm, hot, done = scan.write_todo()
    scan.print_summary(cool, warm, hot, done)
    return scan
