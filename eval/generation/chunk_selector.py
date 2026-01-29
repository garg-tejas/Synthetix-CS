from __future__ import annotations

"""
Heuristics for selecting and ordering chunks for QA generation.

We:
- Score chunks for QA potential.
- Apply simple topic-based diversity so we don't over-focus on a single section.
"""

from collections import defaultdict
from typing import Dict, List

from src.rag.index import ChunkRecord


def _topic_key(chunk: ChunkRecord) -> str:
    """
    Derive a coarse topic key for diversity sampling.

    We group by (book_id, top-level header) so we sample across chapters/books.
    """
    top_header = chunk.header_path.split(">")[0].strip().lower()
    return f"{chunk.book_id}::{top_header}"


def score_chunk_qa_potential(chunk: ChunkRecord) -> float:
    """
    Score how promising this chunk is for QA generation (0-1+).
    """
    score = 0.0

    # 1) Base score by chunk type.
    if chunk.chunk_type == "definition":
        score += 1.0
    elif chunk.chunk_type == "algorithm":
        score += 0.9
    elif chunk.chunk_type in ("section", "protocol"):
        score += 0.8
    elif chunk.chunk_type in ("theorem", "example"):
        score += 0.6
    else:
        score += 0.5

    # 2) Length heuristics: avoid extremely short or extremely long chunks.
    length = len(chunk.text)
    if length < 150:
        score -= 0.3
    elif length < 400:
        score -= 0.1
    elif 400 <= length <= 1800:
        score += 0.2
    elif length > 2600:
        score -= 0.1

    # 3) Key terms density.
    num_terms = len(chunk.key_terms or [])
    if num_terms >= 4:
        score += 0.1
    if num_terms >= 8:
        score += 0.05

    # 4) Heuristic "potential questions" metadata from preprocessing.
    potential_qs = getattr(chunk, "potential_questions", []) or []
    if potential_qs:
        score += 0.3
        if len(potential_qs) > 1:
            score += 0.05

    # Clamp to a sane lower bound.
    if score < 0.0:
        score = 0.0
    return score


def select_chunks_for_generation(
    chunks: List[ChunkRecord],
    target_count: int,
) -> List[ChunkRecord]:
    """
    Select up to `target_count` chunks, balancing quality and topic diversity.

    Strategy:
    - Score all chunks for QA potential.
    - Group by (book_id, top-level header).
    - Within each group, sort by score descending.
    - Round-robin across groups until we hit `target_count`.
    """
    if not chunks or target_count <= 0:
        return []

    # Score and group by topic.
    groups: Dict[str, List[tuple[ChunkRecord, float]]] = defaultdict(list)
    for ch in chunks:
        s = score_chunk_qa_potential(ch)
        groups[_topic_key(ch)].append((ch, s))

    # Sort each group by score descending.
    for key in groups:
        groups[key].sort(key=lambda cs: cs[1], reverse=True)

    # Order topics by their best chunk score so higher-yield topics are sampled first.
    topic_order = sorted(
        groups.keys(),
        key=lambda k: groups[k][0][1] if groups[k] else 0.0,
        reverse=True,
    )

    selected: List[ChunkRecord] = []
    # Round-robin over topic groups.
    while len(selected) < target_count:
        made_progress = False
        for key in topic_order:
            if len(selected) >= target_count:
                break
            group = groups[key]
            if not group:
                continue
            ch, _ = group.pop(0)
            selected.append(ch)
            made_progress = True
        if not made_progress:
            break

    return selected

