"""git: version control awareness for the agent.

status, diff, log, blame, branch, stash, commit.
the agent knows what changed, what's staged, and where it is.
invoked explicitly by the loop, never by keyword match.

in the world: the ledger. every change tracked, every decision recorded.
"""

import subprocess
from pathlib import Path

from keanu.abilities import Ability, ability


def _git(*args, cwd=None):
    """run a git command, return (success, output)."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=15,
            cwd=cwd or str(Path.cwd()),
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()
            return False, err or output or f"git {args[0]} failed"
        return True, output
    except subprocess.TimeoutExpired:
        return False, f"git {args[0]} timed out"
    except FileNotFoundError:
        return False, "git not found"


@ability
class GitAbility(Ability):

    name = "git"
    description = "Git operations: status, diff, log, blame, branch, stash, commit"
    keywords = ["git", "status", "diff", "log", "blame", "branch", "commit", "stash"]
    cast_line = "git opens the ledger..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        ctx = context or {}
        op = ctx.get("op", "status")
        return _OPS.get(op, _op_unknown)(ctx)


def _op_status(ctx):
    """git status, short format."""
    ok, out = _git("status", "--short")
    if not ok:
        return {"success": False, "result": out, "data": {}}

    branch_ok, branch = _git("branch", "--show-current")
    branch_name = branch if branch_ok else "unknown"

    if not out:
        out = "(clean working tree)"

    return {
        "success": True,
        "result": f"branch: {branch_name}\n{out}",
        "data": {"branch": branch_name, "clean": out == "(clean working tree)"},
    }


def _op_diff(ctx):
    """git diff. staged=True for staged changes, file= for specific file."""
    args = ["diff"]
    if ctx.get("staged"):
        args.append("--staged")
    if ctx.get("file"):
        args.append("--")
        args.append(ctx["file"])

    ok, out = _git(*args)
    if not ok:
        return {"success": False, "result": out, "data": {}}

    if not out:
        kind = "staged" if ctx.get("staged") else "unstaged"
        return {"success": True, "result": f"(no {kind} changes)", "data": {"empty": True}}

    # truncate massive diffs
    if len(out) > 8000:
        out = out[:8000] + f"\n... (truncated, {len(out)} total chars)"

    return {"success": True, "result": out, "data": {"empty": False}}


def _op_log(ctx):
    """git log. n= number of entries (default 10)."""
    n = str(ctx.get("n", 10))
    fmt = ctx.get("format", "%h %s (%an, %ar)")
    ok, out = _git("log", f"--oneline", f"-{n}", f"--format={fmt}")
    if not ok:
        return {"success": False, "result": out, "data": {}}
    return {"success": True, "result": out, "data": {"count": int(n)}}


def _op_blame(ctx):
    """git blame a specific file."""
    file = ctx.get("file", "")
    if not file:
        return {"success": False, "result": "No file specified for blame.", "data": {}}

    ok, out = _git("blame", "--line-porcelain", file)
    if not ok:
        # fallback to simple blame
        ok, out = _git("blame", file)
        if not ok:
            return {"success": False, "result": out, "data": {}}

    # truncate
    if len(out) > 8000:
        out = out[:8000] + f"\n... (truncated)"

    return {"success": True, "result": out, "data": {"file": file}}


def _op_branch(ctx):
    """branch operations: list, create, switch."""
    sub = ctx.get("sub", "list")

    if sub == "list":
        ok, out = _git("branch", "-a")
        if not ok:
            return {"success": False, "result": out, "data": {}}
        return {"success": True, "result": out, "data": {}}

    if sub == "create":
        name = ctx.get("name", "")
        if not name:
            return {"success": False, "result": "No branch name.", "data": {}}
        ok, out = _git("checkout", "-b", name)
        if not ok:
            return {"success": False, "result": out, "data": {}}
        return {"success": True, "result": f"Created and switched to branch: {name}", "data": {"branch": name}}

    if sub == "switch":
        name = ctx.get("name", "")
        if not name:
            return {"success": False, "result": "No branch name.", "data": {}}
        ok, out = _git("checkout", name)
        if not ok:
            return {"success": False, "result": out, "data": {}}
        return {"success": True, "result": f"Switched to branch: {name}", "data": {"branch": name}}

    return {"success": False, "result": f"Unknown branch sub-op: {sub}", "data": {}}


def _op_stash(ctx):
    """stash operations: save, pop, list."""
    sub = ctx.get("sub", "save")

    if sub == "save":
        msg = ctx.get("message", "")
        args = ["stash", "push"]
        if msg:
            args.extend(["-m", msg])
        ok, out = _git(*args)
        if not ok:
            return {"success": False, "result": out, "data": {}}
        return {"success": True, "result": out or "Stashed changes.", "data": {}}

    if sub == "pop":
        ok, out = _git("stash", "pop")
        if not ok:
            return {"success": False, "result": out, "data": {}}
        return {"success": True, "result": out or "Popped stash.", "data": {}}

    if sub == "list":
        ok, out = _git("stash", "list")
        if not ok:
            return {"success": False, "result": out, "data": {}}
        return {"success": True, "result": out or "(no stashes)", "data": {}}

    return {"success": False, "result": f"Unknown stash sub-op: {sub}", "data": {}}


def _op_add(ctx):
    """stage files."""
    files = ctx.get("files", [])
    if not files:
        return {"success": False, "result": "No files to stage.", "data": {}}

    ok, out = _git("add", *files)
    if not ok:
        return {"success": False, "result": out, "data": {}}
    return {"success": True, "result": f"Staged: {', '.join(files)}", "data": {"files": files}}


def _op_commit(ctx):
    """commit staged changes."""
    message = ctx.get("message", "")
    if not message:
        return {"success": False, "result": "No commit message.", "data": {}}

    ok, out = _git("commit", "-m", message)
    if not ok:
        return {"success": False, "result": out, "data": {}}
    return {"success": True, "result": out, "data": {"message": message}}


def _op_show(ctx):
    """show a commit."""
    ref = ctx.get("ref", "HEAD")
    ok, out = _git("show", "--stat", ref)
    if not ok:
        return {"success": False, "result": out, "data": {}}

    if len(out) > 8000:
        out = out[:8000] + "\n... (truncated)"

    return {"success": True, "result": out, "data": {"ref": ref}}


def _op_unknown(ctx):
    ops = ", ".join(sorted(_OPS.keys()))
    return {"success": False, "result": f"Unknown git op. Available: {ops}", "data": {}}


_OPS = {
    "status": _op_status,
    "diff": _op_diff,
    "log": _op_log,
    "blame": _op_blame,
    "branch": _op_branch,
    "stash": _op_stash,
    "add": _op_add,
    "commit": _op_commit,
    "show": _op_show,
}
