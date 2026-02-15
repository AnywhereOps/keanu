"""abilities: convergence as architecture.

an ability is ash. a proven, codified capability that used to require
fire (a Claude call into open possibility space) but converged into
something local and deterministic. no LLM needed. pure actuality.

the more abilities exist, the more gets handled without an API call.
the flywheel IS convergence applied to the system itself.

the action bar:
    scout       survey the land. see what's missing.
    recall      summon memories. they come to you.
    scry        see hidden patterns without touching the source.
    attune      three-key attunement (R/Y/B). you go in different.
    purge       check for debuffs. grey and black are debuffs.
    decipher    decode the signal. rogue energy.
    soulstone   capture the essence, store it. pure warlock.
    inspect     inspect target. gear, stats, everything.
    recount     count what you have. day of reckoning.
"""

from pathlib import Path
from typing import Optional


# ============================================================
# ABILITY PROTOCOL
# ============================================================

class Ability:
    """Base class for abilities. An ability is a bounded, structured task.

    Subclass this, set name/description/keywords, implement can_handle
    and execute. Decorate with @ability to auto-register.
    """

    name: str = ""
    description: str = ""
    keywords: list = []

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        """Check if this ability can handle the prompt.

        Returns:
            (can_handle: bool, confidence: float 0.0-1.0)
        """
        raise NotImplementedError

    def execute(self, prompt: str, context: dict = None) -> dict:
        """Execute the ability.

        Returns:
            {
                "success": bool,
                "result": str,       # human-readable
                "data": dict,        # structured output
            }
        """
        raise NotImplementedError


# ============================================================
# REGISTRY
# ============================================================

_REGISTRY: dict[str, Ability] = {}


def ability(cls):
    """Decorator. Registers an ability class."""
    instance = cls()
    _REGISTRY[instance.name] = instance
    return cls


def find_ability(prompt: str, context: dict = None,
                 threshold: float = 0.6) -> tuple:
    """Find the best matching ability for a prompt.

    Returns:
        (ability, confidence) or (None, 0.0) if no match above threshold.
    """
    best = None
    best_conf = 0.0

    for ab in _REGISTRY.values():
        can, conf = ab.can_handle(prompt, context)
        if can and conf > best_conf:
            best = ab
            best_conf = conf

    if best_conf >= threshold:
        return best, best_conf
    return None, 0.0


def list_abilities() -> list[dict]:
    """List all registered abilities."""
    return [
        {
            "name": ab.name,
            "description": ab.description,
            "keywords": ab.keywords,
        }
        for ab in _REGISTRY.values()
    ]


# ============================================================
# BUILT-IN ABILITIES
# ============================================================

@ability
class TodoAbility(Ability):
    """Wraps the existing TodoScan as an ability."""

    name = "scout"
    description = "Survey the land. See what's missing."
    keywords = ["todo", "tasks", "what's next", "project status", "gaps", "generate todo", "scout"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        if any(phrase in p for phrase in ["generate todo", "update todo", "scan project", "write todo"]):
            return True, 0.9

        if any(kw in p for kw in self.keywords):
            return True, 0.6

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.abilities.todo import TodoScan

        project_root = "."
        if context and context.get("project_root"):
            project_root = context["project_root"]

        root = Path(project_root).resolve()
        scan = TodoScan(project_root=root)
        scan.scan_all()
        cool, warm, hot, done = scan.write_todo()

        total = len(cool) + len(warm) + len(hot)
        return {
            "success": True,
            "result": f"Generated TODO.md: {total} tasks ({len(cool)} cool, {len(warm)} warm, {len(hot)} hot)",
            "data": {
                "cool": len(cool),
                "warm": len(warm),
                "hot": len(hot),
                "done": len(done),
            },
        }


# register external abilities (decorator runs at import time)
import keanu.abilities.recall      # noqa: F401
import keanu.abilities.scry        # noqa: F401
import keanu.abilities.attune      # noqa: F401
import keanu.abilities.purge       # noqa: F401
import keanu.abilities.decipher    # noqa: F401
import keanu.abilities.soulstone   # noqa: F401
import keanu.abilities.inspect_ability  # noqa: F401
import keanu.abilities.recount     # noqa: F401
import keanu.abilities.hands       # noqa: F401
