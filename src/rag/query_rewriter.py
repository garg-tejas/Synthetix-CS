"""
Query rewriting utilities for hybrid retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class QueryRewriter:
    """Rule-based query rewriter for BM25 and semantic retrieval."""

    keyword_expansions: Dict[str, str] | None = None

    def __post_init__(self) -> None:
        """Initialize default keyword expansions if not provided."""
        if self.keyword_expansions is None:
            self.keyword_expansions = {
                # OS
                "deadlock": "circular wait hold-and-wait mutual exclusion resource allocation graph",
                "critical section": "race condition mutual exclusion synchronization",
                "paging": "page table page fault virtual memory",
                "segmentation": "segment table segmentation fault memory management",
                "scheduling": "cpu scheduling preemptive non-preemptive round-robin priority",
                # CN
                "tcp handshake": "three-way handshake 3-way handshake connection establishment syn ack fin",
                "three way handshake": "three-way handshake 3-way handshake connection establishment",
                "udp": "user datagram protocol connectionless",
                "osi model": "osi reference model seven layers 7 layers",
                "routing": "routing algorithms distance vector link state shortest path",
                "congestion control": "tcp congestion window slow start congestion avoidance",
                # DBMS
                "acid": "atomicity consistency isolation durability transaction properties",
                "transaction": "commit rollback concurrency serializability schedule",
                "normalization": "functional dependency 1nf 2nf 3nf bcnf",
                "indexing": "b tree b+ tree index selectivity clustered nonclustered",
            }

    def rewrite(self, query: str) -> Dict[str, str]:
        """
        Return different queries for different retrievers.

        Returns:
            Dictionary with keys:
            - original: original user query
            - bm25_query: expanded for keyword-based retrieval
            - semantic_query: cleaned for semantic embedding search
        """
        base = query.strip()
        bm25_query = self._expand_for_keyword(base)
        semantic_query = self._clean_for_semantic(base)
        return {
            "original": base,
            "bm25_query": bm25_query,
            "semantic_query": semantic_query,
        }

    def _expand_for_keyword(self, query: str) -> str:
        """Expand query with keyword variants for BM25."""
        q_lower = query.lower()
        additions: list[str] = []

        for phrase, extra in (self.keyword_expansions or {}).items():
            if phrase in q_lower:
                additions.append(extra)

        if not additions:
            return query

        return query + " " + " ".join(additions)

    def _clean_for_semantic(self, query: str) -> str:
        """Clean query for semantic search by removing politeness/fluff."""
        q = query.strip()
        lower = q.lower()
        for prefix in (
            "please explain ",
            "explain ",
            "can you explain ",
            "what do you mean by ",
            "what is meant by ",
        ):
            if lower.startswith(prefix):
                q = q[len(prefix) :]
                break

        q = q.rstrip(" ?")
        return q.strip()
