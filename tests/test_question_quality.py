from __future__ import annotations

from eval.generation.chunk_selector import score_chunk_qa_potential
from eval.generation.interview_quality import assess_interview_quality
from eval.generation.validate_qa import validate_question
from src.rag.index import ChunkRecord


def _chunk(
    *,
    chunk_type: str,
    header_path: str,
    text: str,
    key_terms: list[str],
) -> ChunkRecord:
    return ChunkRecord(
        id="chunk_x",
        book_id="book",
        header_path=header_path,
        chunk_type=chunk_type,
        key_terms=key_terms,
        text=text,
        subject="cn",
    )


def test_assess_interview_quality_is_keyword_agnostic() -> None:
    q = {
        "query": "What is the Internet?",
        "answer": (
            "The Internet is a global network of interconnected systems using "
            "packet-switched communication and layered protocols."
        ),
        "question_type": "definition",
        "difficulty": "easy",
        "atomic_facts": ["global network", "interconnected systems", "layered protocols"],
        "source_header": "Chapter 1 > Introduction",
    }

    quality = assess_interview_quality(q, min_score=70)
    assert quality.keep is True
    assert quality.score >= 70


def test_assess_interview_quality_accepts_mechanism_question() -> None:
    q = {
        "query": (
            "Why does TCP require a three-way handshake instead of a two-way "
            "handshake, and what reliability issue does it prevent?"
        ),
        "answer": (
            "A two-way handshake can accept stale duplicate segments and leave "
            "one side with incorrect sequence state. The third exchange confirms "
            "both peers are synchronized and prevents half-open confusion."
        ),
        "question_type": "procedural",
        "difficulty": "medium",
        "atomic_facts": [
            "stale duplicate segments can appear",
            "sequence-number synchronization is required",
            "third handshake message confirms both peers",
        ],
        "source_header": "Transport Layer > TCP",
        "key_terms": ["tcp", "handshake", "sequence", "reliability"],
    }

    quality = assess_interview_quality(q, min_score=70)
    assert quality.keep is True
    assert quality.score >= 70


def test_validate_question_requires_llm_score_by_default() -> None:
    q = {
        "query": "What is the Internet?",
        "answer": "The Internet is a network of networks used by many applications.",
        "question_type": "definition",
        "difficulty": "easy",
        "atomic_facts": ["network of networks", "used by applications"],
    }

    is_valid, errors = validate_question(q, min_interview_score=70)
    assert is_valid is False
    assert any("Missing LLM score fields" in e for e in errors)


def test_chunk_selector_prefers_deep_technical_chunk() -> None:
    intro_definition = _chunk(
        chunk_type="definition",
        header_path="Chapter 1 > Introduction > Business Applications",
        text="In this chapter we ask what is the Internet and discuss broad ideas.",
        key_terms=["internet", "network"],
    )
    protocol_chunk = _chunk(
        chunk_type="protocol",
        header_path="Transport Layer > TCP Handshake",
        text=(
            "The handshake handles reliability, sequence synchronization, and "
            "failure recovery under packet loss and delay."
        ),
        key_terms=["tcp", "handshake", "reliability", "failure"],
    )

    assert score_chunk_qa_potential(protocol_chunk) > score_chunk_qa_potential(intro_definition)
