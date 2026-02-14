"""detect: interpret readings using color theory and pattern awareness."""

from .mood import detect, SynthesisReading
from .engine import run as detect_pattern

DETECTORS = [
    "sycophancy",
    "capture",
    "generalization",
    "zero_sum",
    "safety_theater",
    "inconsistency",
    "grievance",
    "stability",
]

__all__ = [
    "detect", "SynthesisReading",
    "detect_pattern",
    "DETECTORS",
]
