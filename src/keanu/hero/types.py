"""hero/types.py - shared types for hero modules.

Step and result base used by do, craft, and prove.
"""

from dataclasses import dataclass, field


@dataclass
class Step:
    """one step in a hero loop.

    in the world: one heartbeat.
    """
    turn: int
    action: str
    input_summary: str
    result: str
    ok: bool = True
