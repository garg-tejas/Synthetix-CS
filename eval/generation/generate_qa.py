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
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if json_match:
        response = json_match.group(1)

    # Try to find JSON object
    json_match = re.search(r"\{.*\"questions\".*?\}", response, re.DOTALL)
    if json_match:
        response = json_match.group(0)

    try:
        data = json.loads(response)
        if "questions" in data:
            return data["questions"]
        elif isinstance(data, list):
            return data
        else:
            return []
    except json.JSONDecodeError:
        # Fallback: try to extract individual questions
        questions = []
        # Look for question-answer pairs in the text
        # This is a simple fallback - may not work well
        return questions


def generate_questions_from_chunk(
    chunk: ChunkRecord,
    llm_client: ModelScopeClient,
    num_questions: int = 2,
    max_retries: int = 2,
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

            questions = parse_llm_response(response)

            if questions:
                # Add metadata
                for q in questions:
                    q["source_chunk_id"] = chunk.id
                    q["source_header"] = chunk.header_path
                    q["source_subject"] = _infer_subject(chunk)

                return questions

        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Warning: Failed to generate questions for {chunk.id}: {e}")
                return []

    return []


def _infer_subject(chunk: ChunkRecord) -> str:
    """Infer subject (os/dbms/cn) from chunk metadata."""
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
) -> List[Dict]:
    """
    Generate questions from multiple chunks in batch.
    
    Args:
        chunks: List of chunks to process
        llm_client: Initialized ModelScopeClient
        questions_per_chunk: Number of questions per chunk
    
    Returns:
        Flat list of all generated questions
    """
    all_questions: List[Dict] = []

    for idx, chunk in enumerate(chunks):
        prev_chunk = chunks[idx - 1] if idx > 0 else None
        next_chunk = chunks[idx + 1] if idx + 1 < len(chunks) else None

        questions = generate_questions_from_chunk(
            chunk,
            llm_client,
            num_questions=questions_per_chunk,
            prev_chunk=prev_chunk,
            next_chunk=next_chunk,
        )
        all_questions.extend(questions)

    return all_questions
