"""
Minimal key-term extractor for chunks.

This is intentionally simple (no external NLP deps yet):
- Lowercase
- Split on non-alphanumeric boundaries
- Remove short tokens and a small stopword list
- Return top-N most frequent tokens as `key_terms`
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

# Very small stopword list; can be extended later.
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "in",
    "on",
    "for",
    "to",
    "is",
    "are",
    "be",
    "as",
    "that",
    "this",
    "these",
    "those",
    "with",
    "by",
    "at",
    "from",
    "it",
    "its",
    "we",
    "they",
    "you",
}


def iter_tokens(text: str) -> Iterable[str]:
    for match in TOKEN_RE.finditer(text.lower()):
        tok = match.group(0)
        if len(tok) <= 2:
            continue
        if tok in STOPWORDS:
            continue
        yield tok


def extract_key_terms(text: str, max_terms: int = 8) -> List[str]:
    counts = Counter(iter_tokens(text))
    if not counts:
        return []
    # Most common tokens; preserve deterministic ordering
    return [tok for tok, _ in counts.most_common(max_terms)]


def _extract_main_concept(header_path: str) -> str:
    """
    Heuristic extraction of the main concept name from a header path.
    """
    # Take the deepest header segment.
    segment = header_path.split(">")[-1].strip()
    # Drop leading numbering like "1. 1" or "2.3.4".
    segment = re.sub(r"^[0-9.\s]+", "", segment)
    # Remove common prefixes like "What Is", "Definition of", etc.
    for prefix in (
        "what is ",
        "what is the ",
        "definition of ",
        "introduction to ",
        "overview of ",
    ):
        if segment.lower().startswith(prefix):
            segment = segment[len(prefix) :]
            break
    return segment.strip()


def extract_potential_questions(
    header_path: str,
    chunk_type: str,
    text: str,
    max_questions: int = 3,
) -> List[str]:
    """
    Generate a small set of potential questions that this chunk can answer.

    This is intentionally lightweight and heuristic; it is used as metadata to
    guide later QA generation and chunk selection.
    """
    concept = _extract_main_concept(header_path)
    questions: List[str] = []

    if concept:
        if chunk_type == "definition":
            questions.append(f"What is {concept}?")
            questions.append(f"Define {concept}.")
        elif chunk_type == "algorithm":
            questions.append(f"How does {concept} work?")
            questions.append(f"Explain the steps of {concept}.")
        elif chunk_type == "protocol":
            questions.append(f"What is the {concept} protocol?")
            questions.append(f"Explain how the {concept} protocol works.")
        else:
            # Generic section: still generate a focused explanation-style question.
            questions.append(f"Explain {concept}.")

    # Fallback: if we failed to derive a concept, try using key terms.
    if not questions:
        terms = extract_key_terms(text, max_terms=3)
        if terms:
            main = " ".join(terms[:2])
            questions.append(f"Explain {main}.")

    # Deduplicate while preserving order.
    seen = set()
    deduped: List[str] = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            deduped.append(q)

    return deduped[:max_questions]


if __name__ == "__main__":
    sample = "The LRU (Least Recently Used) page replacement algorithm uses temporal locality."
    print(extract_key_terms(sample))
    print(
        extract_potential_questions(
            "Chapter 1 > Paging > LRU Page Replacement Algorithm",
            "algorithm",
            sample,
        )
    )

