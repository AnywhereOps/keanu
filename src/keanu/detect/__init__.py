"""detect: interpret readings using color theory and pattern awareness."""

from .mood import detect, SynthesisReading
from .engine import run as detect_pattern, EMPATHY_DETECTORS

# Future: pattern detectors (files deleted, may rebuild)
# "sycophancy", "capture", "generalization", "zero_sum",
# "safety_theater", "inconsistency", "grievance", "stability"

# Active detectors. Used by CLI `keanu detect all`.
DETECTORS = list(EMPATHY_DETECTORS)

__all__ = [
    "detect", "SynthesisReading",
    "detect_pattern",
    "EMPATHY_DETECTORS",
    "DETECTORS",
]
