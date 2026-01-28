from __future__ import annotations

"""
BM25 retriever over textbook chunks.

Usage (CLI):
    uv run python eval/rag/bm25_retriever.py "what is a deadlock"
"""

from dataclasses import dataclass
from typing import List, Tuple

from rank_bm25 import BM25Okapi

from .index import ChunkRecord, load_chunks
from ..chunking.metadata_extractor import iter_tokens


@dataclass
class BM25Index:
    bm25: BM25Okapi
    chunks: List[ChunkRecord]

    @classmethod
    def from_chunks(cls, chunks: List[ChunkRecord]) -> "BM25Index":
        tokenized_docs = [list(iter_tokens(c.text)) for c in chunks]
        bm25 = BM25Okapi(tokenized_docs)
        return cls(bm25=bm25, chunks=chunks)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[ChunkRecord, float]]:
        query_tokens = list(iter_tokens(query))
        scores = self.bm25.get_scores(query_tokens)
        # Get top_k indices by score
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        results: List[Tuple[ChunkRecord, float]] = []
        for idx, score in indexed_scores[:top_k]:
            if score <= 0:
                continue
            results.append((self.chunks[idx], float(score)))
        return results


def _demo(query: str, top_k: int = 5) -> None:
    chunks = load_chunks()
    index = BM25Index.from_chunks(chunks)
    results = index.search(query, top_k=top_k)
    print(f"Top {len(results)} BM25 results for: {query!r}")
    for ch, score in results:
        print("\n====", ch.id, "====")
        print(f"Score: {score:.3f}")
        print("Header:", ch.header_path)
        print("Type:", ch.chunk_type)
        print(ch.text[:400].replace("\n", " "), "...")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python eval/rag/bm25_retriever.py \"your question here\"")
        raise SystemExit(1)
    _demo(" ".join(sys.argv[1:]))

