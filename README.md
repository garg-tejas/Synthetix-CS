# CoreCS Interview Lab

A full-stack CS interview prep app for OS, DBMS, and CN. It turns textbook chunks into interview-style question cards, grades answers with an LLM pipeline, and serves them via spaced repetition with topic-scoped sessions and a learning path.

## Features

- **Review workspace** — Topic-scoped sessions, per-answer feedback, due/overdue tracking
- **Learning path** — Node graph with completed/current/unlocked/locked states; questions follow path order
- **RAG API** — Hybrid retrieval, citation-backed chat and search
- **Quiz API** — Sessions, grading, and progress persisted in PostgreSQL
- **Offline pipeline** — Generate, score, validate, and seed cards from chunks

## API surface

- Auth: `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`
- RAG: `POST /api/search`, `POST /api/chat`, `POST /api/chat/stream`, `GET /api/health`, `GET /api/stats`
- Quiz: `GET /api/quiz/topics`, `GET /api/quiz/stats`, `POST /api/quiz/sessions/start`, `POST /api/quiz/sessions/{id}/answer`, `POST /api/quiz/sessions/{id}/finish`
- Scripts: `python -m scripts.build_topic_dependency_graph`, `scripts.sync_topic_dependency_graph`, `scripts.check_learning_path_graph`
- Pipeline: `eval.generation` (generate, score, validate) then `scripts.seed_cards`

## Repo layout

```
src/       API, auth, DB models, RAG, session service, path planner
eval/      Offline generation and evaluation
scripts/   Chunking, preprocessing, seeding
frontend/  React SPA (Vite, React Router)
docs/      Setup and architecture
tests/     Pytest suite
```

## Setup

See `docs/SETUP.md` for environment setup, migrations, QA pipeline, and running the API.
