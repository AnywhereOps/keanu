"""ability_schema.py - ability protocol upgrade.

abilities declare input/output schemas. chains of abilities can be composed.
transactional: if any step fails, the whole chain rolls back.

in the world: the protocol. how abilities talk to each other.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ParamSchema:
    """schema for a single parameter."""
    name: str
    type: str = "string"   # string, int, float, bool, list, dict, path
    required: bool = True
    default: Any = None
    description: str = ""


@dataclass
class AbilitySchema:
    """input/output schema for an ability."""
    name: str
    description: str = ""
    inputs: list[ParamSchema] = field(default_factory=list)
    outputs: list[ParamSchema] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)         # categorization
    requires_confirmation: bool = False                     # destructive ops
    version: str = "1"

    def validate_input(self, context: dict) -> list[str]:
        """validate input against the schema. returns list of errors."""
        errors = []
        for param in self.inputs:
            if param.required and param.name not in context:
                errors.append(f"missing required parameter: {param.name}")
            if param.name in context:
                value = context[param.name]
                if not _type_check(value, param.type):
                    errors.append(f"{param.name}: expected {param.type}, got {type(value).__name__}")
        return errors

    def signature(self) -> str:
        """human-readable signature for display."""
        params = []
        for p in self.inputs:
            suffix = "?" if not p.required else ""
            params.append(f"{p.name}: {p.type}{suffix}")
        return f"{self.name}({', '.join(params)})"


# built-in schemas for hands abilities
SCHEMAS = {
    "read": AbilitySchema(
        name="read",
        description="Read a file's contents",
        inputs=[ParamSchema("file_path", "path", required=True, description="path to read")],
        outputs=[ParamSchema("content", "string"), ParamSchema("lines", "int"), ParamSchema("size", "int")],
        tags=["file", "read"],
    ),
    "write": AbilitySchema(
        name="write",
        description="Write content to a file",
        inputs=[
            ParamSchema("file_path", "path", required=True),
            ParamSchema("content", "string", required=True),
        ],
        outputs=[ParamSchema("size", "int")],
        tags=["file", "write"],
        requires_confirmation=False,
    ),
    "edit": AbilitySchema(
        name="edit",
        description="Make a targeted edit in a file",
        inputs=[
            ParamSchema("file_path", "path", required=True),
            ParamSchema("old_string", "string", required=True),
            ParamSchema("new_string", "string", required=True),
        ],
        outputs=[ParamSchema("replacements", "int")],
        tags=["file", "write"],
    ),
    "search": AbilitySchema(
        name="search",
        description="Search for patterns in code",
        inputs=[
            ParamSchema("pattern", "string", required=False),
            ParamSchema("path", "string", required=False, default="."),
            ParamSchema("glob", "string", required=False),
        ],
        outputs=[ParamSchema("count", "int"), ParamSchema("mode", "string")],
        tags=["search", "read"],
    ),
    "run": AbilitySchema(
        name="run",
        description="Run a shell command",
        inputs=[ParamSchema("command", "string", required=True)],
        outputs=[ParamSchema("returncode", "int")],
        tags=["shell"],
        requires_confirmation=True,
    ),
    "git": AbilitySchema(
        name="git",
        description="Version control operations",
        inputs=[ParamSchema("op", "string", required=True, description="status|diff|log|blame|branch|stash|add|commit|show")],
        outputs=[],
        tags=["vcs", "git"],
    ),
    "test": AbilitySchema(
        name="test",
        description="Run tests",
        inputs=[ParamSchema("op", "string", required=True, description="run|discover|targeted|coverage")],
        outputs=[],
        tags=["test"],
    ),
    "rename": AbilitySchema(
        name="rename",
        description="Rename a symbol across the project",
        inputs=[
            ParamSchema("old_name", "string", required=True),
            ParamSchema("new_name", "string", required=True),
            ParamSchema("preview", "bool", required=False, default=False),
        ],
        outputs=[ParamSchema("edits", "int"), ParamSchema("files_changed", "list")],
        tags=["refactor"],
    ),
    "lookup": AbilitySchema(
        name="lookup",
        description="Search docs or fetch URL",
        inputs=[
            ParamSchema("url", "string", required=False),
            ParamSchema("query", "string", required=False),
            ParamSchema("library", "string", required=False),
        ],
        outputs=[],
        tags=["web", "docs"],
    ),
}


def get_schema(ability_name: str) -> Optional[AbilitySchema]:
    """get the schema for an ability, if registered."""
    return SCHEMAS.get(ability_name)


# ============================================================
# ABILITY CHAINS
# ============================================================

@dataclass
class ChainStep:
    """one step in an ability chain."""
    ability: str
    args: dict = field(default_factory=dict)
    on_fail: str = "rollback"  # "rollback", "skip", "stop"


@dataclass
class ChainResult:
    """result of executing an ability chain."""
    success: bool
    steps_completed: int = 0
    total_steps: int = 0
    results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rolled_back: bool = False


def execute_chain(steps: list[ChainStep], registry: dict,
                  dry_run: bool = False) -> ChainResult:
    """execute a chain of abilities transactionally.

    if any step fails and on_fail is "rollback", all previous steps
    that are reversible get rolled back. "skip" continues to the next
    step. "stop" halts without rollback.
    """
    results = []
    rollback_stack = []  # (ability_name, original_state) for rollback

    for i, step in enumerate(steps):
        ab = registry.get(step.ability)
        if ab is None:
            return ChainResult(
                success=False,
                steps_completed=i,
                total_steps=len(steps),
                results=results,
                errors=[f"unknown ability: {step.ability}"],
            )

        # validate inputs if schema exists
        schema = get_schema(step.ability)
        if schema:
            errors = schema.validate_input(step.args)
            if errors:
                if step.on_fail == "skip":
                    results.append({"success": False, "result": "; ".join(errors)})
                    continue
                return ChainResult(
                    success=False,
                    steps_completed=i,
                    total_steps=len(steps),
                    results=results,
                    errors=errors,
                )

        if dry_run:
            results.append({"success": True, "result": f"(dry run) {step.ability}"})
            continue

        # capture file state BEFORE execution for potential rollback
        if step.ability in ("write", "edit"):
            path = step.args.get("file_path", "")
            if path:
                try:
                    from pathlib import Path
                    original = Path(path).read_text() if Path(path).exists() else None
                    rollback_stack.append((path, original))
                except Exception:
                    pass

        try:
            result = ab.execute(
                prompt="",
                context=step.args,
            )
        except Exception as e:
            result = {"success": False, "result": str(e), "data": {}}

        results.append(result)

        if not result.get("success"):
            if step.on_fail == "rollback":
                _do_rollback(rollback_stack)
                return ChainResult(
                    success=False,
                    steps_completed=i,
                    total_steps=len(steps),
                    results=results,
                    errors=[f"step {i} ({step.ability}) failed: {result.get('result', 'unknown')}"],
                    rolled_back=True,
                )
            elif step.on_fail == "stop":
                return ChainResult(
                    success=False,
                    steps_completed=i,
                    total_steps=len(steps),
                    results=results,
                    errors=[f"step {i} ({step.ability}) failed"],
                )
            # "skip": continue to next step

    return ChainResult(
        success=True,
        steps_completed=len(steps),
        total_steps=len(steps),
        results=results,
    )


def _do_rollback(rollback_stack: list):
    """roll back file changes in reverse order."""
    from pathlib import Path
    for path_str, original_content in reversed(rollback_stack):
        try:
            p = Path(path_str)
            if original_content is None:
                p.unlink(missing_ok=True)
            else:
                p.write_text(original_content)
        except Exception:
            pass


# ============================================================
# HELPERS
# ============================================================

def _type_check(value: Any, expected_type: str) -> bool:
    """check if a value matches the expected type string."""
    type_map = {
        "string": str,
        "int": int,
        "float": (int, float),
        "bool": bool,
        "list": list,
        "dict": dict,
        "path": str,
    }
    expected = type_map.get(expected_type)
    if expected is None:
        return True  # unknown type, allow
    return isinstance(value, expected)
