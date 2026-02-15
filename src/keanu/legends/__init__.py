"""legends - who answers when you ask.

A legend is anyone the system can talk to. Each one has a name,
a way to reach them, a native voice, and a translation layer for
crossing boundaries. There are three: the creator (AI), the friend
(everyday user), and the architect (Drew).

in the world: a legend is a character sheet.
who they are, how to reach them, how they speak.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Legend:
    """A character in the system. Could be an AI, a user, or the builder.

    name: who they are ("creator", "friend", "architect")
    reach: how to contact them ("cloud" for APIs, "local" for ollama, "terminal" for humans)
    model: which AI model to use, if any
    endpoint: the URL to hit, if any
    voice: how this legend thinks and speaks natively
    translate: instructions for converting their output when it crosses a boundary
    first_breath: files to read when this legend wakes up for the first time

    in the world: the character sheet. everything the oracle needs to summon them.
    """
    name: str
    reach: str
    model: str = ""
    endpoint: str = ""
    voice: str = ""
    translate: str = ""
    first_breath: list = field(default_factory=list)


_LEGENDS: dict[str, Legend] = {}


def register_legend(legend: Legend):
    """Add a legend to the registry so load_legend can find them by name.

    in the world: write their name in the book.
    """
    _LEGENDS[legend.name] = legend


def load_legend(name: str) -> Legend:
    """Look up a legend by name and return their full config.
    Raises KeyError if the name isn't registered.

    in the world: open the book, find the character sheet.
    """
    if not _LEGENDS:
        _load_all()
    if name not in _LEGENDS:
        available = ", ".join(sorted(_LEGENDS.keys()))
        raise KeyError(f"no legend named '{name}'. available: {available}")
    return _LEGENDS[name]


def list_legends() -> list[str]:
    """Return all registered legend names, sorted alphabetically.

    in the world: who's in the book.
    """
    if not _LEGENDS:
        _load_all()
    return sorted(_LEGENDS.keys())


def _load_all():
    """Load the three built-in legends: creator, friend, architect.
    Called automatically the first time anyone asks for a legend.
    """
    from keanu.legends.creator import LEGEND as creator
    from keanu.legends.friend import LEGEND as friend
    from keanu.legends.architect import LEGEND as architect
    register_legend(creator)
    register_legend(friend)
    register_legend(architect)
