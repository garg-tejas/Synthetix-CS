"""
Batch processing CLI for generating QA pairs from chunks using ModelScope API.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import List, Optional

from src.llm.client import ModelScopeClient, create_client
from src.rag.index import ChunkRecord, load_chunks
from .chunk_selector import select_chunks_for_generation
from .generate_qa import generate_questions_batch

ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "eval" / "generation" / "output"


def filter_chunks_for_generation(
    chunks: List[ChunkRecord],
    subject: Optional[str] = None,
    chunk_types: Optional[List[str]] = None,
) -> List[ChunkRecord]:
    """
    Filter chunks suitable for question generation.
    
    Excludes exercise, references, etc. Focuses on definition, algorithm, section, protocol.
    """
    if chunk_types is None:
        chunk_types = ["definition", "algorithm", "section", "protocol"]

    filtered = []
    excluded_types = {"exercise", "references", "bibliography", "citations"}
    excluded_headers = {
        "appendix",
        "exercises",
        "review questions",
        "selected bibliography",
    }

    for chunk in chunks:
        if chunk.chunk_type in excluded_types:
            continue

        header_lower = chunk.header_path.lower()
        if any(marker in header_lower for marker in excluded_headers):
            continue

        if chunk_types and chunk.chunk_type not in chunk_types:
            continue

        if subject:
            inferred = (chunk.subject or _infer_subject_simple(chunk))
            if inferred != subject:
                continue

        filtered.append(chunk)

    return filtered


def _infer_subject_simple(chunk: ChunkRecord) -> str:
    """Simple subject inference."""
    from .generate_qa import _infer_subject
    return _infer_subject(chunk)


def save_checkpoint(questions: List[dict], checkpoint_path: Path, chunk_id: str) -> None:
    """Save intermediate results to checkpoint file."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if checkpoint_path.exists():
        with checkpoint_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    try:
                        existing.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    existing.extend(questions)

    with checkpoint_path.open("w", encoding="utf-8") as f:
        f.write("# Generated questions checkpoint\n")
        for q in existing:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"  Checkpoint saved: {len(existing)} total questions")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate QA pairs from textbook chunks using ModelScope API."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: from MODELSCOPE_MODEL env var, or Qwen/Qwen3-Coder-480B-A35B-Instruct)",
    )
    parser.add_argument(
        "--modelscope-token",
        type=str,
        default=None,
        help="ModelScope API token (or set MODELSCOPE_API_TOKEN env var)",
    )
    parser.add_argument(
        "--subject",
        choices=["os", "dbms", "cn"],
        help="Filter chunks by subject",
    )
    parser.add_argument(
        "--questions-per-chunk",
        type=int,
        default=2,
        help="Number of questions to generate per chunk (default: 2)",
    )
    parser.add_argument(
        "--chunk-types",
        nargs="+",
        default=["definition", "algorithm", "section", "protocol"],
        help="Chunk types to include (default: definition algorithm section protocol)",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Maximum number of chunks to process (for testing)",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=OUTPUT_DIR / "generated_questions.jsonl",
        help="Checkpoint file path",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of chunks to process before saving checkpoint (default: 5 to avoid concurrency limits)",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=5.0,
        help="Seconds to wait between batches (default: 5; use e.g. 45 for strict rate limits)",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=70,
        help="Minimum placement_interview_score (0-100) to keep questions (default: 70)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Start from scratch: delete existing checkpoint if present (no resume)",
    )

    args = parser.parse_args()

    if args.reset and args.checkpoint.exists():
        args.checkpoint.unlink()
        print(f"Reset: removed existing checkpoint {args.checkpoint}")

    print("Loading chunks...")
    all_chunks = load_chunks(subject=args.subject)

    print(f"Filtering chunks...")
    filtered_chunks = filter_chunks_for_generation(
        all_chunks,
        subject=args.subject,
        chunk_types=args.chunk_types,
    )

    if not filtered_chunks:
        print("No chunks to process. Adjust filters.")
        return

    # Apply scoring and topic-diverse selection.
    target_count = args.max_chunks or len(filtered_chunks)
    print(
        f"Scoring {len(filtered_chunks)} chunks for QA potential and selecting "
        f"{target_count} with topic diversity..."
    )
    filtered_chunks = select_chunks_for_generation(
        filtered_chunks,
        target_count=target_count,
    )

    print(f"Selected {len(filtered_chunks)} chunks to process")
    print(f"Expected questions: ~{len(filtered_chunks) * args.questions_per_chunk}")

    print("\nInitializing ModelScope API client...")
    try:
        llm_client = create_client(
            model_name=args.model,
            modelscope_token=args.modelscope_token,
        )
        print(f"Using ModelScope API with model: {llm_client.model_name}")
        print(f"Daily limit: 2000 calls (approx. {len(filtered_chunks) * args.questions_per_chunk} calls needed)")
    except Exception as e:
        print(f"Error initializing ModelScope client: {e}")
        print("\nMake sure openai is installed:")
        print("  uv pip install openai")
        print("\nSet ModelScope API token:")
        print("  export MODELSCOPE_API_TOKEN=your_token")
        print("  Get token from: https://modelscope.cn/my/myaccesstoken")
        return

    print("\nGenerating questions...")
    print("=" * 60)

    all_questions = []
    processed = 0

    for i in range(0, len(filtered_chunks), args.batch_size):
        batch = filtered_chunks[i : i + args.batch_size]
        batch_num = i // args.batch_size + 1
        total_batches = (len(filtered_chunks) + args.batch_size - 1) // args.batch_size

        print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        try:
            batch_questions = generate_questions_batch(
                batch,
                llm_client,
                questions_per_chunk=args.questions_per_chunk,
                min_score=args.min_score,
            )
            all_questions.extend(batch_questions)
            processed += len(batch)

            print(f"  Generated {len(batch_questions)} questions from {len(batch)} chunks")
            if len(batch_questions) == 0:
                print(f"  Warning: No questions generated. Check LLM responses and parsing logic.")

            if (i + args.batch_size) % args.batch_size == 0 or i + args.batch_size >= len(
                filtered_chunks
            ):
                save_checkpoint(batch_questions, args.checkpoint, batch[0].id if batch else "unknown")
            
            # Delay between batches to avoid rate limits
            if i + args.batch_size < len(filtered_chunks):
                delay = args.batch_delay
                print(f"  Waiting {delay:.1f}s before next batch...")
                time.sleep(delay)

        except Exception as e:
            print(f"  Error processing batch: {e}")
            print("  Continuing with next batch...")
            continue

    print("\n" + "=" * 60)
    print(f"Generation complete!")
    print(f"  Processed: {processed}/{len(filtered_chunks)} chunks")
    print(f"  Generated: {len(all_questions)} questions")
    print(f"  Output: {args.checkpoint}")

    if all_questions:
        print("\nNext steps:")
        print("  1. Review generated questions:")
        print(f"     cat {args.checkpoint}")
        print("  2. Validate and filter:")
        print("     uv run python -m eval.generation.validate_qa", args.checkpoint)
        print("  3. Import into questions.jsonl:")
        print("     uv run python -m eval.dataset.build_questions import-from-llm", args.checkpoint)


if __name__ == "__main__":
    main()
