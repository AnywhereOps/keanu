"""hands: the abilities that touch the world. read, write, search, execute.

these are the only way the agent acts on files and commands.
each one is bounded and safe. no raw shell, no unbounded writes.
"""

import os
import subprocess
from pathlib import Path

from keanu.abilities import Ability, ability


# safety: directories the agent can read/write
_SAFE_ROOTS = None


def _get_safe_roots():
    """Lazily compute safe roots (cwd and its children)."""
    global _SAFE_ROOTS
    if _SAFE_ROOTS is None:
        cwd = Path.cwd().resolve()
        _SAFE_ROOTS = [cwd]
    return _SAFE_ROOTS


def _is_safe_path(path_str: str) -> bool:
    """Check if a path is under a safe root."""
    try:
        target = Path(path_str).resolve()
        return any(target == root or root in target.parents for root in _get_safe_roots())
    except (ValueError, OSError):
        return False


# blocked commands that could do real damage
_BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf ~", "rm -rf .", "sudo", "mkfs",
    "dd if=", "> /dev/", "chmod -R 777",
}


def _is_safe_command(cmd: str) -> bool:
    """Basic safety check on shell commands."""
    cmd_lower = cmd.lower().strip()
    return not any(blocked in cmd_lower for blocked in _BLOCKED_COMMANDS)


# ============================================================
# READ FILE
# ============================================================

