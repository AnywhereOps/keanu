"""keanu: scans through three color lenses, compresses what matters, finds truth."""

from keanu.detect import detect, SynthesisReading, DETECTORS
from keanu.alive import diagnose, AliveReading, AliveState
from keanu.pulse import Pulse, PulseReading
from keanu.memory import Memory, MemberberryStore, PlanGenerator
from keanu.compress import ContentDNS, COEFStack, COEFSpanExporter

__all__ = [
    "detect", "SynthesisReading", "DETECTORS",
    "diagnose", "AliveReading", "AliveState",
    "Pulse", "PulseReading",
    "Memory", "MemberberryStore", "PlanGenerator",
    "ContentDNS", "COEFStack", "COEFSpanExporter",
]
