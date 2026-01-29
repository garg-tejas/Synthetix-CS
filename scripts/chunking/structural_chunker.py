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


# Chunk type strings; excluded set used for QA filtering
CHUNK_TYPE_REFERENCES = "references"
CHUNK_TYPE_BIBLIOGRAPHY = "bibliography"
CHUNK_TYPE_CITATIONS = "citations"
CHUNK_TYPE_APPENDIX = "appendix"
CHUNK_TYPE_ALGORITHM = "algorithm"
CHUNK_TYPE_EXAMPLE = "example"
CHUNK_TYPE_DEFINITION = "definition"
CHUNK_TYPE_THEOREM = "theorem"
CHUNK_TYPE_PROTOCOL = "protocol"
CHUNK_TYPE_EXERCISE = "exercise"
CHUNK_TYPE_SECTION = "section"

QA_EXCLUDED_CHUNK_TYPES = frozenset({
    CHUNK_TYPE_EXERCISE, CHUNK_TYPE_REFERENCES, CHUNK_TYPE_BIBLIOGRAPHY,
    CHUNK_TYPE_CITATIONS, CHUNK_TYPE_APPENDIX,
})
QA_EXCLUDED_HEADER_MARKERS = frozenset({
    "appendix", "exercises", "review questions", "selected bibliography",
    "references", "bibliography", "citations", "acknowledgment", "index",
})

# "What is X?" style headers (word boundary to avoid "what is not", etc.)
_WHAT_IS_RE = re.compile(r"\bwhat\s+is\b", re.IGNORECASE)


def _detect_chunk_type(header_text: str, body: str) -> str:
    """
    Heuristic chunk type from header and body.
    Order: back-matter and excluded types first, then content types; first match wins.
    """
    h = header_text.lower()
    b = body.lower()[:800]

    if "references" in h:
        return CHUNK_TYPE_REFERENCES
    if "bibliography" in h:
        return CHUNK_TYPE_BIBLIOGRAPHY
    if "citations" in h:
        return CHUNK_TYPE_CITATIONS
    if "appendix" in h:
        return CHUNK_TYPE_APPENDIX
    if "exercise" in h or "problem" in h:
        return CHUNK_TYPE_EXERCISE

    if any(k in h for k in ("algorithm", "procedure", "pseudo")):
        return CHUNK_TYPE_ALGORITHM
    if any(k in h for k in ("example", "case study", "case-study")):
        return CHUNK_TYPE_EXAMPLE
    if "definition" in h or _WHAT_IS_RE.search(header_text):
        return CHUNK_TYPE_DEFINITION
    if any(k in h for k in ("theorem", "lemma", "proof")):
        return CHUNK_TYPE_THEOREM
    if "protocol" in h or "handshake" in b:
        return CHUNK_TYPE_PROTOCOL

    return CHUNK_TYPE_SECTION


def is_qa_excluded(chunk: Chunk) -> bool:
    """True if chunk should be excluded from QA generation (references, exercises, appendix, etc.)."""
    if chunk.chunk_type in QA_EXCLUDED_CHUNK_TYPES:
        return True
    header_lower = chunk.header_path.lower()
    return any(marker in header_lower for marker in QA_EXCLUDED_HEADER_MARKERS)


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
    base = Path(__file__).resolve().parents[1]
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


