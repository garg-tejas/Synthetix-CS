# QA Generation Workflow

## 6-Day Workflow (with API limits)

Due to API rate limits, use this 6-day workflow:

- **Days 1-3**: Generate questions for each subject (without scoring)
- **Days 4-6**: Score questions for each subject

## Day 1-3: Generate Questions (No Scoring)

### Day 1: Operating Systems (OS)

```bash
uv run python -m eval.generation.batch_generate \
  --subject os \
  --questions-per-chunk 2 \
  --batch-size 5
```

Output: `eval/generation/output/generated_questions_os.jsonl`

### Day 2: Database Management Systems (DBMS)

```bash
uv run python -m eval.generation.batch_generate \
  --subject dbms \
  --questions-per-chunk 2 \
  --batch-size 5
```

Output: `eval/generation/output/generated_questions_dbms.jsonl`

### Day 3: Computer Networks (CN)

```bash
uv run python -m eval.generation.batch_generate \
  --subject cn \
  --questions-per-chunk 2 \
  --batch-size 5
```

Output: `eval/generation/output/generated_questions_cn.jsonl`

## Day 4-6: Score Questions

### Day 4: Score OS Questions

```bash
uv run python -m eval.generation.score_questions \
  eval/generation/output/generated_questions_os.jsonl \
  --min-quality-score 70
```

Output: `eval/generation/output/generated_questions_os.scored.jsonl`

### Day 5: Score DBMS Questions

```bash
uv run python -m eval.generation.score_questions \
  eval/generation/output/generated_questions_dbms.jsonl \
  --min-quality-score 70
```

Output: `eval/generation/output/generated_questions_dbms.scored.jsonl`

### Day 6: Score CN Questions

```bash
uv run python -m eval.generation.score_questions \
  eval/generation/output/generated_questions_cn.jsonl \
  --min-quality-score 70
```

Output: `eval/generation/output/generated_questions_cn.scored.jsonl`

## After Scoring: Combine and Validate

After all scoring is complete, you can:

1. Combine all scored questions
2. Validate and deduplicate
3. Import into the main questions dataset

## Quick Reference

### Generate with scoring (if you have API quota)

```bash
uv run python -m eval.generation.batch_generate \
  --subject os \
  --score \
  --min-quality-score 70
```

### Score existing questions

```bash
uv run python -m eval.generation.score_questions \
  <input_file.jsonl> \
  --min-quality-score 70 \
  --output <output_file.jsonl>
```

### Options

- `--subject`: Filter by subject (`os`, `dbms`, `cn`)
- `--questions-per-chunk`: Number of questions per chunk (default: 2)
- `--batch-size`: Chunks per batch (default: 5, lower for rate limits)
- `--max-chunks`: Limit number of chunks (for testing)
- `--score`: Enable scoring during generation (uses 2x API calls)
- `--min-quality-score`: Minimum score threshold (default: 70)
