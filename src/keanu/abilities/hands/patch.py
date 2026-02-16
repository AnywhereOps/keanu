"""patch.py - multi-file atomic edits.

apply edits across multiple files atomically. if any edit fails,
roll back all changes. preview mode shows what would change.

in the world: you don't renovate one wall at a time and hope
the house stays standing. you plan the whole change.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from keanu.abilities import Ability, ability


@dataclass
class FileEdit:
    """one edit to one file."""
    file_path: str
    old_string: str
    new_string: str


@dataclass
class PatchResult:
    """result of applying a patch."""
    success: bool
    edits_applied: int = 0
    edits_total: int = 0
    errors: list = field(default_factory=list)
    files_changed: list = field(default_factory=list)
    rollback_done: bool = False


def apply_patch(edits: list[FileEdit], dry_run: bool = False) -> PatchResult:
    """apply multiple edits atomically.

    reads all files first, validates all edits, then applies.
    if any edit would fail (string not found, not unique), no files are changed.
    """
    result = PatchResult(success=False, edits_total=len(edits))

    if not edits:
        result.success = True
        return result

    # phase 1: read all files and validate
    originals = {}  # path -> original content
    planned = {}    # path -> new content after all edits

    for edit in edits:
        path = edit.file_path
        try:
            if path not in originals:
                content = Path(path).read_text()
                originals[path] = content
                planned[path] = content
        except (OSError, UnicodeDecodeError) as e:
            result.errors.append(f"cannot read {path}: {e}")
            return result

    # phase 2: validate all edits against planned state
    for i, edit in enumerate(edits):
        content = planned[edit.file_path]
        count = content.count(edit.old_string)

        if count == 0:
            result.errors.append(
                f"edit {i+1}: old_string not found in {edit.file_path}"
            )
            return result
        if count > 1:
            result.errors.append(
                f"edit {i+1}: old_string found {count} times in {edit.file_path} (must be unique)"
            )
            return result

        # apply edit to planned state
        planned[edit.file_path] = content.replace(edit.old_string, edit.new_string, 1)

    # phase 3: preview or apply
    if dry_run:
        result.success = True
        result.edits_applied = len(edits)
        result.files_changed = list(set(e.file_path for e in edits))
        return result

    # phase 4: write all files
    written = []
    try:
        for path, new_content in planned.items():
            if new_content != originals[path]:
                Path(path).write_text(new_content)
                written.append(path)
    except (OSError, IOError) as e:
        # rollback: restore originals
        for wpath in written:
            try:
                Path(wpath).write_text(originals[wpath])
            except Exception:
                pass
        result.errors.append(f"write failed: {e}")
        result.rollback_done = True
        return result

    result.success = True
    result.edits_applied = len(edits)
    result.files_changed = written
    return result


def parse_patch_args(args: dict) -> list[FileEdit]:
    """parse the agent's patch args into FileEdit objects.

    expects args like:
    {
        "edits": [
            {"file_path": "...", "old_string": "...", "new_string": "..."},
            ...
        ]
    }
    """
    edits = []
    for edit_dict in args.get("edits", []):
        edits.append(FileEdit(
            file_path=edit_dict.get("file_path", ""),
            old_string=edit_dict.get("old_string", ""),
            new_string=edit_dict.get("new_string", ""),
        ))
    return edits


@ability
class PatchAbility(Ability):

    name = "patch"
    description = "Apply edits across multiple files atomically"
    keywords = ["patch", "multi-file", "atomic edit"]
    cast_line = "patch reshapes the world..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        ctx = context or {}
        dry_run = ctx.get("preview", False)

        edits = parse_patch_args(ctx)
        if not edits:
            return {"success": False, "result": "No edits provided.", "data": {}}

        # validate paths
        from keanu.abilities.hands.hands import _is_safe_path
        for edit in edits:
            if not _is_safe_path(edit.file_path):
                return {
                    "success": False,
                    "result": f"Path outside project: {edit.file_path}",
                    "data": {},
                }

        result = apply_patch(edits, dry_run=dry_run)

        if result.success:
            mode = "preview" if dry_run else "applied"
            return {
                "success": True,
                "result": f"Patch {mode}: {result.edits_applied} edits across {len(result.files_changed)} files",
                "data": {
                    "edits_applied": result.edits_applied,
                    "files_changed": result.files_changed,
                    "dry_run": dry_run,
                },
            }
        else:
            msg = "; ".join(result.errors)
            if result.rollback_done:
                msg += " (rolled back)"
            return {"success": False, "result": msg, "data": {}}
