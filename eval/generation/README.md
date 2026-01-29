# QA Generation Module

Generate question-answer pairs from textbook chunks using ModelScope API.

## Setup

**No installation needed!** Just get an API token.

1. **Get ModelScope API token**:
   - Visit: https://modelscope.cn/my/myaccesstoken
   - Generate a token
   - **Daily limit: 2000 inference calls** (enough for ~1000 chunks with 2 questions each)

2. **Configure environment variables** (choose one method):

   **Option A: Using `.env` file (recommended)**:

   ```bash
   # Copy the example file from project root
   cp .env.example .env

   # Edit .env and add your token
   # MODELSCOPE_API_TOKEN=your_token_here
   ```

   **Option B: Set environment variables directly**:

   ```bash
   export MODELSCOPE_API_TOKEN="your_token_here"
   export MODELSCOPE_MODEL="zai-org/GLM-4.7-Flash"  # Optional, this is the default
   ```

That's it! The script will automatically load `.env` if it exists, or use environment variables.

## Usage

### 1. Generate QA pairs from chunks

```bash
# Generate questions using ModelScope API (default)
uv run python -m eval.generation.batch_generate

# Test with small subset first
uv run python -m eval.generation.batch_generate --max-chunks 10 --questions-per-chunk 2

# Generate only for OS
uv run python -m eval.generation.batch_generate --subject os

# Generate 3 questions per chunk
uv run python -m eval.generation.batch_generate --questions-per-chunk 3

# Use specific model
uv run python -m eval.generation.batch_generate --model "zai-org/GLM-4.7-Flash"
```

Output: `eval/generation/output/generated_questions.jsonl`

### 2. Validate and filter

```bash
uv run python -m eval.generation.validate_qa eval/generation/output/generated_questions.jsonl

# With auto-linking of supporting chunks
uv run python -m eval.generation.validate_qa eval/generation/output/generated_questions.jsonl --auto-link
```

Output: `eval/generation/output/generated_questions.validated.jsonl`

### 3. Import into questions.jsonl

```bash
uv run python -m eval.dataset.build_questions import-from-llm eval/generation/output/generated_questions.validated.jsonl

# With auto-linking
uv run python -m eval.dataset.build_questions import-from-llm eval/generation/output/generated_questions.validated.jsonl --auto-link
```

## Workflow Example

```bash
# 1. Generate (start small for testing)
uv run python -m eval.generation.batch_generate --subject os --max-chunks 20 --questions-per-chunk 2

# 2. Validate
uv run python -m eval.generation.validate_qa eval/generation/output/generated_questions.jsonl --auto-link

# 3. Review validated questions
cat eval/generation/output/generated_questions.validated.jsonl

# 4. Import
uv run python -m eval.dataset.build_questions import-from-llm eval/generation/output/generated_questions.validated.jsonl

# 5. Verify
uv run python -m eval.dataset.build_questions validate
```

## Notes

- **No installation**: Just need API token
- **Daily limit**: 2000 calls/day (free tier)
- **Speed**: Fast, cloud-based inference
- **Cost**: Free for 2k calls/day
- **Rate limiting**: Automatic (0.5s delay between requests)
- **Checkpoints**: Progress is saved automatically, can resume if interrupted
