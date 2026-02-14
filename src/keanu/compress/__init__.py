"""compress: COEF instruction language, DNS content store, pattern codec."""

from .dns import ContentDNS, sha256
from .instructions import COEFInstruction, COEFProgram
from .executor import COEFExecutor
from .codec import PatternRegistry, COEFEncoder, COEFDecoder, Pattern, Seed, DecodeResult

__all__ = [
    "ContentDNS", "sha256",
    "COEFInstruction", "COEFProgram",
    "COEFExecutor",
    "PatternRegistry", "COEFEncoder", "COEFDecoder",
    "Pattern", "Seed", "DecodeResult",
]
