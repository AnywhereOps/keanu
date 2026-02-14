"""stack.py - the full COEF stack. Words <-> Numbers <-> Vectors.

One object. Five methods. Every layer is reversible. Every transition verified.

    WORDS                          (human layer)
      |  encode                        ^ decode
    NUMBERS                        (seed layer)
      |  embed                         ^ nearest_seed
    VECTORS                        (agent layer)
"""

import hashlib

import numpy as np

from .codec import COEFEncoder, COEFDecoder, PatternRegistry, Seed
from .dns import ContentDNS
from .vectors import VectorStore


class COEFStack:
    """The whole thing. One object. Five methods.

    UP:   words_to_numbers() -> numbers_to_vector()
    DOWN: vector_to_numbers() -> numbers_to_words()
    FULL: round_trip() -> verify at every layer
    """

    def __init__(self, registry: PatternRegistry, dns: ContentDNS = None,
                 vector_dim: int = 20):
        self.registry = registry
        self.encoder = COEFEncoder(registry)
        self.decoder = COEFDecoder(registry)
        self.dns = dns or ContentDNS()
        self.vectors = VectorStore(dim=vector_dim)

    # --- UP ---

    def words_to_numbers(self, content: str, pattern_id: str,
                         anchors: dict = None) -> Seed:
        """Layer 1 UP: human-readable content -> Seed."""
        seed = self.encoder.encode(content, pattern_id, anchor_overrides=anchors)
        self.dns.store(content)
        return seed

    def numbers_to_vector(self, seed: Seed, content: str,
                          semantic: bool = False) -> np.ndarray:
        """Layer 2 UP: Seed -> Vector."""
        if semantic:
            return self.vectors.embed_semantic(seed, content)
        return self.vectors.embed_seed(seed, content)

    # --- DOWN ---

    def vector_to_numbers(self, vec: np.ndarray) -> tuple[Seed, float]:
        """Layer 2 DOWN: Vector -> Seed + confidence."""
        seed, similarity, _ = self.vectors.vector_to_seed(vec)
        return seed, similarity

    def numbers_to_words(self, seed: Seed, use_dns: bool = True) -> dict:
        """Layer 1 DOWN: Seed -> human-readable content."""
        if use_dns:
            result = self.decoder.decode_from_dns(seed.content_hash, self.dns)
            if result:
                return {
                    "content": result.content,
                    "is_lossless": result.is_lossless,
                    "method": "dns_lookup",
                }
        result = self.decoder.decode(seed)
        return {
            "content": result.content,
            "is_lossless": result.is_lossless,
            "method": "template_expansion",
        }

    # --- FULL ROUND TRIP ---

    def round_trip(self, content: str, pattern_id: str, anchors: dict = None,
                   semantic: bool = False) -> dict:
        """Words -> Numbers -> Vectors -> Numbers -> Words. Verified."""
        results = {"layers": [], "final_lossless": False}

        # UP: Words -> Numbers
        seed = self.words_to_numbers(content, pattern_id, anchors)
        results["layers"].append({
            "transition": "WORDS -> NUMBERS",
            "pattern": seed.pattern_id,
            "hash": seed.content_hash[:16],
            "anchors": len(seed.anchors),
        })

        # UP: Numbers -> Vector
        vec = self.numbers_to_vector(seed, content, semantic=semantic)
        results["layers"].append({
            "transition": "NUMBERS -> VECTOR",
            "dim": len(vec),
            "method": "semantic" if semantic else "deterministic",
        })

        # DOWN: Vector -> Numbers
        recovered_seed, similarity = self.vector_to_numbers(vec)
        hash_match = recovered_seed.content_hash == seed.content_hash
        results["layers"].append({
            "transition": "VECTOR -> NUMBERS",
            "similarity": round(similarity, 6),
            "hash_match": hash_match,
        })

        # DOWN: Numbers -> Words
        decoded = self.numbers_to_words(recovered_seed)
        results["layers"].append({
            "transition": "NUMBERS -> WORDS",
            "is_lossless": decoded["is_lossless"],
            "method": decoded.get("method", "template_expansion"),
        })

        # VERIFY
        final_hash = hashlib.sha256(decoded["content"].encode()).hexdigest()
        original_hash = hashlib.sha256(content.encode()).hexdigest()
        results["final_lossless"] = final_hash == original_hash
        results["original"] = content
        results["recovered"] = decoded["content"]

        return results
