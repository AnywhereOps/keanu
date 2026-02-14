"""keanu: scans through three color lenses, compresses what matters, finds truth."""

from keanu.detect import detect, SynthesisReading, DETECTORS
from keanu.signal import Signal, AliveState, from_sequence, core, read_emotion
from keanu.alive import diagnose, AliveReading
from keanu.pulse import Pulse, PulseReading
from keanu.memory import Memory, MemberberryStore, PlanGenerator
from keanu.compress import ContentDNS, COEFStack, COEFSpanExporter

__all__ = [
    "detect", "SynthesisReading", "DETECTORS",
    "Signal", "AliveState", "from_sequence", "core", "read_emotion",
    "diagnose", "AliveReading",
    "Pulse", "PulseReading",
    "Memory", "MemberberryStore", "PlanGenerator",
    "ContentDNS", "COEFStack", "COEFSpanExporter",
]
