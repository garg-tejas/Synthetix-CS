## Setup and Usage

This guide walks through setting up the backend locally, seeding quiz content, and running the API.

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
   DATABASE_URL=postgresql+asyncpg://slm:slm@localhost:5432/slm_rag
   ```

### 4. Start PostgreSQL (Docker)

If you do not already have Postgres running, start a container:

```bash
docker run --name slm-postgres ^
  -e POSTGRES_USER=slm ^
  -e POSTGRES_PASSWORD=slm ^
  -e POSTGRES_DB=slm_rag ^
  -p 5432:5432 ^
  -d postgres:16
```

On subsequent runs:

```bash
docker start slm-postgres
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

### 6. Ensure chunks and validated QA exist

- `data/chunks.jsonl` should contain the RAG chunks.
- `eval/generation/output/generated_questions.validated.jsonl` should contain the validated QA pairs.

If needed, follow the QA generation workflow under `eval/generation/` to regenerate these files.

### 7. Seed quiz content

First, run in dry‑run mode to see what will be seeded:

```bash
uv run python -m scripts.seed_cards --input eval/generation/output/generated_questions.validated.jsonl
```

Then, to write topics and cards into PostgreSQL:

```bash
uv run python -m scripts.seed_cards --input eval/generation/output/generated_questions.validated.jsonl --apply
```

This will:

- Ensure `topics` rows exist for `os`, `cn`, and `dbms`
- Insert one `Card` per validated question, linked to the appropriate topic

### 8. Run the API

Start the FastAPI app with:

```bash
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will:

- Load RAG chunks and build the RAG agent
- Use PostgreSQL for auth and quiz persistence

### 9. Exercise the main flows

#### 9.1 Auth

- `POST /auth/signup` – create a user and receive access/refresh tokens
- `POST /auth/login` – log in with email or username
- `POST /auth/refresh` – get a new access token from a refresh token
- `GET /auth/me` – inspect the current user

#### 9.2 RAG endpoints

- `GET /api/health` – basic health and `chunks_loaded` count
- `GET /api/stats` – active conversation count
- `POST /api/search` – retrieval only
- `POST /api/chat` – non‑streaming RAG answer
- `POST /api/chat/stream` – streaming RAG answer (SSE)

#### 9.3 Quiz endpoints

All quiz endpoints require a Bearer token from the auth routes.

- `GET /api/quiz/topics` – list topics and total card counts
- `POST /api/quiz/next` – fetch the next batch of cards to review
- `POST /api/quiz/answer` – submit a quality rating for a card and update the schedule
- `GET /api/quiz/stats` – per‑topic stats (total, learned, due today, overdue)

These flows together give you a live, seeded skill‑decay tracker on top of the RAG system.

