from __future__ import annotations

"""
Dense retriever over textbook chunks using sentence-transformers.

Usage (CLI):
    uv run python eval/rag/dense_retriever.py "what is a deadlock"
"""

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from .index import ChunkRecord, load_chunks


MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass
class DenseIndex:
    model: SentenceTransformer
    embeddings: np.ndarray  # shape: (n_chunks, dim)
    chunks: List[ChunkRecord]

    @classmethod
    def from_chunks(cls, chunks: List[ChunkRecord]) -> "DenseIndex":
        model = SentenceTransformer(MODEL_NAME)
        texts = [c.text for c in chunks]
        emb = model.encode(texts, batch_size=64, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
        return cls(model=model, embeddings=emb, chunks=chunks)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[ChunkRecord, float]]:
        q_emb = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
        # Cosine similarity with L2-normalized vectors is just dot product
        sims = np.dot(self.embeddings, q_emb)
        idxs = np.argsort(-sims)[:top_k]
        results: List[Tuple[ChunkRecord, float]] = []
        for idx in idxs:
            score = float(sims[idx])
            results.append((self.chunks[int(idx)], score))
        return results


def _demo(query: str, top_k: int = 5) -> None:
    chunks = load_chunks()
    index = DenseIndex.from_chunks(chunks)
    results = index.search(query, top_k=top_k)
    print(f"Top {len(results)} dense results for: {query!r}")
    for ch, score in results:
        print("\n====", ch.id, "====")
        print(f"Score: {score:.3f}")
        print("Header:", ch.header_path)
        print("Type:", ch.chunk_type)
        print(ch.text[:400].replace("\n", " "), "...")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python eval/rag/dense_retriever.py \"your question here\"")
        raise SystemExit(1)
    _demo(" ".join(sys.argv[1:]))

