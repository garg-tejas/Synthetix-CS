# QA Generation Workflow

## Recommended Workflow

Generation and scoring are both LLM-driven. Scoring is optimized for large
files with sequential batched requests and checkpoint/resume.

## Step 1: Generate Questions

### Day 1: Operating Systems (OS)

```bash
uv run python -m eval.generation.batch_generate \
  --subject os \
  --questions-per-chunk 2 \
  --batch-size 5 \
  --quality-mode llm_only
```

Output: `eval/generation/output/generated_questions_os.jsonl`

### Day 2: Database Management Systems (DBMS)

```bash
uv run python -m eval.generation.batch_generate \
  --subject dbms \
  --questions-per-chunk 2 \
  --batch-size 5 \
  --quality-mode llm_only
```

Output: `eval/generation/output/generated_questions_dbms.jsonl`

### Day 3: Computer Networks (CN)

```bash
uv run python -m eval.generation.batch_generate \
  --subject cn \
  --questions-per-chunk 2 \
  --batch-size 5 \
  --quality-mode llm_only
```

Output: `eval/generation/output/generated_questions_cn.jsonl`

## Step 2: Score Questions (LLM-First, Batched)

### Score OS Questions

```bash
uv run python -m eval.generation.score_questions \
  eval/generation/output/generated_questions_os.jsonl \
  --model glm-4.7-flash \
  --batch-size 20 \
  --min-quality-score 85
```

Output: `eval/generation/output/generated_questions_os.scored.jsonl`

### Score DBMS Questions

```bash
uv run python -m eval.generation.score_questions \
  eval/generation/output/generated_questions_dbms.jsonl \
  --model glm-4.7-flash \
  --batch-size 20 \
  --min-quality-score 85
```

Output: `eval/generation/output/generated_questions_dbms.scored.jsonl`

### Score CN Questions

```bash
uv run python -m eval.generation.score_questions \
  eval/generation/output/generated_questions_cn.jsonl \
  --model glm-4.7-flash \
  --batch-size 20 \
  --min-quality-score 85
```

Output: `eval/generation/output/generated_questions_cn.scored.jsonl`

## Step 3: Validate, Deduplicate, and Import

After scoring, you can:

1. Combine all scored questions
2. Validate and deduplicate using LLM score threshold
3. Import into the main questions dataset

## Quick Reference

### Score existing questions

```bash
uv run python -m eval.generation.score_questions \
  <input_file.jsonl> \
  --model glm-4.7-flash \
  --batch-size 20 \
  --min-quality-score 85 \
  --output <output_file.jsonl>
```

### Score 9k questions with resume

```bash
uv run python -m eval.generation.score_questions \
  eval/generation/output/generated_questions.jsonl \
  --model glm-4.7-flash \
  --batch-size 20 \
  --batch-delay 1.5 \
  --checkpoint eval/generation/output/generated_questions.llm_checkpoint.jsonl \
  --min-quality-score 85
```

### Validate scored questions

```bash
uv run python -m eval.generation.validate_qa \
  <input_file.scored.jsonl> \
  --min-interview-score 85
```

### Options

- `--subject`: Filter by subject (`os`, `dbms`, `cn`)
- `--questions-per-chunk`: Number of questions per chunk (default: 2)
- `--batch-size`: Chunk batch size for generation; question batch size for scoring
- `--max-chunks`: Limit number of chunks (for testing)
- `--min-quality-score`: Minimum score threshold (default: 85)
- `--checkpoint`: Resume scoring large files without restarting
- `--max-batch-chars`: Cap prompt size for stable large-run scoring
- `--min-interview-score`: Validation threshold on `quality_score` / `llm_interview_score` (default: 85)
- `--quality-mode`: `deterministic | llm_hybrid | llm_only` (recommended: `llm_only`)
- `--no-llm-rewrite`: Keep only direct keep/reject decisions from reviewer
