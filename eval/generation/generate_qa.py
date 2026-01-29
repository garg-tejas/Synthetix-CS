"""
Core QA generation logic from chunks using LLM.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from src.llm.client import ModelScopeClient
from src.rag.index import ChunkRecord
from .prompts import build_qa_generation_prompt


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
                # Add metadata and filter by placement_interview_score when present
                kept = []
                for q in questions:
                    q["source_chunk_id"] = chunk.id
                    q["source_header"] = chunk.header_path
                    q["source_subject"] = chunk.subject or _infer_subject(chunk)
                    score = q.get("placement_interview_score")
                    if score is not None:
                        try:
                            q["placement_interview_score"] = int(score)
                        except (TypeError, ValueError):
                            q["placement_interview_score"] = 100
                    else:
                        q["placement_interview_score"] = 100
                    if q["placement_interview_score"] >= min_score:
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
) -> List[Dict]:
    """
    Generate questions from multiple chunks in batch.
    
    Args:
        chunks: List of chunks to process
        llm_client: Initialized ModelScopeClient
        questions_per_chunk: Number of questions per chunk
        min_score: Minimum placement_interview_score (0-100) to keep; questions below are dropped.
    
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
            prev_chunk=prev_chunk,
            next_chunk=next_chunk,
        )
        if questions:
            print(f"      Generated {len(questions)} questions")
        else:
            print(f"      No questions generated")
        all_questions.extend(questions)

    return all_questions


def score_questions_batch(
    questions: List[Dict],
    llm_client: ModelScopeClient,
    min_quality_score: int = 70,
    filter_low_scores: bool = True,
) -> tuple[List[Dict], List[Dict]]:
    """
    Filter questions by placement_interview_score (when present).
    Does not call the LLM; uses existing placement_interview_score on each question.
    Returns (accepted, rejected).
    """
    accepted: List[Dict] = []
    rejected: List[Dict] = []
    for q in questions:
        score = q.get("placement_interview_score")
        if score is None:
            accepted.append(q)
            continue
        try:
            s = int(score)
        except (TypeError, ValueError):
            accepted.append(q)
            continue
        q["quality_score"] = s
        if filter_low_scores and s < min_quality_score:
            rejected.append(q)
        else:
            accepted.append(q)
    return accepted, rejected
