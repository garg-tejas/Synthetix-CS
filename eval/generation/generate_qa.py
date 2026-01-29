"""
Core QA generation logic from chunks using LLM.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from src.llm.client import ModelScopeClient
from src.rag.index import ChunkRecord
from .prompts import build_qa_generation_prompt, build_quality_scoring_prompt


def score_question_quality(
    question: Dict,
    llm_client: ModelScopeClient,
    min_score: int = 70,
) -> tuple[int, bool]:
    """
    Score a question's suitability for placement interviews using LLM.
    
    Args:
        question: Question dictionary to score
        llm_client: Initialized ModelScopeClient
        min_score: Minimum score threshold (default: 70)
    
    Returns:
        (score, is_acceptable) tuple
    """
    prompt = build_quality_scoring_prompt(question)
    
    try:
        response = llm_client.generate_single(
            prompt,
            max_tokens=50,
            temperature=0.3,
        )
        
        if not response or not response.strip():
            return 0, False
        
        # Parse JSON response
        response_clean = response.strip()
        json_match = re.search(r'\{[^}]*"score"[^}]*\}', response_clean)
        if json_match:
            response_clean = json_match.group(0)
        
        try:
            data = json.loads(response_clean)
            score = int(data.get("score", 0))
            return score, score >= min_score
        except (json.JSONDecodeError, ValueError, KeyError):
            # If parsing fails, check if score is mentioned in text
            score_match = re.search(r'score["\s:]*(\d+)', response_clean, re.IGNORECASE)
            if score_match:
                score = int(score_match.group(1))
                return score, score >= min_score
            return 0, False
            
    except Exception as e:
        # On error, reject the question
        return 0, False


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
    *,
    prev_chunk: Optional[ChunkRecord] = None,
    next_chunk: Optional[ChunkRecord] = None,
    score_questions: bool = False,
    min_quality_score: int = 70,
) -> List[Dict]:
    """
    Generate questions from a single chunk.
    
    Args:
        chunk: The chunk to generate questions from
        llm_client: Initialized ModelScopeClient
        num_questions: Number of questions to generate
        max_retries: Number of retries if parsing fails
        score_questions: Whether to score questions and filter by quality (default: False)
        min_quality_score: Minimum quality score threshold if scoring is enabled
    
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
                # Add metadata
                for q in questions:
                    q["source_chunk_id"] = chunk.id
                    q["source_header"] = chunk.header_path
                    q["source_subject"] = _infer_subject(chunk)
                
                # Score and filter if requested
                if score_questions:
                    scored_questions = []
                    for q in questions:
                        score, is_acceptable = score_question_quality(q, llm_client, min_score=min_quality_score)
                        q["quality_score"] = score
                        
                        if is_acceptable:
                            scored_questions.append(q)
                        else:
                            print(f"      Filtered question (score {score}): {q.get('query', '')[:50]}...")
                    return scored_questions
                else:
                    return questions
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
    score_questions: bool = False,
    min_quality_score: int = 70,
) -> List[Dict]:
    """
    Generate questions from multiple chunks in batch.
    
    Args:
        chunks: List of chunks to process
        llm_client: Initialized ModelScopeClient
        questions_per_chunk: Number of questions per chunk
        score_questions: Whether to score questions and filter by quality (default: False)
        min_quality_score: Minimum quality score threshold if scoring is enabled
    
    Returns:
        Flat list of all generated questions
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
            prev_chunk=prev_chunk,
            next_chunk=next_chunk,
            score_questions=score_questions,
            min_quality_score=min_quality_score,
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
    Score a batch of existing questions and optionally filter by quality.
    
    Args:
        questions: List of question dictionaries to score
        llm_client: Initialized ModelScopeClient
        min_quality_score: Minimum quality score threshold
        filter_low_scores: If True, return only questions above threshold; if False, return all with scores
    
    Returns:
        (accepted_questions, rejected_questions) tuple if filter_low_scores=True
        (all_questions_with_scores, []) tuple if filter_low_scores=False
    """
    accepted = []
    rejected = []
    
    for idx, q in enumerate(questions):
        if (idx + 1) % 10 == 0:
            print(f"  Scoring question {idx + 1}/{len(questions)}...")
        
        score, is_acceptable = score_question_quality(q, llm_client, min_score=min_quality_score)
        q["quality_score"] = score
        
        if filter_low_scores:
            if is_acceptable:
                accepted.append(q)
            else:
                rejected.append(q)
        else:
            accepted.append(q)
    
    if filter_low_scores:
        return accepted, rejected
    else:
        return accepted, []
