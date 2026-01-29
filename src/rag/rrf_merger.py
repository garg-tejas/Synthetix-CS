"""
Reciprocal Rank Fusion (RRF) for combining results from multiple retrievers.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple


def rrf_merge(
    result_lists: Sequence[Sequence[Tuple[str, float]]],
    k: int = 10,
    k_rrf: int = 60,
) -> List[Tuple[str, float]]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    Args:
        result_lists: List of ranked lists from different retrievers.
                     Each inner list is [(chunk_id, score), ...] sorted by score desc.
        k: Number of final results to return.
        k_rrf: Constant in 1 / (k_rrf + rank), typically 60.

    Returns:
        Merged list of (chunk_id, score) tuples sorted by RRF score.
    """
    scores: Dict[str, float] = defaultdict(float)

    for results in result_lists:
        for rank, (chunk_id, _score) in enumerate(results):
            scores[chunk_id] += 1.0 / (k_rrf + rank + 1)

    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return merged[:k]
