"""
Dry-run script for seeding quiz cards from validated QA data.

For now this only:
- Reads a validated JSONL file.
- Reports basic counts and distributions (by difficulty / question_type).
- Does NOT write anything to the database.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List


def load_questions(path: Path) -> List[Dict]:
    questions: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            try:
                questions.append(json.loads(line))
            except json.JSONDecodeError:
                # Ignore malformed lines in dry-run mode
                continue
    return questions


def summarize_questions(questions: List[Dict]) -> None:
    total = len(questions)
    print(f"Loaded {total} questions")
    if total == 0:
        return

    by_difficulty: Counter = Counter()
    by_qtype: Counter = Counter()

    for q in questions:
        by_difficulty[q.get("difficulty", "unknown")] += 1
        by_qtype[q.get("question_type", "unknown")] += 1

    print("\nBy difficulty:")
    for diff, count in sorted(by_difficulty.items(), key=lambda x: x[0]):
        pct = (count / total) * 100
        print(f"  {diff:10s}: {count:5d} ({pct:5.1f}%)")

    print("\nBy question_type:")
    for qtype, count in sorted(by_qtype.items(), key=lambda x: x[0]):
        pct = (count / total) * 100
        print(f"  {qtype:12s}: {count:5d} ({pct:5.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run: summarize validated QA file for seeding quiz cards.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("eval/generation/output/generated_questions.validated.jsonl"),
        help="Path to validated questions JSONL file",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}")
        return

    print(f"Loading validated questions from {args.input}...")
    questions = load_questions(args.input)
    summarize_questions(questions)
    print("\nDry run complete. No database changes were made.")


if __name__ == "__main__":
    main()

