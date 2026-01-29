"""
CLI for scoring existing QA pairs using LLM quality scoring.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from src.llm.client import create_client
from .generate_qa import score_questions_batch

ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score existing QA pairs for placement interview suitability."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Input JSONL file with questions to score",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for scored questions (default: input_file with .scored suffix)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: from MODELSCOPE_MODEL env var)",
    )
    parser.add_argument(
        "--modelscope-token",
        type=str,
        default=None,
        help="ModelScope API token (or set MODELSCOPE_API_TOKEN env var)",
    )
    parser.add_argument(
        "--min-quality-score",
        type=int,
        default=70,
        help="Minimum quality score (0-100) to accept questions (default: 70)",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Don't filter questions, just add scores to all questions",
    )
    parser.add_argument(
        "--subject",
        choices=["os", "dbms", "cn"],
        help="Filter questions by subject (optional, for organization)",
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}")
        return

    # Load questions
    print(f"Loading questions from {args.input_file}...")
    questions: List[dict] = []
    with args.input_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            try:
                questions.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON line: {e}")
                continue

    print(f"Loaded {len(questions)} questions")

    # Filter by subject if specified
    if args.subject:
        original_count = len(questions)
        questions = [q for q in questions if q.get("source_subject") == args.subject]
        print(f"Filtered to {len(questions)} questions for subject: {args.subject} (removed {original_count - len(questions)})")
        if not questions:
            print("No questions found for this subject.")
            return

    # Initialize LLM client
    print("\nInitializing ModelScope API client...")
    try:
        llm_client = create_client(
            model_name=args.model,
            modelscope_token=args.modelscope_token,
        )
        print(f"Using ModelScope API with model: {llm_client.model_name}")
        print(f"Quality threshold: {args.min_quality_score}/100")
        if not args.no_filter:
            print(f"Filtering: Questions below threshold will be excluded")
        else:
            print(f"Filtering: Disabled (all questions will be scored and included)")
    except Exception as e:
        print(f"Error initializing ModelScope client: {e}")
        print("\nMake sure openai is installed:")
        print("  uv pip install openai")
        print("\nSet ModelScope API token:")
        print("  export MODELSCOPE_API_TOKEN=your_token")
        print("  Get token from: https://modelscope.cn/my/myaccesstoken")
        return

    # Score questions
    print(f"\nScoring {len(questions)} questions...")
    print("=" * 60)

    accepted, rejected = score_questions_batch(
        questions,
        llm_client,
        min_quality_score=args.min_quality_score,
        filter_low_scores=not args.no_filter,
    )

    print("\n" + "=" * 60)
    print(f"Scoring complete!")
    print(f"  Total questions: {len(questions)}")
    print(f"  Accepted (score >= {args.min_quality_score}): {len(accepted)}")
    if rejected:
        print(f"  Rejected (score < {args.min_quality_score}): {len(rejected)}")

    if rejected and not args.no_filter:
        print("\nRejected questions (first 5):")
        for q in rejected[:5]:
            score = q.get("quality_score", "N/A")
            query = q.get("query", "N/A")[:60]
            print(f"  [{score}] {query}...")

    # Save scored questions
    output_path = args.output or args.input_file.with_suffix(".scored.jsonl")
    print(f"\nSaving scored questions to {output_path}...")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write("// Scored questions\n")
        for q in accepted:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"Saved {len(accepted)} questions to {output_path}")

    # Optionally save rejected questions
    if rejected and not args.no_filter:
        rejected_path = args.input_file.with_suffix(".rejected.jsonl")
        print(f"Saving rejected questions to {rejected_path}...")
        with rejected_path.open("w", encoding="utf-8") as f:
            f.write("// Rejected questions (below quality threshold)\n")
            for q in rejected:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        print(f"Saved {len(rejected)} rejected questions to {rejected_path}")


if __name__ == "__main__":
    main()
