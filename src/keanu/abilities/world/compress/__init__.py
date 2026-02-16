"""compress: COEF instruction language, DNS content store, pattern codec, vector layer, span exporter."""

from .dns import ContentDNS, sha256
from .instructions import COEFInstruction, COEFProgram
from .executor import COEFExecutor
from .codec import PatternRegistry, COEFEncoder, COEFDecoder, Pattern, Seed, DecodeResult
from .vectors import VectorStore, VectorEntry
from .stack import COEFStack
from .exporter import COEFSpanExporter, register_span_patterns, SPAN_PATTERNS

__all__ = [
    "ContentDNS", "sha256",
    "COEFInstruction", "COEFProgram",
    "COEFExecutor",
    "PatternRegistry", "COEFEncoder", "COEFDecoder",
    "Pattern", "Seed", "DecodeResult",
    "VectorStore", "VectorEntry",
    "COEFStack",
    "COEFSpanExporter", "register_span_patterns", "SPAN_PATTERNS",
]
