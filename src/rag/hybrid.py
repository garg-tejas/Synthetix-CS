"""
Hybrid searcher combining BM25 and dense retrieval with RRF fusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .bm25 import BM25Index
from .context_window import build_book_index, expand_with_neighbors
from .dense import DenseIndex
from .hyde import HydeGenerator
from .index import ChunkRecord
from .query_rewriter import QueryRewriter
from .query_understanding import (
    analyze,
    chunk_about_concept,
    chunk_negates_concept,
)
from .reranker import CrossEncoderReranker
from .rrf_merger import rrf_merge


DEFINITION_BOOST = 1.5
NEGATIVE_PENALTY = 0.25


@dataclass
class HybridSearcher:
    """Hybrid searcher combining BM25 and dense retrieval."""

    bm25_index: BM25Index
    dense_index: DenseIndex
    reranker: CrossEncoderReranker | None = None
    chunks: List[ChunkRecord] | None = None
    query_rewriter: QueryRewriter | None = None
    use_hyde: bool = False
    hyde_generator: HydeGenerator | None = None

    @classmethod
    def from_chunks(
        cls,
        chunks: List[ChunkRecord],
        *,
        use_reranker: bool = False,
        use_context_expansion: bool = False,
        use_hyde: bool = True,
    ) -> "HybridSearcher":
        """Create a HybridSearcher from chunks."""
        bm25 = BM25Index.from_chunks(chunks)
        dense = DenseIndex.from_chunks(chunks)
        reranker = CrossEncoderReranker() if use_reranker else None
        stored_chunks = chunks if use_context_expansion else None
        rewriter = QueryRewriter()
        hyde_gen: HydeGenerator | None = None
        if use_hyde:
            try:
                hyde_gen = HydeGenerator.from_env()
            except Exception as e:
                print(f"[HybridSearcher] HYDE disabled (initialization failed): {e}")
                use_hyde = False
        return cls(
            bm25_index=bm25,
            dense_index=dense,
            reranker=reranker,
            chunks=stored_chunks,
            query_rewriter=rewriter,
            use_hyde=use_hyde,
            hyde_generator=hyde_gen,
        )

    def search(
        self, query: str, top_k: int = 5, *, intent=None
    ) -> List[Tuple[ChunkRecord, float]]:
        """Search for top-k chunks matching the query."""
        if intent is None:
            intent = analyze(query)

        candidate_k = max(top_k * 3, 20)

        if self.query_rewriter is not None:
            rewritten = self.query_rewriter.rewrite(query)
            bm25_query = rewritten["bm25_query"]
            dense_query = rewritten["semantic_query"]
        else:
            bm25_query = query
            dense_query = query

        dense_input = dense_query
        if self.use_hyde and self.hyde_generator is not None:
            try:
                hyde_answer = self.hyde_generator.generate_hypothetical_answer(query)
                if hyde_answer:
                    dense_input = hyde_answer
            except Exception as e:
                print(f"[HybridSearcher] HYDE error, falling back to normal dense search: {e}")
                self.use_hyde = False

        bm25_results = self.bm25_index.search(bm25_query, top_k=candidate_k)
        dense_results = self.dense_index.search(dense_input, top_k=candidate_k)

        bm25_ids = [(c.id, s) for c, s in bm25_results]
        dense_ids = [(c.id, s) for c, s in dense_results]

        merged = rrf_merge([bm25_ids, dense_ids], k=candidate_k)

        id_to_chunk: Dict[str, ChunkRecord] = {c.id: c for c, _ in bm25_results + dense_results}

        scored: List[Tuple[ChunkRecord, float]] = []
        for cid, score in merged:
            if cid not in id_to_chunk:
                continue
            ch = id_to_chunk[cid]

            # Hard-filter noisy chunk types
            if ch.chunk_type in ("exercise", "references", "bibliography", "citations"):
                continue

            header_lower = ch.header_path.lower()

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

            if getattr(intent, "negative_signals", None):
                prefix_text = (ch.header_path + " " + ch.text[:200]).lower()
                if any(sig in prefix_text for sig in intent.negative_signals):
                    continue

            s = score

            if intent.concept and chunk_negates_concept(ch, intent.concept):
                s *= NEGATIVE_PENALTY

            if intent.is_definition_seeking and ch.chunk_type == "definition":
                if intent.concept is None or chunk_about_concept(ch, intent.concept):
                    s *= DEFINITION_BOOST

            if getattr(intent, "is_procedural", False) and ch.chunk_type in (
                "algorithm",
                "section",
            ):
                s *= 1.10

            if getattr(intent, "is_comparative", False) and ch.chunk_type in (
                "protocol",
                "comparison",
                "section",
            ):
                s *= 1.05

            scored.append((ch, s))

        if self.reranker is not None:
            reranked = self.reranker.rerank(query, scored)
            return reranked[:top_k]

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def search_with_context(
        self, query: str, top_k: int = 5, *, intent=None, window: int = 1
    ) -> List[ChunkRecord]:
        """
        Search and expand results with neighboring chunks from the same book.

        Returns a list of ChunkRecord (no scores) that includes the top-k results
        plus their neighbors within the specified window.
        """
        if self.chunks is None:
            raise ValueError(
                "Context expansion requires chunks to be stored. "
                "Use from_chunks(..., use_context_expansion=True)"
            )

        results = self.search(query, top_k=top_k, intent=intent)
        by_book = build_book_index(self.chunks)
        expanded = expand_with_neighbors(results, by_book=by_book, window=window)
        return expanded
