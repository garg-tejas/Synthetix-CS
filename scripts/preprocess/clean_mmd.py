"""
Lightweight preprocessor for textbook-style `.mmd` files.

Goals for v0:
- Remove or normalize obvious OCR / conversion artifacts.
- Collapse extreme repetition within lines and paragraphs.
- Write cleaned `.mmd` files into `books/mmd_clean/` while keeping
  structure (headings, sections) intact.

This runs *before* structural chunking so that the chunker sees
cleaner text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "books" / "mmd"
OUT_DIR = ROOT / "books" / "mmd_clean"


RE_MULTISPACE = re.compile(r"\s+")
RE_SENTENCE = re.compile(r"([^.!?]*[.!?])", re.UNICODE)

# Simple patterns for obvious OCR/conversion artifacts that we are happy to drop.
# These are intentionally conservative and only target clearly non-essential fluff.
FIGURE_LINE_RE = re.compile(r"^Figure\s+\d")
TABLE_LINE_RE = re.compile(r"^Table\s+\d")


def collapse_repeated_phrases(text: str) -> str:
    """
    Simple de-noising at token level:
    - Collapse more than 3 identical words in a row down to 2.
    """
    tokens = RE_MULTISPACE.split(text.strip())
    if not tokens:
        return text

    cleaned = []
    last_token = None
    repeat_count = 0
    for tok in tokens:
        if tok == last_token:
            repeat_count += 1
            # Allow at most two repeats in a row
            if repeat_count <= 1:
                cleaned.append(tok)
        else:
            last_token = tok
            repeat_count = 0
            cleaned.append(tok)

    return " ".join(cleaned)


def dedup_repeated_sentences(text: str) -> str:
    """
    Remove immediately repeated identical sentences within a single line.
    This is a targeted fix for artifacts like:
    \"S1. S1. S2.\" → \"S1. S2.\"
    """
    stripped = text.strip()
    if not stripped:
        return text

    sentences = RE_SENTENCE.findall(stripped)
    if not sentences:
        return text

    deduped = []
    last = None
    for s in sentences:
        s_norm = s.strip()
        if s_norm and s_norm != last:
            deduped.append(s_norm)
            last = s_norm
    # Preserve spacing between sentences
    return " ".join(deduped)


def dominant_token_ratio(text: str) -> float:
    tokens = RE_MULTISPACE.split(text.strip())
    tokens = [t for t in tokens if t]
    if not tokens:
        return 0.0
    freq = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    max_freq = max(freq.values())
    return max_freq / len(tokens)


def is_noisy_line(line: str) -> bool:
    """
    Heuristic: consider a line noisy if:
    - After stripping, it's very short and not a heading.
    (More aggressive paragraph-level filtering is done separately.)
    """
    stripped = line.strip()
    if not stripped:
        return False  # keep blank lines for spacing

    # Keep headings and list markers
    if stripped.startswith("#") or stripped.startswith(("*", "-", "+")):
        return False

    # Very short, non-heading, non-list line → likely noise
    if len(stripped) < 8:
        return True

    return False


def is_noisy_paragraph(lines: List[str]) -> bool:
    """
    Aggressive paragraph-level filter:
    - Drop paragraphs where a single token dominates (e.g. 'Internet' repeated).
    - Drop paragraphs where any token appears an extreme number of times.
    - Only consider reasonably long paragraphs.
    """
    joined = " ".join(l.strip() for l in lines if l.strip())
    if len(joined) < 80:  # keep short paragraphs, handle them line-wise
        return False

    tokens = RE_MULTISPACE.split(joined.strip())
    tokens = [t for t in tokens if t]
    if not tokens:
        return False

    # If one token accounts for a large fraction of all tokens, this is
    # almost certainly garbage repetition ("rich area of the Internet ...").
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    max_freq = max(freq.values())
    ratio = max_freq / len(tokens)

    # Lower the threshold quite a bit; real textbook prose virtually
    # never has a single token taking > 35–40% of all tokens.
    if ratio >= 0.4:
        return True

    # Also treat as noisy if any token appears a *lot* of times and the
    # paragraph is reasonably long. This catches cases where the dominant
    # token ratio is smaller because there are a few different words
    # repeated in a loop.
    if max_freq >= 20 and len(tokens) > 40:
        return True

    return False


def is_figure_or_table_line(line: str) -> bool:
    """
    Drop obvious figure/table captions that survived the PDF → mmd pass.
    These tend not to be useful once diagrams are gone.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if FIGURE_LINE_RE.match(stripped):
        return True
    if TABLE_LINE_RE.match(stripped):
        return True
    return False


def clean_mmd_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8") as fin, dst.open(
        "w", encoding="utf-8", newline="\n"
    ) as fout:
        paragraph: List[str] = []

        def flush_paragraph() -> None:
            nonlocal paragraph
            if not paragraph:
                return
            if is_noisy_paragraph(paragraph):
                paragraph = []
                return
            for raw_line in paragraph:
                line = raw_line.rstrip("\n")
                if is_noisy_line(line) or is_figure_or_table_line(line):
                    continue
                cleaned = collapse_repeated_phrases(line)
                cleaned = dedup_repeated_sentences(cleaned)
                fout.write(cleaned + "\n")
            fout.write("\n")
            paragraph = []

        for raw_line in fin:
            if raw_line.strip() == "":
                # Paragraph boundary
                flush_paragraph()
            paragraph.append(raw_line)

        flush_paragraph()


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(f"Raw .mmd directory not found: {RAW_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mmd_files = sorted(RAW_DIR.glob("*.mmd"))
    if not mmd_files:
        raise SystemExit(f"No .mmd files found in {RAW_DIR}")

    print(f"Cleaning {len(mmd_files)} .mmd files from {RAW_DIR} into {OUT_DIR}")
    for src in mmd_files:
        dst = OUT_DIR / src.name
        clean_mmd_file(src, dst)
    print("Done.")


if __name__ == "__main__":
    main()

