"""craft.py - the coder. now a config of the unified loop.

kept as a module for backwards compatibility. the real loop lives in do.py.
"""

from keanu.hero.do import (  # noqa: F401
    craft,
    LoopResult as CraftResult,
    Step as CraftStep,
    HANDS,
    CRAFT_CONFIG,
    CRAFT_PROMPT,
    AgentLoop,
    call_oracle,
    try_interpret,
    Feel,
    _REGISTRY,
)
