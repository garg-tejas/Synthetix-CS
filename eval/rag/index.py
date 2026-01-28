from __future__ import annotations

"""
Core data loading utilities for RAG over textbook chunks.

This module:
- Loads `eval/dataset/chunks.jsonl`
- Provides a simple `ChunkRecord` dataclass
"""

import dataclasses
import json
from pathlib import Path
from typing import Iterable, List


ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = ROOT / "eval" / "dataset" / "chunks.jsonl"


@dataclasses.dataclass
class ChunkRecord:
    id: str
    book_id: str
    header_path: str
    chunk_type: str
    key_terms: List[str]
    text: str


def load_chunks(path: Path | None = None) -> List[ChunkRecord]:
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
            chunks.append(
                ChunkRecord(
                    id=obj["id"],
                    book_id=obj["book_id"],
                    header_path=obj["header_path"],
                    chunk_type=obj["chunk_type"],
                    key_terms=list(obj.get("key_terms", [])),
                    text=obj["text"],
                )
            )
    return chunks


def iter_chunks(path: Path | None = None) -> Iterable[ChunkRecord]:
    for ch in load_chunks(path):
        yield ch


if __name__ == "__main__":
    cs = load_chunks()
    print(f"Loaded {len(cs)} chunks from {CHUNKS_PATH}")
    for c in cs[:3]:
        print("ID:", c.id)
        print("Header:", c.header_path)
        print("Type:", c.chunk_type)
        print()

