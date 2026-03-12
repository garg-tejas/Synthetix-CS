# CoreCS Interview Lab

CoreCS Interview Lab is a full-stack CS interview prep system for OS, DBMS, and Computer Networks.
It combines a hybrid RAG assistant with an adaptive quiz engine, so you can both ask conceptual questions and practice recall on a spaced schedule.

## Problem and Solution

### Problem

Most interview prep workflows break into disconnected pieces:

- static notes with no retrieval support,
- random question lists with no memory model,
- and no signal-driven way to decide what to study next.

That creates two practical issues:

1. You can read a lot without closing knowledge gaps in weak topics.
2. You can answer questions once, but still forget them because review timing is not adaptive.

### Solution

CoreCS Interview Lab unifies retrieval, evaluation, and revision:

- textbook chunks are indexed for retrieval-backed Q&A,
- chunks are converted into interview-style cards,
- answers are graded to a 0-5 quality signal,
- SM-2 spaced repetition schedules next review,
- and a prerequisite-aware learning path orders what to tackle first.

Result: one system for understanding concepts, practicing recall, and prioritizing topics that are both weak and structurally important.

## Key Features

**Retrieval (RAG)**

- Hybrid search: BM25 + dense retrieval + RRF fusion with optional cross-encoder reranking
- Citation-backed answers: Generated responses include `[n]` citations mapped to source chunks, with citation validation and grounding checks
- Query enhancement: Rewriting, subject-aware HYDE expansion, and follow-up query reformulation for multi-turn conversations

**Adaptive Quizzing**

- Session startup: Prioritizes due cards, fills with new cards, optional topic/subject scoping, difficulty filter (easy/medium/hard)
- LLM grading: Each answer gets a 0-5 quality score, concept summary, and targeted feedback (type-aware rubrics)
- SM-2 spaced repetition: Review scheduling with proportional interval reset on lapse and ease factor tracking
- "Don't know" button: Failed recall without LLM grading (SM-2 quality=0, shows reference answer)
- Skip button: Advance to next card without recording an attempt or changing SRS state

**Learning Path**

- Prerequisite-aware ordering: Topics unlock based on completed dependencies
- Mastery + SWOT modeling: Per-topic signals drive priority (weakness/threat/opportunity/strength), configurable via `SWOTConfig`
- Runtime card variants: Quality-gated generation ensures only interview-worthy variants are persisted

**Infrastructure**

- End-to-end persistence: Auth, cards, attempts, review states, mastery, SWOT, taxonomy, and prerequisites in PostgreSQL
- Offline generation pipeline: Question generation, scoring, validation, and seeding

## Technical Highlights

### 1) Hybrid Retrieval Internals

- Sparse retrieval: `rank_bm25` over tokenized chunk text.
- Dense retrieval: `sentence-transformers` embeddings (`all-MiniLM-L6-v2` by default).
- Fusion: Reciprocal Rank Fusion (`1 / (k_rrf + rank)`, default `k_rrf=60`).
- Candidate depth: `candidate_k=max(top_k*3, config.candidate_k)` (default `top_k=5`, `candidate_k=20`).
- Intent-aware scoring:
  - definition chunks get a boost (`x1.5`) for definition-seeking queries,
  - negating chunks can be penalized (`x0.25`),
  - procedural/comparative intents apply smaller type-aware boosts.
- Noise filtering: reference/exercise/bibliography style chunks are removed before final ranking.
- Optional second-stage reranking: cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) with blended score.

### 2) Spaced Repetition Algorithm (SM-2)

- Input signal: LLM grader outputs a `quality` score in `[0, 5]`.
- Failure path (`quality < 3`):
  - repetitions reset to `0`,
  - interval proportionally reset: `max(1, min(interval // 2, 7))` (e.g., interval 6 -> 3, interval 30 -> 7),
  - lapses increment.
- Success path (`quality >= 3`):
  - ease factor updated with classic SM-2 delta formula,
  - floor enforced at `min_ease_factor=1.3`,
  - interval progression: `1`, `6`, then `round(interval * EF)`.
