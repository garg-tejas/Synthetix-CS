"""
Helpers for expanding retrieved chunks with neighboring chunks from the same book.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

from .index import ChunkRecord


def _chunk_order_key(chunk: ChunkRecord) -> Tuple[str, int]:
    """Sort key for chunks within a book."""
    cid = chunk.id
    try:
        suffix = cid.split("chunk_", 1)[1]
        num = int(suffix)
    except Exception:
        num = 0
    return chunk.book_id, num


def build_book_index(chunks: Sequence[ChunkRecord]) -> Dict[str, List[ChunkRecord]]:
    """Group chunks by book and sort them in their natural within-book order."""
    by_book: Dict[str, List[ChunkRecord]] = {}
    for ch in chunks:
        by_book.setdefault(ch.book_id, []).append(ch)
    for bid, lst in by_book.items():
        lst.sort(key=_chunk_order_key)
    return by_book


def expand_with_neighbors(
    results: Iterable[Tuple[ChunkRecord, float]],
    *,
    by_book: Dict[str, List[ChunkRecord]],
    window: int = 1,
) -> List[ChunkRecord]:
    """
    Expand results with neighboring chunks from the same book.

    Args:
        results: Ranked list of (chunk, score) pairs
        by_book: Per-book index of chunks
        window: Number of neighbors to include on each side

    Returns:
        Deduplicated list of chunks including hits and their neighbors.
    """
    expanded: Dict[str, ChunkRecord] = {}

    for hit, _score in results:
        book_chunks = by_book.get(hit.book_id)
        if not book_chunks:
            expanded.setdefault(hit.id, hit)
            continue

        idx = None
        for i, ch in enumerate(book_chunks):
            if ch.id == hit.id:
                idx = i
                break
        if idx is None:
            expanded.setdefault(hit.id, hit)
            continue

        start = max(0, idx - window)
        end = min(len(book_chunks) - 1, idx + window)
        for j in range(start, end + 1):
            ch = book_chunks[j]
            expanded.setdefault(ch.id, ch)

    return list(expanded.values())
