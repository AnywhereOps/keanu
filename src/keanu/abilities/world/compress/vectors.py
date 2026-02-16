"""vectors.py - the agent communication layer.

Seeds become vectors. Vectors find seeds.
Deterministic by default (hash-based). Semantic mode uses
behavioral feature extraction (20 named dimensions, explainable).
"""

from dataclasses import dataclass

import numpy as np

from .codec import Seed


@dataclass
class VectorEntry:
    """A seed stored in vector space."""
    vector: np.ndarray
    seed: Seed
    original_content: str


class VectorStore:
    """Numbers <-> Vectors. The agent layer.

    Two embedding strategies:
    1. DETERMINISTIC (default): seed hash spread across dimensions.
       Lossless by construction. Round trip guaranteed.
    2. SEMANTIC: swap in real embeddings for meaning-based search.
       The hash layer catches any drift.

    Swap-in point: replace embed_seed/embed_semantic with ChromaDB/FAISS calls.
    """

    def __init__(self, dim: int = 20):
        self.dim = dim
        self.entries: list[VectorEntry] = []

    def embed_seed(self, seed: Seed, content: str) -> np.ndarray:
        """Numbers -> Vector. Deterministic, hash-based."""
        vec = seed.to_flat_array(dim=self.dim)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        self.entries.append(VectorEntry(vector=vec, seed=seed, original_content=content))
        return vec

    def embed_semantic(self, seed: Seed, content: str) -> np.ndarray:
        """Semantic embedding via behavioral feature extraction.

        20 named dimensions, each 0-1. Every dimension is explainable.
        Truncated or zero-padded to match store dim.
        """
        from .behavioral import FeatureExtractor
        extractor = FeatureExtractor()
        raw = extractor.extract(content)
        # fit to store dimension
        vec = np.zeros(self.dim)
        n = min(self.dim, len(raw))
        vec[:n] = raw[:n]
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        self.entries.append(VectorEntry(vector=vec, seed=seed, original_content=content))
        return vec

    def nearest(self, query_vec: np.ndarray, k: int = 1) -> list[tuple[VectorEntry, float]]:
        """Vector -> Numbers. Cosine similarity search."""
        results = []
        for entry in self.entries:
            sim = float(np.dot(query_vec, entry.vector))
            results.append((entry, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def vector_to_seed(self, vec: np.ndarray) -> tuple[Seed, float, str]:
        """Full reverse: vector -> seed + confidence + original content."""
        matches = self.nearest(vec, k=1)
        if not matches:
            raise ValueError("Empty vector store")
        entry, similarity = matches[0]
        return entry.seed, similarity, entry.original_content
