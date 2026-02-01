"""
Dense semantic retriever using sentence-transformers.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from .index import CHUNKS_PATH, ChunkRecord

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_CACHE_PATH = CHUNKS_PATH.with_name("embeddings_cache.npz")


def _load_cached_embeddings(chunks: List[ChunkRecord]) -> np.ndarray | None:
    """Try to load cached embeddings matching the given chunk IDs."""
    if not EMBEDDING_CACHE_PATH.exists():
        return None
    try:
        data = np.load(EMBEDDING_CACHE_PATH, allow_pickle=True)
        cached_ids = data["chunk_ids"].tolist()
        current_ids = [c.id for c in chunks]
        if cached_ids == current_ids:
            return data["embeddings"]
    except Exception as e:
        logger.warning("Failed to load embedding cache: %s", e)
        return None
    return None


def _save_cached_embeddings(embeddings: np.ndarray, chunks: List[ChunkRecord]) -> None:
    """Persist embeddings to disk for faster subsequent startups."""
    try:
        EMBEDDING_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        chunk_ids = np.array([c.id for c in chunks], dtype=object)
        np.savez(EMBEDDING_CACHE_PATH, embeddings=embeddings, chunk_ids=chunk_ids)
    except Exception as e:
        logger.warning("Failed to save embedding cache: %s", e)


@dataclass
class DenseIndex:
    """Dense semantic retrieval index."""

    model: SentenceTransformer
    embeddings: np.ndarray  # shape: (n_chunks, dim)
    chunks: List[ChunkRecord]

    @classmethod
    def from_chunks(cls, chunks: List[ChunkRecord]) -> "DenseIndex":
        """Build dense index from chunks with caching."""
        model = SentenceTransformer(EMBEDDING_MODEL)

        emb = _load_cached_embeddings(chunks)
        if emb is None:
            texts = [c.text for c in chunks]
            emb = model.encode(
                texts,
                batch_size=64,
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            _save_cached_embeddings(emb, chunks)

        return cls(model=model, embeddings=emb, chunks=chunks)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[ChunkRecord, float]]:
        """Search for top-k chunks using cosine similarity."""
        q_emb = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]
        sims = np.dot(self.embeddings, q_emb)
        idxs = np.argsort(-sims)[:top_k]
        results: List[Tuple[ChunkRecord, float]] = []
        for idx in idxs:
            score = float(sims[idx])
            results.append((self.chunks[int(idx)], score))
        return results
