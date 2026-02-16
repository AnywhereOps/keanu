"""environ.py - environment detection and management.

detects virtual environments, docker, CI systems, OS capabilities.
knows what tools are available and what constraints exist.

in the world: the surveyor. before you build, you need to know
what ground you're standing on.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Environment:
    """detected environment information."""
    python_version: str = ""
    python_path: str = ""
    virtualenv: str = ""
    virtualenv_type: str = ""  # venv, conda, poetry, pipenv, none
    os_name: str = ""
    arch: str = ""
    in_docker: bool = False
    in_ci: bool = False
    ci_system: str = ""
    shell: str = ""
    tools: dict = field(default_factory=dict)  # tool -> version
    project_root: str = ""

    def to_dict(self) -> dict:
        return {
            "python_version": self.python_version,
            "python_path": self.python_path,
            "virtualenv": self.virtualenv,
            "virtualenv_type": self.virtualenv_type,
            "os_name": self.os_name,
            "arch": self.arch,
            "in_docker": self.in_docker,
            "in_ci": self.in_ci,
            "ci_system": self.ci_system,
            "shell": self.shell,
            "tools": self.tools,
        }


# ============================================================
# DETECTION
# ============================================================

def detect_python() -> tuple[str, str]:
    """detect Python version and path."""
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return version, sys.executable


def detect_virtualenv() -> tuple[str, str]:
    """detect if running in a virtual environment and its type.

    returns (path, type) where type is venv/conda/poetry/pipenv/none.
    """
    # check VIRTUAL_ENV (standard venv/virtualenv)
    venv = os.environ.get("VIRTUAL_ENV", "")
    if venv:
        return venv, "venv"

    # check CONDA_DEFAULT_ENV
    conda = os.environ.get("CONDA_DEFAULT_ENV", "")
    if conda:
        conda_prefix = os.environ.get("CONDA_PREFIX", "")
        return conda_prefix or conda, "conda"

    # check for poetry
    if os.environ.get("POETRY_ACTIVE"):
        return os.environ.get("VIRTUAL_ENV", ""), "poetry"

    # check for pipenv
    if os.environ.get("PIPENV_ACTIVE"):
        return os.environ.get("VIRTUAL_ENV", ""), "pipenv"

    # check sys.prefix vs sys.base_prefix
    if sys.prefix != sys.base_prefix:
        return sys.prefix, "venv"

    return "", "none"


def detect_docker() -> bool:
    """detect if running inside a Docker container."""
    # check /.dockerenv
    if Path("/.dockerenv").exists():
        return True

    # check cgroup
    try:
        cgroup = Path("/proc/1/cgroup")
        if cgroup.exists():
            content = cgroup.read_text()
            if "docker" in content or "containerd" in content:
                return True
    except OSError:
        pass

    return False


def detect_ci() -> tuple[bool, str]:
    """detect if running in a CI system.

    returns (is_ci, system_name).
    """
    ci_vars = {
        "GITHUB_ACTIONS": "github_actions",
        "GITLAB_CI": "gitlab",
        "CIRCLECI": "circleci",
        "TRAVIS": "travis",
        "JENKINS_URL": "jenkins",
        "BITBUCKET_PIPELINE_UUID": "bitbucket",
        "CODEBUILD_BUILD_ID": "codebuild",
        "BUILDKITE": "buildkite",
        "DRONE": "drone",
        "SEMAPHORE": "semaphore",
    }

    for var, name in ci_vars.items():
        if os.environ.get(var):
            return True, name

    # generic CI check
    if os.environ.get("CI"):
        return True, "unknown"

    return False, ""


def detect_shell() -> str:
    """detect the current shell."""
    shell = os.environ.get("SHELL", "")
    if shell:
        return Path(shell).name
    return ""


def detect_tools() -> dict[str, str]:
    """detect available development tools and their versions."""
    tools = {}

    checks = {
        "git": ["git", "--version"],
        "docker": ["docker", "--version"],
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "pip": ["pip", "--version"],
        "poetry": ["poetry", "--version"],
        "ruff": ["ruff", "--version"],
        "pytest": ["python3", "-m", "pytest", "--version"],
        "make": ["make", "--version"],
        "curl": ["curl", "--version"],
        "ollama": ["ollama", "--version"],
    }

    for name, cmd in checks.items():
        if shutil.which(cmd[0]):
            try:
                r = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0:
                    # extract version from first line
                    version = r.stdout.strip().split("\n")[0]
                    tools[name] = version[:60]
            except (subprocess.TimeoutExpired, OSError):
                tools[name] = "installed (version unknown)"

    return tools


def detect_project_root(start: str = ".") -> str:
    """find the project root by walking up looking for markers."""
    markers = [
        "pyproject.toml", "setup.py", "setup.cfg",
        "package.json", "go.mod", "Cargo.toml",
        ".git", "Makefile",
    ]

    current = Path(start).resolve()
    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                return str(current)
        current = current.parent

    return str(Path(start).resolve())


# ============================================================
# FULL SCAN
# ============================================================

def detect_environment(include_tools: bool = True) -> Environment:
    """run all environment detection."""
    import platform

    py_version, py_path = detect_python()
    venv_path, venv_type = detect_virtualenv()
    in_docker = detect_docker()
    in_ci, ci_system = detect_ci()

    env = Environment(
        python_version=py_version,
        python_path=py_path,
        virtualenv=venv_path,
        virtualenv_type=venv_type,
        os_name=platform.system(),
        arch=platform.machine(),
        in_docker=in_docker,
        in_ci=in_ci,
        ci_system=ci_system,
        shell=detect_shell(),
        project_root=detect_project_root(),
    )

    if include_tools:
        env.tools = detect_tools()

    return env


def format_environment(env: Environment) -> str:
    """format environment info for display."""
    lines = [
        "Environment",
        "=" * 40,
        f"  Python: {env.python_version} ({env.python_path})",
        f"  OS: {env.os_name} {env.arch}",
        f"  Shell: {env.shell}",
    ]

    if env.virtualenv:
        lines.append(f"  Virtualenv: {env.virtualenv_type} ({env.virtualenv})")
    else:
        lines.append("  Virtualenv: none")

    if env.in_docker:
        lines.append("  Docker: yes")
    if env.in_ci:
        lines.append(f"  CI: {env.ci_system}")

    if env.tools:
        lines.append("")
        lines.append("  Tools:")
        for name, version in sorted(env.tools.items()):
            lines.append(f"    {name}: {version}")

    return "\n".join(lines)
