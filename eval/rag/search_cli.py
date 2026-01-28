from __future__ import annotations

"""
Simple CLI to run hybrid BM25 + dense retrieval over chunks.

Recommended usage (run as a module so package imports work):

    uv run python -m eval.rag.search_cli "what is a deadlock"
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .bm25_retriever import BM25Index
from .dense_retriever import DenseIndex
from .index import ChunkRecord, load_chunks
from .query_understanding import (
    analyze,
    chunk_about_concept,
    chunk_negates_concept,
)
from .reranker import CrossEncoderReranker
from .rrf_merger import rrf_merge


DEFINITION_BOOST = 1.5   # multiplier for definition chunks about the concept
NEGATIVE_PENALTY = 0.25  # multiplier for chunks that negate the concept (e.g. non-deadlock)


@dataclass
class HybridSearcher:
    bm25_index: BM25Index
    dense_index: DenseIndex
    reranker: CrossEncoderReranker | None = None

    @classmethod
    def from_chunks(
        cls, chunks: List[ChunkRecord], *, use_reranker: bool = False
    ) -> "HybridSearcher":
        bm25 = BM25Index.from_chunks(chunks)
        dense = DenseIndex.from_chunks(chunks)
        reranker = CrossEncoderReranker() if use_reranker else None
        return cls(bm25_index=bm25, dense_index=dense, reranker=reranker)

    def search(
        self, query: str, top_k: int = 5, *, intent=None
    ) -> List[Tuple[ChunkRecord, float]]:
        if intent is None:
            intent = analyze(query)

        # Use a slightly larger candidate pool so that the reranker and
        # heuristics have room to work.
        candidate_k = max(top_k * 3, 20)

        bm25_results = self.bm25_index.search(query, top_k=candidate_k)
        dense_results = self.dense_index.search(query, top_k=candidate_k)

        bm25_ids = [(c.id, s) for c, s in bm25_results]
        dense_ids = [(c.id, s) for c, s in dense_results]

        # Merge to a larger candidate pool so definition boost and reranker
        # can surface the best chunks.
        merged = rrf_merge([bm25_ids, dense_ids], k=candidate_k)

        id_to_chunk: Dict[str, ChunkRecord] = {c.id: c for c, _ in bm25_results + dense_results}

        scored: List[Tuple[ChunkRecord, float]] = []
        for cid, score in merged:
            if cid not in id_to_chunk:
                continue
            ch = id_to_chunk[cid]

            # 1) Hard‑filter clearly noisy chunk types.
            if ch.chunk_type in ("exercise", "references", "bibliography", "citations"):
                continue

            header_lower = ch.header_path.lower()

            # 2) Hard‑filter obvious back‑of‑chapter material by header text.
            #    We keep "Problems" because many problem sections in these books
            #    contain rich explanatory text, but we drop Appendices,
            #    bibliographies, and exercise/review‑question sections.
            if any(
                marker in header_lower
                for marker in (
                    "references",
                    "selected bibliography",
                    "bibliography",
                    "further reading",
                    "appendix",
                    "exercises",
                    "review questions",
                )
            ):
                continue

            # 3) Use query‑level negative signals (if any) to skip confuser chunks
            #    e.g., TLS record/auth protocols when the user asked about TCP 3‑way handshake.
            if getattr(intent, "negative_signals", None):
                prefix_text = (ch.header_path + " " + ch.text[:200]).lower()
                if any(sig in prefix_text for sig in intent.negative_signals):
                    continue

            s = score

            # 4) Down‑weight chunks that explicitly *negate* the concept (non‑deadlock, etc.).
            if intent.concept and chunk_negates_concept(ch, intent.concept):
                s *= NEGATIVE_PENALTY

            # 5) Boost clean definition chunks when the query is clearly definition‑seeking.
            if intent.is_definition_seeking and ch.chunk_type == "definition":
                if intent.concept is None or chunk_about_concept(ch, intent.concept):
                    s *= DEFINITION_BOOST

            # 6) For procedural ("how to") queries, slightly prefer algorithm / section chunks.
            if getattr(intent, "is_procedural", False) and ch.chunk_type in (
                "algorithm",
                "section",
            ):
                s *= 1.10

            # 7) For comparative queries, slightly prefer protocol / comparison / section chunks.
            if getattr(intent, "is_comparative", False) and ch.chunk_type in (
                "protocol",
                "comparison",
                "section",
            ):
                s *= 1.05

            scored.append((ch, s))

        # If we have a reranker, use it as a second stage; otherwise fall back
        # to the hybrid score.
        if self.reranker is not None:
            reranked = self.reranker.rerank(query, scored)
            return reranked[:top_k]

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


def _demo(query: str, top_k: int = 5) -> None:
    intent = analyze(query)
    if intent.is_definition_seeking:
        print(f"Query intent: definition-seeking (concept: {intent.concept or '—'}) → boosting definition chunks")
    chunks = load_chunks()
    # For the demo, enable the reranker so CLI runs reflect the full stack.
    searcher = HybridSearcher.from_chunks(chunks, use_reranker=True)
    results = searcher.search(query, top_k=top_k, intent=intent)
    print(f"Top {len(results)} hybrid results (BM25 + dense) for: {query!r}")
    for ch, score in results:
        print("\n====", ch.id, "====")
        print(f"Score: {score:.4f}")
        print("Header:", ch.header_path)
        print("Type:", ch.chunk_type)
        print(ch.text[:400].replace("\n", " "), "...")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python eval/rag/search_cli.py \"your question here\"")
        raise SystemExit(1)
    _demo(" ".join(sys.argv[1:]))

