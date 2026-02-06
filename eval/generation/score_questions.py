"""
CLI for LLM-first scoring of generated QA pairs.

Designed for large sets (~9k rows):
- one API request at a time (no parallel calls)
- batched scoring to reduce request count
- checkpoint/resume support
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List

from src.llm.client import create_client

from .interview_quality import assess_interview_quality
from .llm_review import LLMBatchScoreOutcome, score_questions_batch_with_llm


def _truncate_error(error: Exception, max_len: int = 240) -> str:
    text = f"{type(error).__name__}: {error}"
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _load_jsonl(path: Path) -> List[dict]:
    rows: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _load_checkpoint(path: Path) -> Dict[int, dict]:
    if not path.exists():
        return {}
    seen: Dict[int, dict] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            idx = row.get("_row_index")
            if isinstance(idx, int):
                seen[idx] = row
    return seen


def _append_checkpoint(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _finalize_row(row: dict) -> dict:
    # Structural sanity (keyword-agnostic) as a weak floor.
    structural = assess_interview_quality(row, min_score=0)
    row["structural_quality_score"] = structural.score
    if structural.reasons:
        row["structural_quality_reasons"] = structural.reasons

    llm_score = row.get("llm_interview_score")
    try:
        llm_score_int = int(llm_score)
    except (TypeError, ValueError):
        llm_score_int = 0
    llm_score_int = max(0, min(100, llm_score_int))

    # LLM is primary; structure only guards malformed entries.
    row["quality_score"] = round(0.9 * llm_score_int + 0.1 * structural.score)
    return row


def _estimate_row_chars(row: dict) -> int:
    # Keep aligned with the scoring LLM payload fields in llm_review.py
    # (query, question_type, difficulty, source_subject, source_header, index).
    query = str(row.get("query") or "")
    question_type = str(row.get("question_type") or "")
    difficulty = str(row.get("difficulty") or "")
    source_subject = str(row.get("source_subject") or "")
    source_header = str(row.get("source_header") or "")
    return len(query) + len(question_type) + len(difficulty) + len(source_subject) + len(source_header) + 96


def _build_batches(rows: List[dict], *, max_items: int, max_chars: int) -> List[List[dict]]:
    batches: List[List[dict]] = []
    current: List[dict] = []
    current_chars = 0

    for row in rows:
        row_chars = _estimate_row_chars(row)
        if current and (len(current) >= max_items or current_chars + row_chars > max_chars):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(row)
        current_chars += row_chars

    if current:
        batches.append(current)
    return batches


def _should_keep(row: dict, min_quality_score: int) -> bool:
    decision = str(row.get("llm_review_decision") or "").strip().lower()
    score = row.get("quality_score")
    try:
        score_int = int(score)
    except (TypeError, ValueError):
        score_int = 0
    return decision in {"keep", "rewrite"} and score_int >= min_quality_score


def _count_missing_required(rows: List[dict], required: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {k: 0 for k in required}
    for row in rows:
        for key in required:
            val = row.get(key)
            missing = (
                val is None
                or (isinstance(val, str) and not val.strip())
                or (isinstance(val, list) and len(val) == 0)
            )
            if missing:
                counts[key] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-first scoring for generated interview questions."
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
        help="Accepted output file (default: <input>.scored.jsonl)",
    )
    parser.add_argument(
        "--rejected-output",
        type=Path,
        default=None,
        help="Rejected output file (default: <input>.rejected.jsonl)",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Checkpoint JSONL path for resume (default: <input>.llm_checkpoint.jsonl)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing checkpoint and rescore from scratch",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="glm-4.7-flash",
        help="LLM model name (default: glm-4.7-flash)",
    )
    parser.add_argument(
        "--modelscope-token",
        type=str,
        default=None,
        help="API key override (otherwise uses env vars)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Questions per LLM request (default: 20)",
    )
    parser.add_argument(
        "--max-batch-chars",
        type=int,
        default=24000,
        help="Approximate character budget per LLM request (default: 24000)",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=1.5,
        help="Delay seconds between LLM requests (default: 1.5)",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Optional limit for testing (process only first N pending batches)",
    )
    parser.add_argument(
        "--min-quality-score",
        type=int,
        default=85,
        help="Minimum final quality score (0-100) to keep a question",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Score all questions but do not drop low-score rows in output",
    )
    parser.add_argument(
        "--subject",
        choices=["os", "dbms", "cn"],
        help="Optional subject filter",
    )
    parser.add_argument(
        "--allow-rewrite",
        action="store_true",
        help="Allow LLM to rewrite borderline questions while scoring",
    )
    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: input file not found: {args.input_file}")
        return

    output_path = args.output or args.input_file.with_suffix(".scored.jsonl")
    rejected_path = args.rejected_output or args.input_file.with_suffix(".rejected.jsonl")
    checkpoint_path = args.checkpoint or args.input_file.with_suffix(".llm_checkpoint.jsonl")

    if args.reset and checkpoint_path.exists():
        checkpoint_path.unlink()
        print(f"Reset: removed checkpoint {checkpoint_path}")

    print(f"Loading questions from {args.input_file}...")
    questions = _load_jsonl(args.input_file)
    if not questions:
        print("No questions found.")
        return

    # Assign stable row indexes for checkpoint/resume.
    indexed_questions: List[dict] = []
    for i, q in enumerate(questions):
        qq = dict(q)
        qq["_row_index"] = i
        indexed_questions.append(qq)

    if args.subject:
        before = len(indexed_questions)
        indexed_questions = [
            q for q in indexed_questions if q.get("source_subject") == args.subject
        ]
        print(
            f"Subject filter {args.subject}: {len(indexed_questions)} / {before} questions kept"
        )
        if not indexed_questions:
            print("No questions to score after subject filter.")
            return

    print("Initializing LLM client...")
    try:
        llm_client = create_client(
            model_name=args.model,
            modelscope_token=args.modelscope_token,
        )
    except Exception as e:
        print(f"Error initializing LLM client: {e}")
        return
    print(f"Using model: {llm_client.model_name} ({llm_client.base_url})")
    print("Scoring mode: sequential batched requests (one request at a time)")
    print(
        f"Batch size: {args.batch_size}, max batch chars: {args.max_batch_chars}, "
        f"batch delay: {args.batch_delay:.1f}s, min quality: {args.min_quality_score}"
    )
    if args.allow_rewrite:
        print("Rewrite mode: enabled")

    # Resume state.
    scored_by_index = _load_checkpoint(checkpoint_path)
    if scored_by_index:
        print(f"Loaded {len(scored_by_index)} scored rows from checkpoint")
    else:
        print("No existing checkpoint rows found")

    pending = [
        q for q in indexed_questions
        if q["_row_index"] not in scored_by_index
    ]
    print(f"Pending rows: {len(pending)} / {len(indexed_questions)}")

    pending_batches = _build_batches(
        pending,
        max_items=max(1, args.batch_size),
        max_chars=max(4000, args.max_batch_chars),
    )
    print(f"Planned LLM requests: {len(pending_batches)}")

    processed_batches = 0
    for batch in pending_batches:
        if args.max_batches is not None and processed_batches >= args.max_batches:
            print(f"Stopping at max batches limit: {args.max_batches}")
            break

        batch_no = processed_batches + 1
        total_batches = len(pending_batches)
        print(f"Scoring batch {batch_no}/{total_batches} ({len(batch)} rows)...")
        try:
            outcome = score_questions_batch_with_llm(
                questions=batch,
                llm_client=llm_client,
                min_score=args.min_quality_score,
                allow_rewrite=args.allow_rewrite,
                max_retries=2,
            )
        except Exception as e:
            print(
                f"Warning: batch {batch_no} crashed; marking rows rejected and continuing. "
                f"Error: {_truncate_error(e)}"
            )
            fallback_rows: List[dict] = []
            for row in batch:
                failed = dict(row)
                failed["llm_review_decision"] = "reject"
                failed["llm_interview_score"] = 0
                failed["llm_interview_reasons"] = [f"Batch exception: {_truncate_error(e)}"]
                failed["quality_score"] = 0
                fallback_rows.append(failed)
            outcome = LLMBatchScoreOutcome(
                success=False,
                scored=fallback_rows,
                failed_indexes=list(range(len(batch))),
            )
        finalized_batch: List[dict] = []
        for row in outcome.scored:
            finalized = _finalize_row(row)
            finalized_batch.append(finalized)
            idx = finalized.get("_row_index")
            if isinstance(idx, int):
                scored_by_index[idx] = finalized

        _append_checkpoint(checkpoint_path, finalized_batch)
        processed_batches += 1

        if outcome.failed_indexes:
            print(
                f"  Warning: {len(outcome.failed_indexes)} rows had missing/failed LLM results in this batch"
            )
        if not outcome.success:
            print("  Warning: batch completed with LLM failure fallback rows")

        if processed_batches < len(pending_batches):
            time.sleep(max(0.0, args.batch_delay))

    # Reassemble in original order for selected scope.
    scored_rows: List[dict] = []
    missing_after_run = 0
    for q in indexed_questions:
        idx = q["_row_index"]
        row = scored_by_index.get(idx)
        if row is None:
            missing_after_run += 1
            fallback = dict(q)
            fallback["llm_review_decision"] = "reject"
            fallback["llm_interview_score"] = 0
            fallback["llm_interview_reasons"] = ["not scored in current run"]
            fallback = _finalize_row(fallback)
            row = fallback
        scored_rows.append(row)

    if missing_after_run:
        print(f"Warning: {missing_after_run} rows were not scored and were marked rejected.")

    accepted: List[dict] = []
    rejected: List[dict] = []
    for row in scored_rows:
        if args.no_filter or _should_keep(row, args.min_quality_score):
            accepted.append(row)
        else:
            rejected.append(row)

    required_fields = ["query", "answer", "question_type", "difficulty", "atomic_facts"]
    missing_acc = _count_missing_required(accepted, required_fields)
    missing_rej = _count_missing_required(rejected, required_fields)
    if any(v > 0 for v in missing_acc.values()):
        print(f"Warning: accepted set has missing required fields counts: {missing_acc}")
    if any(v > 0 for v in missing_rej.values()):
        print(f"Warning: rejected set has missing required fields counts: {missing_rej}")

    def _clean(row: dict) -> dict:
        return {k: v for k, v in row.items() if k != "_row_index"}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write("// LLM-scored accepted questions\n")
        for row in accepted:
            f.write(json.dumps(_clean(row), ensure_ascii=False) + "\n")

    with rejected_path.open("w", encoding="utf-8") as f:
        f.write("// LLM-scored rejected questions\n")
        for row in rejected:
            f.write(json.dumps(_clean(row), ensure_ascii=False) + "\n")

    print("\nScoring complete.")
    print(f"  Total in scope: {len(scored_rows)}")
    print(f"  Accepted: {len(accepted)}")
    print(f"  Rejected: {len(rejected)}")
    print(f"  Accepted output: {output_path}")
    print(f"  Rejected output: {rejected_path}")
    print(f"  Checkpoint: {checkpoint_path}")


if __name__ == "__main__":
    main()
