## Setup and Usage

This guide walks through setting up the backend locally, running the QA pipeline (generation -> LLM scoring -> validation), seeding quiz content, and running the API.

### 1. Prerequisites

- Python 3.12 with `uv` available in your shell
- Docker (recommended) or a local PostgreSQL instance

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment

1. Copy the example file:

```bash
cp .env.example .env
```

2. Edit `.env` and set:

- LLM settings (for Z.AI / GLM or your chosen provider)
- `DATABASE_URL`, for example:

```env
DATABASE_URL=postgresql+asyncpg://csrag:csrag@localhost:5432/cs_rag
```

### 4. Start PostgreSQL (Docker)

If you do not already have Postgres running, start a container:

```bash
docker run --name csrag-postgres \
  -e POSTGRES_USER=csrag \
  -e POSTGRES_PASSWORD=csrag \
  -e POSTGRES_DB=cs_rag \
  -p 5432:5432 \
  -d postgres:16
```

On subsequent runs:

```bash
docker start csrag-postgres
```

### 5. Run migrations

Apply Alembic migrations to create the schema:

```bash
uv run alembic upgrade head
```

You can verify the tables exist with:

```bash
uv run python -m scripts.check_db
```

You should see at least `users`, `topics`, `cards`, `review_states`, and `review_attempts`.

### 6. Ensure chunks exist

`data/chunks.jsonl` should contain the RAG chunks.

If needed, regenerate with your chunking pipeline before proceeding.

### 7. QA pipeline (post-generation LLM scoring)

#### 7.1 Generate candidate questions

Example:

```bash
uv run python -m eval.generation.batch_generate \
  --subject os \
  --questions-per-chunk 2 \
  --batch-size 5 \
  --quality-mode llm_only \
  --min-score 85 \
  --checkpoint eval/generation/output/generated_questions.jsonl
```

Repeat for `dbms` and `cn` as needed, or run without `--subject` for all.

#### 7.2 Score questions with LLM

```bash
uv run python -m eval.generation.score_questions \
  eval/generation/output/generated_questions.jsonl \
  --model glm-4.7-flash \
  --batch-size 10 \
  --max-batch-chars 24000 \
  --batch-delay 0 \
  --checkpoint eval/generation/output/generated_questions.llm_checkpoint.jsonl \
  --min-quality-score 85
```

This creates:

- `eval/generation/output/generated_questions.scored.jsonl` (accepted by score threshold)
- `eval/generation/output/generated_questions.rejected.jsonl` (rejected by score threshold)
- `eval/generation/output/generated_questions.llm_checkpoint.jsonl` (full graded rows + resume state)

#### 7.3 Validate scored rows into final seed file

Recommended: validate from the graded checkpoint (full set):

```bash
uv run python -m eval.generation.validate_qa \
  eval/generation/output/generated_questions.llm_checkpoint.jsonl \
  --min-interview-score 85 \
  --output eval/generation/output/generated_questions.llm_checkpoint.validated.jsonl
```

Optional helper to tune `--batch-size` and `--max-batch-chars`:

```bash
uv run python -m eval.generation.analyze_scoring_payload \
  eval/generation/output/generated_questions.jsonl \
  --target-max-chars 24000 \
  --target-batch-size 10
```

### 8. Seed quiz content

First, run in dry-run mode:

```bash
uv run python -m scripts.seed_cards --input eval/generation/output/generated_questions.llm_checkpoint.validated.jsonl
```

Then write topics/cards into PostgreSQL:

```bash
uv run python -m scripts.seed_cards --input eval/generation/output/generated_questions.llm_checkpoint.validated.jsonl --apply
```

This will:

- Ensure `topics` rows exist for `os`, `cn`, and `dbms`
- Insert one `Card` per validated question, linked to the appropriate topic

### 9. Run the API

Start the FastAPI app:

```bash
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will:

- Load RAG chunks and build the RAG agent
- Use PostgreSQL for auth and quiz persistence

### 10. Exercise the main flows

#### 10.1 Auth

- `POST /auth/signup` - create a user and receive access/refresh tokens
- `POST /auth/login` - log in with email or username
- `POST /auth/refresh` - get a new access token from a refresh token
- `GET /auth/me` - inspect the current user

#### 10.2 RAG endpoints

- `GET /api/health` - basic health and `chunks_loaded` count
- `GET /api/stats` - active conversation count
- `POST /api/search` - retrieval only
- `POST /api/chat` - non-streaming RAG answer
- `POST /api/chat/stream` - streaming RAG answer (SSE)

#### 10.3 Quiz endpoints

All quiz endpoints require a Bearer token from the auth routes.

- `GET /api/quiz/topics` - list topics and total card counts
- `POST /api/quiz/next` - fetch the next batch of cards to review
- `POST /api/quiz/answer` - submit a quality rating for a card and update the schedule
- `GET /api/quiz/stats` - per-topic stats (total, learned, due today, overdue)

These flows together give you a live, seeded skill-decay tracker on top of the RAG system.
