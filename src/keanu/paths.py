"""paths.py - one place for all keanu paths.

every file that touches ~/.keanu/ or ~/memberberries/ imports from here.
no more hardcoded Path.home() scattered across the codebase.
"""

from pathlib import Path


def keanu_home() -> Path:
    """~/.keanu/ - the root of all keanu state."""
    return Path.home() / ".keanu"


def ensure_dir(path: Path) -> Path:
    """mkdir -p. returns the path for chaining."""
    path.mkdir(parents=True, exist_ok=True)
    return path


# -- ~/.keanu/ paths --
GRIMOIRE = keanu_home() / "grimoire.json"
MISS_FILE = keanu_home() / "misses.jsonl"
MISTAKES_FILE = keanu_home() / "mistakes.jsonl"
METRICS_FILE = keanu_home() / "metrics.jsonl"
COEF_DIR = keanu_home() / "coef"

# -- ~/.memberberry/ paths --
MEMBERBERRY_DIR = Path.home() / ".memberberry"
MEMORIES_FILE = MEMBERBERRY_DIR / "memories.json"
PLANS_FILE = MEMBERBERRY_DIR / "plans.json"
CONFIG_FILE = MEMBERBERRY_DIR / "config.json"

# -- ~/memberberries/ (shared git-backed) --
SHARED_DIR = Path.home() / "memberberries"
