"""refactor.py - refactoring abilities for the agent.

rename, extract, move. wraps refactor.py operations as abilities.
"""

from keanu.abilities import Ability, ability


@ability
class RenameAbility(Ability):

    name = "rename"
    description = "Rename a symbol across the project (AST-aware)"
    keywords = ["rename", "refactor rename"]
    cast_line = "rename reshapes the name..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.analysis.refactor import rename

        ctx = context or {}
        old_name = ctx.get("old_name", "")
        new_name = ctx.get("new_name", "")
        root = ctx.get("root", ".")
        dry_run = ctx.get("preview", False)

        if not old_name or not new_name:
            return {"success": False, "result": "Provide old_name and new_name.", "data": {}}

        result = rename(old_name, new_name, root=root, dry_run=dry_run)

        if not result.success:
            return {"success": False, "result": "; ".join(result.errors), "data": {}}

        return {
            "success": True,
            "result": result.summary,
            "data": {
                "edits": len(result.edits),
                "files_changed": result.files_changed,
                "dry_run": result.dry_run,
            },
        }


@ability
class ExtractAbility(Ability):

    name = "extract"
    description = "Extract lines into a new function"
    keywords = ["extract", "refactor extract"]
    cast_line = "extract distills the essence..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.analysis.refactor import extract_function

        ctx = context or {}
        filepath = ctx.get("file_path", "")
        start = ctx.get("start_line", 0)
        end = ctx.get("end_line", 0)
        new_name = ctx.get("new_name", "")
        dry_run = ctx.get("preview", False)

        if not filepath or not new_name or not start or not end:
            return {
                "success": False,
                "result": "Provide file_path, start_line, end_line, and new_name.",
                "data": {},
            }

        result = extract_function(filepath, start, end, new_name, dry_run=dry_run)

        if not result.success:
            return {"success": False, "result": "; ".join(result.errors), "data": {}}

        return {
            "success": True,
            "result": result.summary,
            "data": {"files_changed": result.files_changed, "dry_run": result.dry_run},
        }


@ability
class MoveAbility(Ability):

    name = "move"
    description = "Move a function/class between modules"
    keywords = ["move", "refactor move"]
    cast_line = "move carries the weight..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.analysis.refactor import move_symbol

        ctx = context or {}
        name = ctx.get("name", "")
        from_file = ctx.get("from_file", "")
        to_file = ctx.get("to_file", "")
        root = ctx.get("root", ".")
        dry_run = ctx.get("preview", False)

        if not name or not from_file or not to_file:
            return {
                "success": False,
                "result": "Provide name, from_file, and to_file.",
                "data": {},
            }

        result = move_symbol(name, from_file, to_file, root=root, dry_run=dry_run)

        if not result.success:
            return {"success": False, "result": "; ".join(result.errors), "data": {}}

        return {
            "success": True,
            "result": result.summary,
            "data": {"files_changed": result.files_changed, "dry_run": result.dry_run},
        }
