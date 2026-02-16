"""firstrun.py - first-run experience and setup wizard.

makes sure `pip install keanu && keanu` works without chromadb or API key.
detects what's available, guides the user through setup, and degrades
gracefully when optional dependencies are missing.

in the world: the welcome mat. you can walk in and start using the place
even if you haven't brought all your furniture yet.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_SETUP_DONE_FILE = keanu_home() / ".setup_done"


@dataclass
class Dependency:
    """a dependency check result."""
    name: str
    available: bool
    required: bool
    message: str
    install_hint: str = ""


@dataclass
class SetupStatus:
    """overall setup status."""
    dependencies: list[Dependency] = field(default_factory=list)
    ready: bool = False
    warnings: list[str] = field(default_factory=list)
    setup_done: bool = False

    @property
    def missing_required(self) -> list[Dependency]:
        return [d for d in self.dependencies if d.required and not d.available]

    @property
    def missing_optional(self) -> list[Dependency]:
        return [d for d in self.dependencies if not d.required and not d.available]


# ============================================================
# DEPENDENCY CHECKS
# ============================================================

def check_python_version() -> Dependency:
    """check that Python is 3.10+."""
    import sys
    ok = sys.version_info >= (3, 10)
    return Dependency(
        name="python",
        available=ok,
        required=True,
        message=f"Python {sys.version_info.major}.{sys.version_info.minor}" if ok else "Python 3.10+ required",
    )


def check_anthropic_key() -> Dependency:
    """check for ANTHROPIC_API_KEY in environment."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    has_key = bool(key and len(key) > 10)
    return Dependency(
        name="anthropic_api_key",
        available=has_key,
        required=False,
        message="found" if has_key else "not set (cloud LLM unavailable)",
        install_hint="export ANTHROPIC_API_KEY=sk-ant-...",
    )


def check_ollama() -> Dependency:
    """check if ollama is installed and running."""
    has_binary = shutil.which("ollama") is not None
    running = False

    if has_binary:
        try:
            r = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=5,
            )
            running = r.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            pass

    available = has_binary and running
    if available:
        msg = "installed and running"
    elif has_binary:
        msg = "installed but not running (ollama serve)"
    else:
        msg = "not installed"

    return Dependency(
        name="ollama",
        available=available,
        required=False,
        message=msg,
        install_hint="curl -fsSL https://ollama.ai/install.sh | sh",
    )


def check_chromadb() -> Dependency:
    """check if chromadb is importable."""
    try:
        import chromadb  # noqa: F401
        return Dependency(
            name="chromadb",
            available=True,
            required=False,
            message="available",
        )
    except ImportError:
        return Dependency(
            name="chromadb",
            available=False,
            required=False,
            message="not installed (vector features unavailable)",
            install_hint="pip install chromadb",
        )


def check_rich() -> Dependency:
    """check if rich is importable (for REPL)."""
    try:
        import rich  # noqa: F401
        return Dependency(name="rich", available=True, required=False, message="available")
    except ImportError:
        return Dependency(
            name="rich",
            available=False,
            required=False,
            message="not installed (REPL formatting limited)",
            install_hint="pip install rich",
        )


def check_keanu_home() -> Dependency:
    """check that ~/.keanu/ directory exists."""
    home = keanu_home()
    exists = home.is_dir()
    if not exists:
        try:
            home.mkdir(parents=True, exist_ok=True)
            exists = True
        except OSError:
            pass

    return Dependency(
        name="keanu_home",
        available=exists,
        required=True,
        message=str(home) if exists else f"could not create {home}",
    )


def check_llm_available() -> Dependency:
    """check that at least one LLM backend is available."""
    has_cloud = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    has_ollama = shutil.which("ollama") is not None

    if has_cloud and has_ollama:
        msg = "cloud + local"
    elif has_cloud:
        msg = "cloud only"
    elif has_ollama:
        msg = "local only (ollama)"
    else:
        msg = "no LLM backend (set ANTHROPIC_API_KEY or install ollama)"

    return Dependency(
        name="llm_backend",
        available=has_cloud or has_ollama,
        required=False,
        message=msg,
        install_hint="export ANTHROPIC_API_KEY=sk-ant-... or install ollama",
    )


