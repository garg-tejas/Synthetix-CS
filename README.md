# SLM-Based RAG and Skill Tracker

This repository combines a retrieval-augmented question answering system with a spaced-repetition “skill decay” tracker for Operating Systems, Database Management Systems, and Computer Networks. The RAG pipeline answers questions with citations, and the skill tracker will quiz the user over time to keep those topics fresh.

## What is built today

- **RAG pipeline**
  - Hybrid retrieval (BM25 + dense embeddings with RRF merge)
  - Optional query understanding, HYDE, and cross-encoder reranking
  - Answer generation with citation markers and extracted citations
- **FastAPI backend**
  - `/api/search`, `/api/chat`, `/api/chat/stream`, `/api/health`, `/api/stats`, `/api/conversation`
  - Loads prebuilt chunks (`data/chunks.jsonl`) and wires them through the RAG agent
- **PostgreSQL persistence layer**
  - Async SQLAlchemy engine and Alembic migrations
  - Core models for the skill tracker: `User`, `Topic`, `Card`, `ReviewState`, `ReviewAttempt`
- **Authentication**
  - Password hashing (bcrypt via passlib)
  - JWT access and refresh tokens
  - Auth routes: `/auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/me`
- **Evaluation and content tooling**
  - Question generation and validation under `eval/generation/`
  - `scripts/seed_cards.py` dry-run script to summarize validated questions before seeding
- **Test coverage**
  - Retrieval, generation, orchestrator, API routes, and auth utilities covered by pytest

## What we are building next

- **Spaced-repetition quiz engine**
  - SM-2-style scheduler using `ReviewState` and `ReviewAttempt`
  - Quiz service to pick due/new cards and record attempts
- **Quiz APIs**
  - Endpoints for fetching next questions, submitting answers, and viewing progress
  - Integration with existing RAG chunks for explanations and context
- **Web UI (React, later phase)**
  - Authenticated dashboard for daily reviews, per-topic stats, and simple history

## Project layout (high level)

```
src/
  api/          FastAPI app and public API routes
  auth/         Auth routes, schemas, JWT + password utilities
  db/           Async engine, session, and ORM models
  rag/          Retrieval components and indexing
  generation/   Answer generation and citation handling
  orchestrator/ Agentic RAG orchestration
  llm/          LLM client abstractions

eval/           Offline QA generation and evaluation pipeline
scripts/        Helper CLI tools (chunk building, seeding, preprocessing)
tests/          Pytest suite for retrieval, generation, API, auth
docs/           Architecture and evaluation notes
```

## Notes on usage and setup

The codebase already supports:

- Running the RAG API over `data/chunks.jsonl`
- Using Z.AI / GLM (or alternative providers) via `.env`
- Running Alembic migrations against PostgreSQL

Detailed setup, run commands, and examples will be documented separately as the skill tracker APIs and UI solidify. For now, the best references are the tests under `tests/` and the documents in `docs/`.
