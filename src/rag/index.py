"""
Core data loading utilities for RAG over textbook chunks.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = ROOT / "data" / "chunks.jsonl"


@dataclasses.dataclass
class ChunkRecord:
    """Represents a single chunk from the textbook corpus."""

    id: str
    book_id: str
    header_path: str
    chunk_type: str
    key_terms: List[str]
    text: str
    potential_questions: List[str] = dataclasses.field(default_factory=list)
    subject: str = ""


def load_chunks(
    path: Path | None = None,
    subject: Optional[str] = None,
) -> List[ChunkRecord]:
    """Load chunks from JSONL file. If subject is set, only chunks with that subject are loaded."""
    if path is None:
        path = CHUNKS_PATH
    if not path.exists():
        raise FileNotFoundError(f"chunks.jsonl not found at {path}")

    chunks: List[ChunkRecord] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if subject and obj.get("subject") and obj.get("subject") != subject:
                continue
            chunks.append(
                ChunkRecord(
                    id=obj["id"],
                    book_id=obj["book_id"],
                    header_path=obj["header_path"],
                    chunk_type=obj["chunk_type"],
                    key_terms=list(obj.get("key_terms", [])),
                    text=obj["text"],
                    potential_questions=list(obj.get("potential_questions", [])),
                    subject=obj.get("subject", ""),
                )
            )
    return chunks


def iter_chunks(path: Path | None = None) -> Iterable[ChunkRecord]:
    """Iterate over chunks from JSONL file."""
    for ch in load_chunks(path):
        yield ch
