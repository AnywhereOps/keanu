"""prove.py - the scientist. now a config of the unified loop.

kept as a module for backwards compatibility. the real loop lives in do.py.
"""

from keanu.hero.do import (  # noqa: F401
    prove,
    LoopResult as ProveResult,
    Step as ProveStep,
    EVIDENCE_TOOLS,
    PROVE_CONFIG,
    PROVE_PROMPT,
    AgentLoop,
    call_oracle,
    try_interpret,
    Feel,
    _REGISTRY,
)
