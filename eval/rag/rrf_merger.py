from __future__ import annotations

"""
Reciprocal Rank Fusion (RRF) merger for combining results from multiple retrievers.

Each retriever returns a list of (chunk_id, score) pairs (score is ignored here;
we only care about rank positions). RRF then combines them into a single ranking.
"""

from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple


def rrf_merge(
    result_lists: Sequence[Sequence[Tuple[str, float]]],
    k: int = 10,
    k_rrf: int = 60,
) -> List[Tuple[str, float]]:
    """
    result_lists: list of ranked lists from different retrievers.
                  each inner list is [(chunk_id, score), ...] sorted by score desc.
    k: number of final results to return.
    k_rrf: constant in 1 / (k_rrf + rank), typically 60.
    """
    scores: Dict[str, float] = defaultdict(float)

    for results in result_lists:
        for rank, (chunk_id, _score) in enumerate(results):
            scores[chunk_id] += 1.0 / (k_rrf + rank + 1)

    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return merged[:k]


if __name__ == "__main__":
    # Tiny sanity check
    r1 = [("a", 1.0), ("b", 0.9), ("c", 0.8)]
    r2 = [("b", 1.0), ("c", 0.9), ("d", 0.8)]
    print(rrf_merge([r1, r2], k=3))

