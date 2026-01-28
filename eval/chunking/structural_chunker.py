"""
Structural chunker for textbook-style .mmd files.

Goals for v0:
- Work on the existing `.mmd` files under `books/mmd/`.
- Produce structurally coherent chunks instead of fixed-size windows.
- Attach basic metadata (header_path, chunk_type) for later retrieval.

This is intentionally dependency-light (stdlib only) so it can be iterated on
quickly before we introduce heavier NLP tooling.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Iterable, List, Optional


CHUNK_SEPARATOR_RE = re.compile(r"^(#{2,4})\s+(.*)")


@dataclasses.dataclass
class Chunk:
    id: str
    book_id: str
    header_path: str
    chunk_type: str
    text: str


def _detect_chunk_type(header_text: str, body: str) -> str:
    """Very simple heuristic for now; can be upgraded later."""
    header_lower = header_text.lower()
    body_lower = body.lower()

    if any(k in header_lower for k in ("algorithm", "procedure", "pseudo")):
        return "algorithm"
    if any(k in header_lower for k in ("example", "case study", "case-study")):
        return "example"
    if "definition" in header_lower or "what is" in header_lower:
        return "definition"
    if "theorem" in header_lower or "lemma" in header_lower or "proof" in header_lower:
        return "theorem"
    if "protocol" in header_lower or "handshake" in body_lower:
        return "protocol"
    if "exercise" in header_lower or "problem" in header_lower:
        return "exercise"
    return "section"


def _iter_lines(path: Path) -> Iterable[str]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n")


def chunk_mmd_file(path: Path, *, book_id: Optional[str] = None) -> List[Chunk]:
    """
    Naive structural chunker:
    - Uses markdown headings (##, ###, ####) as boundaries.
    - Builds a header_path from nested headings.
    """
    if book_id is None:
        book_id = path.stem

    header_stack: List[str] = []
    chunks: List[Chunk] = []

    current_header: Optional[str] = None
    current_body: List[str] = []
    current_level: Optional[int] = None
    chunk_index = 0

    def flush_chunk() -> None:
        nonlocal chunk_index, current_header, current_body, current_level
        if current_header is None or not current_body:
            return
        header_path = " > ".join(header_stack)
        body_text = "\n".join(current_body).strip()
        if not body_text:
            return
        chunk_type = _detect_chunk_type(current_header, body_text)
        chunk_id = f"{book_id}::chunk_{chunk_index:05d}"
        chunk_index += 1
        chunks.append(
            Chunk(
                id=chunk_id,
                book_id=book_id,
                header_path=header_path,
                chunk_type=chunk_type,
                text=body_text,
            )
        )
        current_body = []

    for line in _iter_lines(path):
        m = CHUNK_SEPARATOR_RE.match(line)
        if m:
            # Heading line
            level = len(m.group(1))  # number of '#' characters
            header_text = m.group(2).strip()

            # Flush previous chunk before starting new one
            flush_chunk()

            # Update header stack based on level
            # level 2 → index 0, level 3 → index 1, etc.
            stack_index = level - 2
            if stack_index < 0:
                # Ignore top-level (#) for now
                stack_index = 0
            if stack_index < len(header_stack):
                header_stack = header_stack[: stack_index + 1]
                header_stack[stack_index] = header_text
            else:
                # Extend stack
                while len(header_stack) < stack_index:
                    header_stack.append("")
                header_stack.append(header_text)

            current_header = header_text
            current_level = level
            current_body = []
        else:
            # Normal text line
            if current_header is None:
                # Pre-chapter text; skip for now
                continue
            current_body.append(line)

    # Flush last chunk
    flush_chunk()
    return chunks


def chunk_books_in_dir(mmd_dir: Path) -> List[Chunk]:
    """
    Convenience helper: chunk all `.mmd` files in a directory.
    """
    all_chunks: List[Chunk] = []
    for path in sorted(mmd_dir.glob("*.mmd")):
        all_chunks.extend(chunk_mmd_file(path))
    return all_chunks


if __name__ == "__main__":
    # Simple manual smoke test.
    base = Path(__file__).resolve().parents[2]
    cleaned_dir = base / "books" / "mmd_clean"
    raw_dir = base / "books" / "mmd"

    if cleaned_dir.exists():
        mmd_dir = cleaned_dir
    else:
        mmd_dir = raw_dir

    chunks = chunk_books_in_dir(mmd_dir)
    print(f"Chunked {len(chunks)} chunks from {mmd_dir}")
    # Print a couple of sample chunks
    for c in chunks[:5]:
        print("\n====", c.id, "====")
        print("Header path:", c.header_path)
        print("Type:", c.chunk_type)
        print(c.text[:400], "...")