- State update writes `due_at`, `last_reviewed_at`, `interval_days`, `repetitions`, `ease_factor`, and `lapses`.

### 3) Learning Path Logic

- Inputs:
  - `UserTopicMastery`,
  - `UserTopicSWOT`,
  - `TopicTaxonomyNode`,
  - `TopicPrerequisite`.
- Priority scoring:
  - `deficit = max(0, 100 - mastery_score)`
  - bucket bonus: weakness `+28`, threat `+22`, opportunity `+14`, strength `+4`
  - `priority = deficit + bucket_bonus`
- Ordering method:
  - prerequisite-aware topological ordering,
  - ties broken by higher priority,
  - cycle fallback appends remaining nodes by priority.
- Session serving integrates path order by ranking selected cards with `topic_key -> path_rank`.

### 4) Topic Graph Construction Pipeline

- LLM-assisted two-pass graph build:
  1. candidate extraction (topics + edges),
  2. edge validation (keep/drop + confidence).
- Rule filtering removes self-loops, missing-topic edges, duplicates, and low confidence edges.
- Cycle breaking drops the lowest-confidence edge in detected cycles.
- Outputs are synced to DB via `scripts.sync_topic_dependency_graph`.

## Tech Stack

**Retrieval and LLM**

- `rank-bm25` (sparse search)
- `sentence-transformers` (dense embeddings + cross-encoder reranking)
- OpenAI-compatible client layer (Z.AI/GLM, ModelScope)

**Backend**

- Python 3.12, FastAPI, Uvicorn
- SQLAlchemy (async) + AsyncPG
- Alembic migrations, Pydantic v2

**Data and Storage**

- PostgreSQL (users, cards, review state, attempts, mastery, SWOT, taxonomy, prerequisites)
- JSONL corpora and artifacts

**Frontend**

- React 18 + TypeScript, Vite, React Router

**Tooling**

- `uv` for dependency management
- Pytest test suite

## Project Structure

```text
src/       API, auth, DB models, RAG, orchestrator, quiz/session logic
eval/      Question generation, scoring, validation
scripts/  Chunking, seeding, graph build/sync checks
frontend/  React SPA (dashboard, setup, path preview, review flow)
docs/      Architecture and setup guides
tests/     Backend test suite
```

## Quick Start

Typical flow:

1. Configure `.env` (Postgres, OpenAI-compatible API key, JWT secret)
2. Run migrations: `uv run alembic upgrade head`
3. Generate questions: `uv run python -m eval.generation.batch_generate --subject os`
4. Seed cards: `uv run python -m scripts.seed_cards --input <validated_jsonl> --apply`
5. Sync topic graph: `uv run python -m scripts.sync_topic_dependency_graph --subject os --replace-subject`
6. Start backend: `uv run uvicorn src.api.main:app --reload`
7. Start frontend: `cd frontend && pnpm dev`

See `docs/SETUP.md` for detailed instructions.

## What I Learned

- Hybrid retrieval quality depends less on any one retriever and more on careful fusion, filtering, and reranking.
- Query intent signals (definition/procedural/comparative) are simple to add but have outsized ranking impact.
- LLM outputs in pipelines need strict parsing, fallback behavior, and schema guards to stay production-usable — early grading attempts failed 12% of the time from malformed JSON; adding retry logic + schema validation brought failures under 1%.
- Spaced repetition becomes much more useful when paired with explanation-level feedback instead of raw correctness only.
- Learning paths are stronger when they combine graph constraints (prerequisites) with personalized signals (mastery + SWOT).
- Persisting detailed review telemetry (quality, lapses, due pressure, trends) enables better prioritization over time.

## Status

This project is functional end-to-end for:

- auth,
- retrieval-backed chat/search,
- session-based quiz review,
- spaced repetition state updates,
- learning path preview/order,
- and offline content generation + validation pipelines.

## Limitations

- Currently supports OS, DBMS, and Computer Networks only (no algorithms, systems design, or ML topics)
- LLM grading can be inconsistent on edge cases (very short or off-topic answers)
- Learning path assumes linear prerequisite chains; doesn't handle circular concept dependencies well
- Single-user focus (no multi-user collaboration or shared study paths)