# ============================================================
# SETUP STATUS
# ============================================================

def check_setup() -> SetupStatus:
    """run all dependency checks and return setup status."""
    status = SetupStatus()

    status.dependencies = [
        check_python_version(),
        check_keanu_home(),
        check_llm_available(),
        check_anthropic_key(),
        check_ollama(),
        check_chromadb(),
        check_rich(),
    ]

    status.setup_done = _SETUP_DONE_FILE.exists()
    status.ready = len(status.missing_required) == 0

    # build warnings
    if not status.setup_done:
        status.warnings.append("first run: setup not yet completed")

    for dep in status.missing_optional:
        status.warnings.append(f"{dep.name}: {dep.message}")

    return status


def mark_setup_done():
    """mark first-run setup as complete."""
    _SETUP_DONE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETUP_DONE_FILE.write_text(f"setup completed\n")


def is_first_run() -> bool:
    """check if this is the first run."""
    return not _SETUP_DONE_FILE.exists()


# ============================================================
# SETUP WIZARD
# ============================================================

def format_status(status: SetupStatus) -> str:
    """format setup status as a human-readable string."""
    lines = ["keanu setup status", "=" * 40]

    for dep in status.dependencies:
        icon = "+" if dep.available else ("-" if dep.required else "~")
        tag = "required" if dep.required else "optional"
        lines.append(f"  [{icon}] {dep.name} ({tag}): {dep.message}")
        if not dep.available and dep.install_hint:
            lines.append(f"      hint: {dep.install_hint}")

    lines.append("")
    if status.ready:
        lines.append("ready to go.")
    else:
        lines.append("missing required dependencies:")
        for dep in status.missing_required:
            lines.append(f"  - {dep.name}: {dep.message}")

    if status.warnings:
        lines.append("")
        lines.append("warnings:")
        for w in status.warnings:
            lines.append(f"  - {w}")

    return "\n".join(lines)


def get_quickstart() -> str:
    """get quickstart instructions based on what's available."""
    status = check_setup()

    lines = ["keanu quickstart", "=" * 40, ""]

    if not status.ready:
        lines.append("fix required dependencies first:")
        for dep in status.missing_required:
            lines.append(f"  {dep.install_hint or dep.message}")
        return "\n".join(lines)

    # determine what features are available
    has_cloud = any(d.name == "anthropic_api_key" and d.available for d in status.dependencies)
    has_ollama = any(d.name == "ollama" and d.available for d in status.dependencies)
    has_chromadb = any(d.name == "chromadb" and d.available for d in status.dependencies)

    lines.append("available right now:")
    lines.append("  keanu                    # launch the REPL")
    lines.append("  keanu healthz            # system health check")

    if has_cloud or has_ollama:
        lines.append("  keanu do 'task'          # agent loop")
        lines.append("  keanu ask 'question'     # convergence")
        lines.append("  keanu dream 'goal'       # planning")

    lines.append("  keanu scan file.md       # three-primary color reading")
    lines.append("  keanu alive 'text'       # ALIVE-GREY-BLACK check")
    lines.append("  keanu abilities          # list all abilities")

    if not has_cloud and not has_ollama:
        lines.append("")
        lines.append("to unlock LLM features:")
        lines.append("  export ANTHROPIC_API_KEY=sk-ant-...")
        lines.append("  # or install ollama for local models")

    if not has_chromadb:
        lines.append("")
        lines.append("to unlock vector features (scan, detect):")
        lines.append("  pip install chromadb")
        lines.append("  keanu bake              # train the lenses")

    return "\n".join(lines)


def run_setup_wizard() -> SetupStatus:
    """run the first-time setup wizard. returns final status.

    non-interactive. checks everything and reports what's available.
    creates ~/.keanu/ if it doesn't exist. marks setup as done.
    """
    status = check_setup()

    if status.ready:
        mark_setup_done()

    return status