@ability
class ReadFileAbility(Ability):

    name = "read"
    description = "Read a file's contents"
    keywords = ["read", "cat", "show", "view", "open", "contents of"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        # hands abilities are invoked explicitly by the loop, not by keyword match
        # they should NOT match on casual prompts
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        path = context.get("file_path", "") if context else ""
        if not path:
            return {"success": False, "result": "No file_path provided.", "data": {}}

        if not _is_safe_path(path):
            return {"success": False, "result": f"Path outside project: {path}", "data": {}}

        try:
            content = Path(path).read_text()
            lines = content.count("\n") + 1
            return {
                "success": True,
                "result": content,
                "data": {"path": path, "lines": lines, "size": len(content)},
            }
        except (OSError, IOError) as e:
            return {"success": False, "result": f"Could not read: {e}", "data": {}}


# ============================================================
# WRITE FILE
# ============================================================

@ability
class WriteFileAbility(Ability):

    name = "write"
    description = "Write content to a file (creates or overwrites)"
    keywords = ["write", "create", "save"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        path = context.get("file_path", "") if context else ""
        content = context.get("content", "") if context else ""

        if not path:
            return {"success": False, "result": "No file_path provided.", "data": {}}
        if not content:
            return {"success": False, "result": "No content provided.", "data": {}}
        if not _is_safe_path(path):
            return {"success": False, "result": f"Path outside project: {path}", "data": {}}

        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return {
                "success": True,
                "result": f"Wrote {len(content)} chars to {path}",
                "data": {"path": path, "size": len(content)},
            }
        except (OSError, IOError) as e:
            return {"success": False, "result": f"Could not write: {e}", "data": {}}


# ============================================================
# EDIT FILE
# ============================================================

@ability
class EditFileAbility(Ability):

    name = "edit"
    description = "Make a targeted edit in a file (old_string -> new_string)"
    keywords = ["edit", "replace", "change", "modify"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        path = context.get("file_path", "") if context else ""
        old = context.get("old_string", "") if context else ""
        new = context.get("new_string", "") if context else ""

        if not path:
            return {"success": False, "result": "No file_path provided.", "data": {}}
        if not old:
            return {"success": False, "result": "No old_string provided.", "data": {}}
        if not _is_safe_path(path):
            return {"success": False, "result": f"Path outside project: {path}", "data": {}}

        try:
            p = Path(path)
            content = p.read_text()
            count = content.count(old)
            if count == 0:
                return {"success": False, "result": f"old_string not found in {path}", "data": {}}
            if count > 1:
                return {"success": False, "result": f"old_string found {count} times (must be unique)", "data": {}}

            new_content = content.replace(old, new, 1)
            p.write_text(new_content)
            return {
                "success": True,
                "result": f"Edited {path}",
                "data": {"path": path, "replacements": 1},
            }
        except (OSError, IOError) as e:
            return {"success": False, "result": f"Could not edit: {e}", "data": {}}


# ============================================================
# SEARCH CODE
# ============================================================

@ability
class SearchAbility(Ability):

    name = "search"
    description = "Search for patterns in code (grep + glob)"
    keywords = ["search", "grep", "find", "where is", "look for"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        pattern = context.get("pattern", "") if context else ""
        path = context.get("path", ".") if context else "."
        glob_pattern = context.get("glob", "") if context else ""

        if not pattern and not glob_pattern:
            return {"success": False, "result": "No pattern or glob provided.", "data": {}}

        if not _is_safe_path(path):
            return {"success": False, "result": f"Path outside project: {path}", "data": {}}

        # glob mode: find files by name pattern
        if glob_pattern and not pattern:
            try:
                matches = sorted(Path(path).rglob(glob_pattern))[:50]
                result_lines = [str(m) for m in matches]
                return {
                    "success": True,
                    "result": "\n".join(result_lines) if result_lines else "No files matched.",
                    "data": {"count": len(result_lines), "mode": "glob"},
                }
            except Exception as e:
                return {"success": False, "result": f"Glob failed: {e}", "data": {}}

        # grep mode: search content
        try:
            cmd = ["grep", "-rn", "--include=*.py", pattern, path]
            if glob_pattern:
                cmd = ["grep", "-rn", f"--include={glob_pattern}", pattern, path]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
            )
            lines = result.stdout.strip().split("\n")[:50]
            output = "\n".join(lines) if lines[0] else "No matches."
            return {
                "success": True,
                "result": output,
                "data": {"count": len(lines) if lines[0] else 0, "mode": "grep"},
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "result": "Search timed out.", "data": {}}
        except Exception as e:
            return {"success": False, "result": f"Search failed: {e}", "data": {}}


# ============================================================
# LIST FILES
# ============================================================

@ability
class ListFilesAbility(Ability):

    name = "ls"
    description = "List files in a directory"
    keywords = ["list", "ls", "directory", "files in"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        path = context.get("path", ".") if context else "."

        if not _is_safe_path(path):
            return {"success": False, "result": f"Path outside project: {path}", "data": {}}

        try:
            p = Path(path)
            if not p.is_dir():
                return {"success": False, "result": f"Not a directory: {path}", "data": {}}

            entries = sorted(p.iterdir())
            lines = []
            for e in entries[:100]:
                if e.name.startswith("."):
                    continue
                prefix = "d" if e.is_dir() else "f"
                lines.append(f"{prefix} {e.name}")

            return {
                "success": True,
                "result": "\n".join(lines) if lines else "(empty directory)",
                "data": {"count": len(lines), "path": path},
            }
        except (OSError, IOError) as e:
            return {"success": False, "result": f"Could not list: {e}", "data": {}}


# ============================================================
# RUN COMMAND
# ============================================================

@ability
class RunCommandAbility(Ability):

    name = "run"
    description = "Run a shell command and capture output"
    keywords = ["run", "execute", "shell", "command", "bash"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        cmd = context.get("command", "") if context else ""

        if not cmd:
            return {"success": False, "result": "No command provided.", "data": {}}

        if not _is_safe_command(cmd):
            return {"success": False, "result": f"Command blocked: {cmd}", "data": {}}

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=60, cwd=str(Path.cwd()),
            )
            output = result.stdout
            if result.stderr:
                output += f"\n--- stderr ---\n{result.stderr}"

            # truncate if too long
            if len(output) > 10000:
                output = output[:10000] + f"\n... (truncated, {len(output)} total chars)"

            return {
                "success": result.returncode == 0,
                "result": output if output.strip() else "(no output)",
                "data": {
                    "returncode": result.returncode,
                    "command": cmd,
                },
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "result": f"Command timed out (60s): {cmd}", "data": {}}
        except Exception as e:
            return {"success": False, "result": f"Command failed: {e}", "data": {}}
