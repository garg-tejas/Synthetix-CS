"""
Validation and filtering for generated QA pairs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.rag import HybridSearcher, load_chunks


def validate_question(question: Dict, chunk_id: Optional[str] = None) -> tuple[bool, List[str]]:
    """
    Validate a single question for quality.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    required_fields = ["query", "answer", "question_type", "difficulty"]

    # Check required fields
    for field in required_fields:
        if field not in question or not question[field]:
            errors.append(f"Missing or empty '{field}'")

    # Validate question_type
    valid_types = {"definition", "procedural", "comparative", "factual"}
    if question.get("question_type") not in valid_types:
        errors.append(f"Invalid question_type: {question.get('question_type')}")

    # Validate difficulty
    valid_difficulties = {"easy", "medium", "hard"}
    if question.get("difficulty") not in valid_difficulties:
        errors.append(f"Invalid difficulty: {question.get('difficulty')}")

    # Check answer length
    answer = question.get("answer", "")
    if len(answer) < 50:
        errors.append(f"Answer too short ({len(answer)} chars, min 50)")
    if len(answer) > 1000:
        errors.append(f"Answer too long ({len(answer)} chars, max 1000)")

    # Check query quality
    query = question.get("query", "")
    if len(query) < 10:
        errors.append(f"Query too short ({len(query)} chars)")
    if query.lower().startswith("generate") or "generate" in query.lower():
        errors.append("Query appears to be a generation instruction, not a real question")

    # Check atomic_facts
    atomic_facts = question.get("atomic_facts", [])
    if not atomic_facts or len(atomic_facts) < 2:
        errors.append("Need at least 2 atomic_facts")

    return len(errors) == 0, errors


def deduplicate_questions(questions: List[Dict], similarity_threshold: float = 0.8) -> List[Dict]:
    """
    Remove duplicate or very similar questions.
    
    Uses simple string similarity (Jaccard on words) for now.
    Can be upgraded to embedding-based similarity later.
    """
    def _word_set(text: str) -> Set[str]:
        return set(text.lower().split())

    def _jaccard_similarity(text1: str, text2: str) -> float:
        set1 = _word_set(text1)
        set2 = _word_set(text2)
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    unique_questions = []
    seen_queries = set()

    for q in questions:
        query = q.get("query", "").lower().strip()

        # Check for exact duplicates
        if query in seen_queries:
            continue

        # Check for similar queries
        is_duplicate = False
        for seen_query in seen_queries:
            similarity = _jaccard_similarity(query, seen_query)
            if similarity > similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_questions.append(q)
            seen_queries.add(query)

    return unique_questions


def auto_link_chunks(
    question: Dict,
    searcher: HybridSearcher,
    top_k: int = 3,
) -> List[str]:
    """
    Automatically find supporting chunks for a question using retrieval.
    
    Returns list of chunk IDs.
    """
    query = question.get("query", "")
    if not query:
        return []

    results = searcher.search_raw(query, top_k=top_k)
    chunk_ids = [chunk.id for chunk, _score in results]

    # If question has source_chunk_id, prioritize it
    source_id = question.get("source_chunk_id")
    if source_id and source_id not in chunk_ids:
        chunk_ids.insert(0, source_id)

    return chunk_ids[:top_k]


def validate_and_filter(
    questions: List[Dict],
    auto_link: bool = False,
    searcher: Optional[HybridSearcher] = None,
) -> tuple[List[Dict], List[Dict]]:
    """
    Validate and filter questions.
    
    Returns:
        (valid_questions, invalid_questions_with_errors)
    """
    valid = []
    invalid = []

    for q in questions:
        is_valid, errors = validate_question(q)
        
        if is_valid:
            # Auto-link chunks if requested
            if auto_link and searcher:
                if "supporting_chunk_ids" not in q or not q["supporting_chunk_ids"]:
                    q["supporting_chunk_ids"] = auto_link_chunks(q, searcher)
            
            valid.append(q)
        else:
            q["_validation_errors"] = errors
            invalid.append(q)

    # Deduplicate valid questions
    valid = deduplicate_questions(valid)

    return valid, invalid


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and filter generated QA pairs."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Input JSONL file with generated questions",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for validated questions (default: input_file with .validated suffix)",
    )
    parser.add_argument(
        "--auto-link",
        action="store_true",
        help="Automatically link supporting chunks using retrieval",
    )
    parser.add_argument(
        "--deduplicate",
        action="store_true",
        default=True,
        help="Remove duplicate questions (default: True)",
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}")
        return

    # Load questions
    print(f"Loading questions from {args.input_file}...")
    questions = []
    with args.input_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                questions.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON line: {e}")
                continue

    print(f"Loaded {len(questions)} questions")

    # Initialize searcher if auto-linking
    searcher = None
    if args.auto_link:
        print("Initializing searcher for auto-linking...")
        
        chunks = load_chunks()
        searcher = HybridSearcher.from_chunks(chunks, use_reranker=True)

    # Validate and filter
    print("\nValidating questions...")
    valid, invalid = validate_and_filter(
        questions,
        auto_link=args.auto_link,
        searcher=searcher,
    )

    print(f"\nValidation results:")
    print(f"  Valid: {len(valid)}")
    print(f"  Invalid: {len(invalid)}")

    if invalid:
        print("\nInvalid questions (first 5):")
        for q in invalid[:5]:
            print(f"  - {q.get('query', 'N/A')[:60]}...")
            print(f"    Errors: {', '.join(q.get('_validation_errors', []))}")

    # Save validated questions
    output_path = args.output or args.input_file.with_suffix(".validated.jsonl")
    print(f"\nSaving validated questions to {output_path}...")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write("# Validated questions\n")
        for q in valid:
            # Remove validation metadata
            q_clean = {k: v for k, v in q.items() if not k.startswith("_")}
            f.write(json.dumps(q_clean, ensure_ascii=False) + "\n")

    print(f"Saved {len(valid)} validated questions to {output_path}")


if __name__ == "__main__":
    main()
