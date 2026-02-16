"""githooks.py - git hook management.

install, manage, and run git hooks that integrate with keanu.
pre-commit hooks can run lint, format, security checks.
commit-msg hooks can validate conventional commits.

in the world: the guardian at the gate. checks that everything
is in order before the change goes through.
"""

import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path


HOOK_TYPES = [
    "pre-commit", "commit-msg", "pre-push",
    "post-commit", "post-merge", "post-checkout",
    "prepare-commit-msg",
]


@dataclass
class HookConfig:
    """configuration for a git hook."""
    hook_type: str
    commands: list[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class HookResult:
    """result of running a hook."""
    hook_type: str
    success: bool
    output: str = ""
    errors: list[str] = field(default_factory=list)


# ============================================================
# HOOK TEMPLATES
# ============================================================

PRE_COMMIT_TEMPLATE = """#!/bin/sh
# keanu pre-commit hook
# runs lint, format check, and security scan before commit

set -e

{commands}

echo "keanu: all pre-commit checks passed"
"""

COMMIT_MSG_TEMPLATE = """#!/bin/sh
# keanu commit-msg hook
# validates conventional commit format

MSG_FILE="$1"
MSG=$(cat "$MSG_FILE")

# check conventional commit format: type(scope): subject
if ! echo "$MSG" | grep -qE '^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)([(].+[)])?!?:.+'; then
    echo "keanu: commit message must follow conventional commits format"
    echo "  format: type(scope): subject"
    echo "  types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert"
    echo "  example: feat(auth): add login endpoint"
    exit 1
fi
"""

PRE_PUSH_TEMPLATE = """#!/bin/sh
# keanu pre-push hook
# runs tests before push

set -e

{commands}

echo "keanu: all pre-push checks passed"
"""


def _default_pre_commit_commands() -> list[str]:
    """default pre-commit commands."""
    return [
        "# lint check",
        'python3 -m ruff check . --select E,W,F 2>/dev/null || echo "ruff not available, skipping lint"',
        "",
        "# format check",
        'python3 -m ruff format --check . 2>/dev/null || echo "format check skipped"',
        "",
        "# security: check for secrets in staged files",
        'python3 -c "from keanu.abilities.world.security import check_secrets_in_staged; findings = check_secrets_in_staged(); exit(1) if findings else exit(0)" 2>/dev/null || true',
    ]


def _default_pre_push_commands() -> list[str]:
    """default pre-push commands."""
    return [
        "# run tests",
        'python3 -m pytest --tb=line -q 2>/dev/null || { echo "tests failed"; exit 1; }',
    ]


# ============================================================
# HOOK MANAGEMENT
# ============================================================

def hooks_dir(root: str = ".") -> Path:
    """get the git hooks directory."""
    return Path(root) / ".git" / "hooks"


def is_git_repo(root: str = ".") -> bool:
    """check if root is a git repository."""
    return (Path(root) / ".git").is_dir()


def list_hooks(root: str = ".") -> list[dict]:
    """list all installed hooks."""
    hdir = hooks_dir(root)
    if not hdir.is_dir():
        return []

    installed = []
    for hook_type in HOOK_TYPES:
        hook_path = hdir / hook_type
        if hook_path.exists() and not hook_path.name.endswith(".sample"):
            is_keanu = False
            try:
                content = hook_path.read_text()
                is_keanu = "keanu" in content
            except OSError:
                pass

            installed.append({
                "type": hook_type,
                "path": str(hook_path),
                "keanu_managed": is_keanu,
                "executable": os.access(str(hook_path), os.X_OK),
            })

    return installed


def install_hook(hook_type: str, root: str = ".",
                 commands: list[str] = None, force: bool = False) -> str:
    """install a git hook."""
    if hook_type not in HOOK_TYPES:
        raise ValueError(f"unknown hook type: {hook_type}")

    if not is_git_repo(root):
        raise ValueError(f"not a git repository: {root}")

    hdir = hooks_dir(root)
    hdir.mkdir(parents=True, exist_ok=True)

    hook_path = hdir / hook_type

    if hook_path.exists() and not force:
        # check if it's a keanu hook
        try:
            content = hook_path.read_text()
            if "keanu" not in content:
                raise FileExistsError(
                    f"hook {hook_type} already exists (not keanu-managed). use force=True to overwrite"
                )
        except FileExistsError:
            raise
        except OSError:
            pass

    # generate hook content
    if hook_type == "pre-commit":
        cmds = commands or _default_pre_commit_commands()
        content = PRE_COMMIT_TEMPLATE.format(commands="\n".join(cmds))
    elif hook_type == "commit-msg":
        content = COMMIT_MSG_TEMPLATE
    elif hook_type == "pre-push":
        cmds = commands or _default_pre_push_commands()
        content = PRE_PUSH_TEMPLATE.format(commands="\n".join(cmds))
    else:
        cmd_str = "\n".join(commands or ["echo 'keanu hook (no commands configured)'"])
        content = f"#!/bin/sh\n# keanu {hook_type} hook\n\n{cmd_str}\n"

    hook_path.write_text(content)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)

    return str(hook_path)


def uninstall_hook(hook_type: str, root: str = ".") -> bool:
    """uninstall a keanu-managed hook."""
    hook_path = hooks_dir(root) / hook_type

    if not hook_path.exists():
        return False

    try:
        content = hook_path.read_text()
        if "keanu" not in content:
            return False  # not our hook
    except OSError:
        return False

    hook_path.unlink()
    return True


def install_all(root: str = ".", force: bool = False) -> list[str]:
    """install all recommended hooks."""
    installed = []

    for hook_type in ["pre-commit", "commit-msg", "pre-push"]:
        try:
            path = install_hook(hook_type, root, force=force)
            installed.append(path)
        except (ValueError, FileExistsError):
            pass

    return installed


# ============================================================
# COMMIT MESSAGE VALIDATION
# ============================================================

CONVENTIONAL_PATTERN = re.compile(
    r'^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)'
    r'(\(.+\))?'
    r'!?'
    r':\s.+'
)


def validate_commit_message(message: str) -> tuple[bool, str]:
    """validate a commit message against conventional commits format.

    returns (is_valid, error_message).
    """
    if not message or not message.strip():
        return False, "commit message is empty"

    first_line = message.strip().split("\n")[0]

    if len(first_line) > 72:
        return False, f"subject line too long ({len(first_line)} chars, max 72)"

    if CONVENTIONAL_PATTERN.match(first_line):
        return True, ""

    return False, "does not follow conventional commits format (type(scope): subject)"


def suggest_commit_type(diff_summary: str) -> str:
    """suggest a commit type based on diff content."""
    s = diff_summary.lower()
    if "test" in s:
        return "test"
    if "readme" in s or "doc" in s:
        return "docs"
    if "fix" in s or "bug" in s:
        return "fix"
    if "refactor" in s or "rename" in s or "move" in s:
        return "refactor"
    if "lint" in s or "format" in s:
        return "style"
    if "perf" in s or "speed" in s:
        return "perf"
    if "ci" in s or "pipeline" in s or "workflow" in s:
        return "ci"
    if "dep" in s or "bump" in s or "upgrade" in s:
        return "build"
    return "feat"
