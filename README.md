# CoreCS Interview Lab

## What this project is

`CoreCS Interview Lab` is a full-stack CS interview prep platform for OS, DBMS, and CN.
It converts textbook chunks into interview-style question cards, scores and filters them with an
LLM-first pipeline, and serves them through a spaced-repetition quiz app with answer grading.

## What exists today

- RAG API with hybrid retrieval and citation-backed responses:
  `POST /api/search`, `POST /api/chat`, `POST /api/chat/stream`,
  `GET /api/health`, `GET /api/stats`, `DELETE /api/conversation`
- Auth API:
  `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`
- Quiz API (PostgreSQL-backed):
  `GET /api/quiz/topics`, `GET /api/quiz/stats`,
  `POST /api/quiz/sessions/start`,
  `POST /api/quiz/sessions/{session_id}/answer`,
  `POST /api/quiz/sessions/{session_id}/finish`
- Learning path graph scripts:
  `python -m scripts.build_topic_dependency_graph`,
  `python -m scripts.sync_topic_dependency_graph`,
  `python -m scripts.check_learning_path_graph`
- Offline QA pipeline:
  generate -> LLM score (`eval.generation.score_questions`) ->
  validate (`eval.generation.validate_qa`) -> seed cards (`scripts.seed_cards`)

## Repo layout (high level)

```text
src/     API, auth, DB models/session, RAG, generation, orchestrator, LLM client
eval/    Offline generation/evaluation tooling
scripts/ Helpers (chunking, preprocessing, seeding)
frontend/ React app
docs/    Setup and architecture notes
tests/   Pytest suite
```

## Setup

Use `docs/SETUP.md` for the complete flow:
- local env + Postgres + migrations
- QA pipeline (generate -> score -> validate)
- seeding cards into DB
- running the API
