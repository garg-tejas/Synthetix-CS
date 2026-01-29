"""
Interactive CLI tool for building the questions dataset.

Usage:
    uv run python -m eval.dataset.build_questions add
    uv run python -m eval.dataset.build_questions link q_001
    uv run python -m eval.dataset.build_questions validate
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.rag import HybridSearcher, load_chunks

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = ROOT / "data" / "questions.jsonl"


def load_questions() -> List[Dict[str, Any]]:
    """Load all questions from JSONL file."""
    if not QUESTIONS_PATH.exists():
        return []
    
    questions = []
    with QUESTIONS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            questions.append(json.loads(line))
    return questions


def save_questions(questions: List[Dict[str, Any]]) -> None:
    """Save questions to JSONL file."""
    QUESTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with QUESTIONS_PATH.open("w", encoding="utf-8") as f:
        f.write("// Questions dataset for Phase 1 reasoning model evaluation\n")
        f.write("// Each line is a JSON object (see schema in comments above)\n\n")
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")


def add_question() -> None:
    """Interactively add a new question."""
    questions = load_questions()
    
    print("Adding new question...")
    print("=" * 60)
    
    q_id = input("Question ID (e.g., q_001): ").strip()
    if not q_id:
        print("Error: Question ID is required")
        return
    
    if any(q["id"] == q_id for q in questions):
        print(f"Error: Question ID '{q_id}' already exists")
        return
    
    subject = input("Subject (os/dbms/cn): ").strip().lower()
    if subject not in ("os", "dbms", "cn"):
        print("Error: Subject must be os, dbms, or cn")
        return
    
    query = input("Query: ").strip()
    if not query:
        print("Error: Query is required")
        return
    
    question_type = input("Question type (definition/procedural/comparative/factual): ").strip().lower()
    if question_type not in ("definition", "procedural", "comparative", "factual"):
        print("Error: Invalid question type")
        return
    
    answer = input("Ground truth answer: ").strip()
    if not answer:
        print("Error: Answer is required")
        return
    
    difficulty = input("Difficulty (easy/medium/hard): ").strip().lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    
    atomic_facts_input = input("Atomic facts (comma-separated, optional): ").strip()
    atomic_facts = [f.strip() for f in atomic_facts_input.split(",") if f.strip()]
    
    new_question = {
        "id": q_id,
        "subject": subject,
        "query": query,
        "question_type": question_type,
        "answer": answer,
        "supporting_chunk_ids": [],
        "atomic_facts": atomic_facts,
        "difficulty": difficulty,
    }
    
    questions.append(new_question)
    save_questions(questions)
    print(f"\nQuestion '{q_id}' added successfully!")
    print("Use 'link' command to add supporting chunk IDs.")


def link_chunks(question_id: str) -> None:
    """Search for and link supporting chunks to a question."""
    questions = load_questions()
    
    question = next((q for q in questions if q["id"] == question_id), None)
    if not question:
        print(f"Error: Question '{question_id}' not found")
        return
    
    print(f"Linking chunks for question: {question['query']}")
    print("=" * 60)
    
    chunks = load_chunks()
    searcher = HybridSearcher.from_chunks(chunks, use_reranker=True)
    
    results = searcher.search_raw(question["query"], top_k=10)
    
    print("\nTop retrieval results:")
    for i, (chunk, score) in enumerate(results, 1):
        print(f"\n{i}. {chunk.id}")
        print(f"   Score: {score:.4f}")
        print(f"   Header: {chunk.header_path}")
        print(f"   Type: {chunk.chunk_type}")
        print(f"   Text: {chunk.text[:200].replace(chr(10), ' ')}...")
    
    print("\n" + "=" * 60)
    selected = input(
        "Enter chunk IDs to link (comma-separated, e.g., 1,3,5 or chunk_00294,chunk_00431): "
    ).strip()
    
    if not selected:
        print("No chunks selected")
        return
    
    selected_ids = []
    for s in selected.split(","):
        s = s.strip()
        if s.isdigit():
            idx = int(s) - 1
            if 0 <= idx < len(results):
                selected_ids.append(results[idx][0].id)
        else:
            selected_ids.append(s)
    
    question["supporting_chunk_ids"] = selected_ids
    save_questions(questions)
    print(f"\nLinked {len(selected_ids)} chunks to question '{question_id}'")


def validate_dataset() -> None:
    """Validate all questions have required fields."""
    questions = load_questions()
    
    if not questions:
        print("No questions found in dataset")
        return
    
    print(f"Validating {len(questions)} questions...")
    print("=" * 60)
    
    required_fields = ["id", "subject", "query", "question_type", "answer"]
    errors = []
    
    for q in questions:
        for field in required_fields:
            if field not in q or not q[field]:
                errors.append(f"{q.get('id', 'unknown')}: missing '{field}'")
        
        if q.get("subject") not in ("os", "dbms", "cn"):
            errors.append(f"{q['id']}: invalid subject '{q.get('subject')}'")
        
        if q.get("question_type") not in ("definition", "procedural", "comparative", "factual"):
            errors.append(f"{q['id']}: invalid question_type '{q.get('question_type')}'")
    
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("All questions are valid!")
    
    # Print summary
    by_subject = {}
    by_type = {}
    for q in questions:
        by_subject[q["subject"]] = by_subject.get(q["subject"], 0) + 1
        by_type[q["question_type"]] = by_type.get(q["question_type"], 0) + 1
    
    print("\nSummary:")
    print(f"  Total questions: {len(questions)}")
    print(f"  By subject: {by_subject}")
    print(f"  By type: {by_type}")
    print(f"  With chunks linked: {sum(1 for q in questions if q.get('supporting_chunk_ids'))}")


def import_from_llm(input_file: Path, auto_link: bool = False) -> None:
    """Import questions from LLM-generated JSONL file."""
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        return

    print(f"Loading questions from {input_file}...")
    generated_questions = []
    with input_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                generated_questions.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON line: {e}")
                continue

    print(f"Loaded {len(generated_questions)} generated questions")

    # Load existing questions
    existing_questions = load_questions()
    existing_ids = {q["id"] for q in existing_questions}

    # Initialize searcher if auto-linking
    searcher = None
    if auto_link:
        print("Initializing searcher for auto-linking...")
        chunks = load_chunks()
        searcher = HybridSearcher.from_chunks(chunks, use_reranker=True)

    # Convert to questions.jsonl format
    imported_count = 0
    skipped_count = 0

    for gen_q in generated_questions:
        # Generate unique ID if not present
        if "id" not in gen_q:
            base_id = f"q_{len(existing_questions) + imported_count + 1:03d}"
            counter = 1
            q_id = base_id
            while q_id in existing_ids:
                q_id = f"{base_id}_{counter}"
                counter += 1
            gen_q["id"] = q_id

        # Skip if ID already exists
        if gen_q["id"] in existing_ids:
            skipped_count += 1
            continue

        # Ensure required fields
        if "subject" not in gen_q:
            gen_q["subject"] = gen_q.get("source_subject", "os")

        # Auto-link chunks if requested
        if auto_link and searcher:
            if "supporting_chunk_ids" not in gen_q or not gen_q["supporting_chunk_ids"]:
                query = gen_q.get("query", "")
                if query:
                    results = searcher.search_raw(query, top_k=3)
                    gen_q["supporting_chunk_ids"] = [chunk.id for chunk, _score in results]

        # Remove LLM-specific metadata
        for key in ["source_chunk_id", "source_header", "source_subject"]:
            gen_q.pop(key, None)

        existing_questions.append(gen_q)
        existing_ids.add(gen_q["id"])
        imported_count += 1

    # Save
    save_questions(existing_questions)
    print(f"\nImport complete:")
    print(f"  Imported: {imported_count}")
    print(f"  Skipped (duplicates): {skipped_count}")
    print(f"  Total questions: {len(existing_questions)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and manage the questions dataset for evaluation."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    subparsers.add_parser("add", help="Add a new question interactively")
    subparsers.add_parser("validate", help="Validate all questions in the dataset")
    
    link_parser = subparsers.add_parser("link", help="Link supporting chunks to a question")
    link_parser.add_argument("question_id", help="Question ID to link chunks for")
    
    import_parser = subparsers.add_parser("import-from-llm", help="Import questions from LLM-generated JSONL")
    import_parser.add_argument("input_file", type=Path, help="Path to generated questions JSONL file")
    import_parser.add_argument("--auto-link", action="store_true", help="Automatically link supporting chunks")
    
    args = parser.parse_args()
    
    if args.command == "add":
        add_question()
    elif args.command == "link":
        link_chunks(args.question_id)
    elif args.command == "validate":
        validate_dataset()
    elif args.command == "import-from-llm":
        import_from_llm(args.input_file, auto_link=args.auto_link)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
