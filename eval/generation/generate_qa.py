"""
Core QA generation logic from chunks using LLM.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Literal, Optional

from src.llm.client import ModelScopeClient
from src.rag.index import ChunkRecord
from .interview_quality import assess_interview_quality
from .llm_review import review_questions_with_llm
from .prompts import build_qa_generation_prompt


QualityMode = Literal["deterministic", "llm_hybrid", "llm_only"]


def parse_llm_response(response: str) -> List[Dict]:
    """
    Parse LLM response into structured question objects.
    
    Handles various response formats (JSON, markdown code blocks, etc.)
    """
    if not response or not response.strip():
        return []

    original_response = response
    
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if json_match:
        response = json_match.group(1)

    # Try to find JSON object with "questions" key
    if '"questions"' not in response:
        json_match = re.search(r"\{.*\"questions\".*?\}", original_response, re.DOTALL)
        if json_match:
            response = json_match.group(0)

    # Try to find any JSON object
    if not response.startswith("{"):
        json_match = re.search(r"\{.*\}", original_response, re.DOTALL)
        if json_match:
            response = json_match.group(0)

    try:
        data = json.loads(response)
        if "questions" in data:
            questions = data["questions"]
            if isinstance(questions, list) and len(questions) > 0:
                return questions
        elif isinstance(data, list):
            return data
        else:
            return []
    except json.JSONDecodeError as e:
        # Debug: log parsing failure
        return []


def generate_questions_from_chunk(
    chunk: ChunkRecord,
    llm_client: ModelScopeClient,
    num_questions: int = 2,
    max_retries: int = 2,
    min_score: int = 70,
    quality_mode: QualityMode = "llm_hybrid",
    llm_allow_rewrite: bool = True,
    *,
    prev_chunk: Optional[ChunkRecord] = None,
    next_chunk: Optional[ChunkRecord] = None,
) -> List[Dict]:
    """
    Generate questions from a single chunk.
    
    Args:
        chunk: The chunk to generate questions from
        llm_client: Initialized ModelScopeClient
        num_questions: Number of questions to generate
        max_retries: Number of retries if parsing fails
        min_score: Minimum quality score (0-100)
        quality_mode: Quality filter strategy:
            - deterministic: structural-only post filter
            - llm_hybrid: LLM review + placement score blend
            - llm_only: LLM review as primary gate
        llm_allow_rewrite: Whether LLM reviewer may rewrite borderline questions
    
    Returns:
        List of question dictionaries with keys: query, answer, question_type, atomic_facts, difficulty
    """
    prompt = build_qa_generation_prompt(
        chunk,
        num_questions=num_questions,
        prev_chunk=prev_chunk,
        next_chunk=next_chunk,
    )

    for attempt in range(max_retries):
        try:
            response = llm_client.generate_single(
                prompt,
                max_tokens=1024,
                temperature=0.7,
                stop=["\n\n\n", "---"],
            )

            if not response or not response.strip():
                if attempt == max_retries - 1:
                    print(f"Warning: Empty response from LLM for chunk {chunk.id}")
                continue

            questions = parse_llm_response(response)

            if questions:
                # Add source metadata to every candidate.
                candidates = []
                for q in questions:
                    q["source_chunk_id"] = chunk.id
                    q["source_header"] = chunk.header_path
                    q["source_subject"] = chunk.subject or _infer_subject(chunk)
                    placement_score = q.get("placement_interview_score")
                    if placement_score is not None:
                        try:
                            q["placement_interview_score"] = int(placement_score)
                        except (TypeError, ValueError):
                            q["placement_interview_score"] = 100
                    else:
                        q["placement_interview_score"] = 100
                    candidates.append(q)

                # Optional LLM second-pass review (keep/rewrite/reject).
                if quality_mode in {"llm_hybrid", "llm_only"}:
                    review = review_questions_with_llm(
                        questions=candidates,
                        chunk=chunk,
                        llm_client=llm_client,
                        min_score=min_score,
                        allow_rewrite=llm_allow_rewrite,
                        max_retries=max_retries,
                    )
                    if review.success:
                        candidates = review.accepted
                    elif quality_mode == "llm_only":
                        # Strict mode: if reviewer fails, fail closed.
                        return []

                kept = []
                for q in candidates:
                    # Structural sanity gate (keyword-agnostic).
                    structural_quality = assess_interview_quality(
                        q,
                        chunk=chunk,
                        min_score=0,
                    )
                    q["structural_quality_score"] = structural_quality.score
                    if structural_quality.reasons:
                        q["structural_quality_reasons"] = structural_quality.reasons

                    llm_score = q.get("llm_interview_score")
                    llm_score_int: Optional[int] = None
                    if llm_score is not None:
                        try:
                            llm_score_int = max(0, min(100, int(llm_score)))
                        except (TypeError, ValueError):
                            llm_score_int = None

                    # Final score composition by mode.
                    if quality_mode == "llm_only":
                        effective_score = llm_score_int if llm_score_int is not None else 0
                        keep = (
                            q.get("llm_review_decision") in {"keep", "rewrite"}
                            and effective_score >= min_score
                            and structural_quality.score >= 55
                        )
                    elif quality_mode == "llm_hybrid" and llm_score_int is not None:
                        effective_score = round(
                            0.35 * q["placement_interview_score"]
                            + 0.65 * llm_score_int
                        )
                        keep = (
                            effective_score >= min_score
                            and structural_quality.score >= 55
                        )
                    else:
                        effective_score = round(
                            0.4 * q["placement_interview_score"] + 0.6 * structural_quality.score
                        )
                        keep = (
                            structural_quality.score >= max(60, min_score - 10)
                            and effective_score >= min_score
                        )

                    q["quality_score"] = effective_score
                    if keep:
                        kept.append(q)
                return kept
            else:
                # Debug: show response snippet if parsing failed
                if attempt == max_retries - 1:
                    response_preview = response[:200] if response else "(empty)"
                    print(f"Warning: Failed to parse questions from chunk {chunk.id}. Response preview: {response_preview}...")

        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Warning: Failed to generate questions for {chunk.id}: {e}")
                return []

    return []


def _infer_subject(chunk: ChunkRecord) -> str:
    """Subject from chunk tag or inferred from metadata."""
    if getattr(chunk, "subject", None) and chunk.subject:
        return chunk.subject
    header_lower = chunk.header_path.lower()
    text_lower = chunk.text[:500].lower()

    # DBMS keywords
    dbms_terms = ["database", "sql", "transaction", "acid", "index", "b+ tree", "normalization", "dbms"]
    if any(term in header_lower or term in text_lower for term in dbms_terms):
        return "dbms"

    # CN keywords
    cn_terms = ["tcp", "udp", "network", "protocol", "routing", "handshake", "http", "computer network"]
    if any(term in header_lower or term in text_lower for term in cn_terms):
        return "cn"

    # OS keywords (default)
    os_terms = ["process", "thread", "scheduling", "memory", "deadlock", "virtual memory", "operating system"]
    if any(term in header_lower or term in text_lower for term in os_terms):
        return "os"

    # Default to os if unclear
    return "os"


def generate_questions_batch(
    chunks: List[ChunkRecord],
    llm_client: ModelScopeClient,
    questions_per_chunk: int = 2,
    min_score: int = 70,
    quality_mode: QualityMode = "llm_hybrid",
    llm_allow_rewrite: bool = True,
) -> List[Dict]:
    """
    Generate questions from multiple chunks in batch.
    
    Args:
        chunks: List of chunks to process
        llm_client: Initialized ModelScopeClient
        questions_per_chunk: Number of questions per chunk
        min_score: Minimum quality score (0-100) to keep questions.
        quality_mode: Quality filtering strategy.
        llm_allow_rewrite: Whether LLM reviewer can rewrite borderline questions.
    
    Returns:
        Flat list of generated questions (only those with placement_interview_score >= min_score).
    """
    all_questions: List[Dict] = []

    for idx, chunk in enumerate(chunks):
        prev_chunk = chunks[idx - 1] if idx > 0 else None
        next_chunk = chunks[idx + 1] if idx + 1 < len(chunks) else None

        print(f"    Processing chunk {idx + 1}/{len(chunks)}: {chunk.id[:20]}...")
        questions = generate_questions_from_chunk(
            chunk,
            llm_client,
            num_questions=questions_per_chunk,
            min_score=min_score,
            quality_mode=quality_mode,
            llm_allow_rewrite=llm_allow_rewrite,
            prev_chunk=prev_chunk,
            next_chunk=next_chunk,
        )
        if questions:
            print(f"      Generated {len(questions)} questions")
        else:
            print(f"      No questions generated")
        all_questions.extend(questions)

    return all_questions
