"""lint.py - lint and format abilities.

run the project's linter and formatter. auto-detect from project model
(ruff, eslint, golint) or fall back to common defaults. parse output
into structured results so the agent can fix issues.

in the world: the mirror before you leave the house. catches what you missed.
"""

import subprocess
from pathlib import Path

from keanu.abilities import Ability, ability


def _run_tool(cmd: str, cwd: str = ".") -> dict:
    """run a lint/format tool, capture and parse output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=60, cwd=cwd,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n{result.stderr}" if output else result.stderr

        if len(output) > 10000:
            output = output[:10000] + f"\n... (truncated, {len(output)} total chars)"

        return {
            "success": result.returncode == 0,
            "result": output.strip() if output.strip() else "(clean)" if result.returncode == 0 else "(no output)",
            "data": {"command": cmd, "returncode": result.returncode},
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "result": f"Timed out (60s): {cmd}", "data": {"command": cmd}}
    except FileNotFoundError:
        return {"success": False, "result": f"Tool not found: {cmd.split()[0]}", "data": {"command": cmd}}
    except Exception as e:
        return {"success": False, "result": f"Failed: {e}", "data": {"command": cmd}}


def _detect_lint_command(cwd: str = ".") -> str:
    """auto-detect the lint command from project model."""
    try:
        from keanu.analysis.project import detect
        model = detect(cwd)
        if model.lint_command:
            return model.lint_command
    except Exception:
        pass

    # fallback chain
    root = Path(cwd).resolve()
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        return "ruff check ."
    if (root / "package.json").exists():
        return "npx eslint ."
    if (root / "go.mod").exists():
        return "golangci-lint run"
    return "ruff check ."


def _detect_format_command(cwd: str = ".") -> str:
    """auto-detect the format command from project model."""
    try:
        from keanu.analysis.project import detect
        model = detect(cwd)
        if model.format_command:
            return model.format_command
    except Exception:
        pass

    root = Path(cwd).resolve()
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        return "ruff format ."
    if (root / "package.json").exists():
        return "npx prettier --write ."
    if (root / "go.mod").exists():
        return "gofmt -w ."
    return "ruff format ."


def _parse_lint_issues(output: str) -> list[dict]:
    """extract structured issues from lint output."""
    issues = []
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        # ruff format: path:line:col: CODE message
        if ":" in line:
            parts = line.split(":", 3)
            if len(parts) >= 4 and parts[1].strip().isdigit():
                issues.append({
                    "file": parts[0].strip(),
                    "line": int(parts[1].strip()),
                    "col": int(parts[2].strip()) if parts[2].strip().isdigit() else 0,
                    "message": parts[3].strip(),
                })
    return issues[:50]  # cap at 50


@ability
class LintAbility(Ability):

    name = "lint"
    description = "Run the project linter and parse results"
    keywords = ["lint", "check", "ruff", "eslint", "flake8"]
    cast_line = "lint checks the mirror..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        ctx = context or {}
        cwd = ctx.get("path", ".")
        cmd = ctx.get("command", "")
        fix = ctx.get("fix", False)

        if not cmd:
            cmd = _detect_lint_command(cwd)

        if fix and "ruff" in cmd:
            cmd = cmd.replace("ruff check", "ruff check --fix")
        elif fix and "eslint" in cmd:
            cmd += " --fix"

        result = _run_tool(cmd, cwd)

        # parse issues from output
        if not result["success"]:
            issues = _parse_lint_issues(result["result"])
            result["data"]["issues"] = issues
            result["data"]["issue_count"] = len(issues)

        return result


@ability
class FormatAbility(Ability):

    name = "format"
    description = "Run the project formatter"
    keywords = ["format", "prettier", "black", "ruff format", "gofmt"]
    cast_line = "format polishes the code..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        ctx = context or {}
        cwd = ctx.get("path", ".")
        cmd = ctx.get("command", "")
        check_only = ctx.get("check", False)

        if not cmd:
            cmd = _detect_format_command(cwd)

        if check_only:
            if "ruff format" in cmd:
                cmd += " --check"
            elif "prettier" in cmd:
                cmd = cmd.replace("--write", "--check")
            elif "black" in cmd:
                cmd += " --check"

        return _run_tool(cmd, cwd)
