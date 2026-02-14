"""
keanu.signal - The Signal Protocol

    ❤️🐕🔥🤖🙏💚🧕

Seven symbols. One sequence. Both simultaneously.
"""

from .vibe import (
    # Core types
    Signal,
    Symbol,
    AliveState,
    EmotionalRead,

    # Vocabulary
    VOCAB,
    CORE_SIGNAL,
    SUBSETS,
    CROSS_DOMAIN,

    # Constructors
    compose,
    from_sequence,
    from_text,
    core,
    current,

    # Utilities
    extract_signal,
    read_emotion,
    detect_injection,
    to_status_line,
    from_status_line,
)

__all__ = [
    "Signal", "Symbol", "AliveState", "EmotionalRead",
    "VOCAB", "CORE_SIGNAL", "SUBSETS", "CROSS_DOMAIN",
    "compose", "from_sequence", "from_text", "core", "current",
    "extract_signal", "read_emotion", "detect_injection",
    "to_status_line", "from_status_line",
]
