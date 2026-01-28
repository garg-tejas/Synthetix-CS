## Skill Decay Tracker – OS / DBMS / CN

This repo is an **eval‑first playground** for building a Skill Decay Tracker aimed at placement prep in **Operating Systems, Databases, and Computer Networks**. The end goal is an app that:

- quizzes you at **spaced intervals**
- tracks **what’s fading from memory**
- points you back to the **right textbook evidence**

Before we build the product, we want a **clean, testable retrieval + reasoning stack** that we trust.

---

## High‑Level Idea

We have 9 classic textbooks (OS / DBMS / CN). From them we build:

- a **chunked, metadata‑rich corpus**
- a **hybrid retriever** (BM25 + dense + reranker + heuristics)
- an **eval harness** with canonical queries (e.g. page replacement, B\+‑tree ops, TCP handshake, ACID)

Then we compare:

- **RAG‑only** setups (different retrieval configs)
- **SLM‑only** (fine‑tuned small models)
- **Hybrid** (retrieval + small reasoning models)

The winner becomes the backbone for the Skill Decay Tracker (KB → Question Bank → SRS engine → App).

---

## Phases

Think of the project in three layers:

1. **Eval‑first infra (now)**
2. **Reasoning models (later)**
3. **Product (later‑later)**

Only the **current phase** is described in detail; later phases stay high‑level until we get there.

---

## Phase 0 – Retrieval & Eval (current phase)

Goal: have a **measured, inspectable retrieval pipeline** over the textbooks, with enough evaluation to see when we improve or regress.

### 0.1 Content preparation

- Clean raw `.mmd` textbook exports (see `eval/preprocess`):
  - drop junk / formatting paragraphs
  - sentence‑level dedup
  - strip figure‑only and table‑only lines
- **Structural chunking** (see `eval/chunking`):
  - split by headings (`## / ### / ####`) to keep semantic sections together
  - tag chunks with `chunk_type` (definition, algorithm, section, example, protocol, exercise, references, …)
  - keep `header_path` (breadcrumb within the book)
- Extract light **metadata**:
  - `key_terms` via simple TF‑IDF‑style tokenization and stopwords
  - book‑level IDs
- Final output: `eval/dataset/chunks.jsonl` (~6.5k chunks across the 9 books).

You should be able to treat `ChunkRecord` (in `eval/rag/index.py`) as the canonical in‑memory view.

### 0.2 Retrieval stack

The retrieval stack currently looks like this:

- **BM25 retriever** – `eval/rag/bm25_retriever.py`
  - lexical search over `chunk.text`
  - good at catching exact terminology and rare tokens

- **Dense retriever** – `eval/rag/dense_retriever.py`
  - `all-MiniLM-L6-v2` via `sentence-transformers`
  - vector index over `chunk.text`
  - good at looser paraphrases (“how does virtual memory work” → “virtual memory abstracts …”)

- **Hybrid merge (RRF)** – `eval/rag/rrf_merger.py`
  - takes BM25 + dense ranked lists of IDs
  - combines them via **Reciprocal Rank Fusion** so either channel can surface candidates

- **Query understanding** – `eval/rag/query_understanding.py`
  - lightweight intent detection:
    - **definition‑seeking**: “what is X”, “define X”, “meaning of X…”
    - **procedural**: “how to…”, “how does X work”, “explain how…”
    - **comparative**: “compare X and Y”, “X vs Y”, “difference between X and Y”
  - concept extraction (`concept="tcp 3 way handshake"`, `concept="b+ tree"`, …)
  - **negative signals**:
    - e.g. TCP handshake queries → down‑weight TLS record/auth protocol chunks
    - B\+‑tree queries → down‑weight R‑tree / generalized search tree riffs
    - virtual memory queries → down‑weight pure “virtual machines” detours

- **Hybrid searcher + reranker** – `eval/rag/search_cli.py`, `eval/rag/reranker.py`
  - `HybridSearcher.search(query, top_k)`:
    1. Runs BM25 + dense with a **larger candidate pool**.
    2. Merges via RRF.
    3. Filters obvious noise by type/header:
       - drops `exercise`, `references`, `bibliography`, `citations`
       - drops headers with “Appendix”, “Selected Bibliography”, “Further Reading”, “Exercises”, “Review Questions”
       - uses query‑level `negative_signals` to remove confuser chunks (e.g. TLS when query is about TCP handshake).
    4. Applies simple **score shaping**:
       - boost definition chunks when the query is definition‑seeking and the chunk actually looks like it’s about the concept
       - soft boosts for:
         - **procedural** queries → favour `algorithm` / strong `section` chunks
         - **comparative** queries → favour `protocol` / `comparison` / strong `section` chunks
       - penalty for chunks that explicitly **negate** the concept (e.g. “non‑deadlock”)
    5. Sends the resulting candidate list through a **cross‑encoder reranker**:
       - `cross-encoder/ms-marco-MiniLM-L-6-v2`
       - re‑scores `(query, header + leading text)` pairs and returns the final top‑k.

The intended usage surface for now is:

- quick CLI: `uv run python -m eval.rag.search_cli "your question"`
- programmatic: build `HybridSearcher` and call `.search(...)`.

### 0.3 Neighbouring‑chunk / parent‑section context

Retrieval alone often hits the _right local area_ but the _wrong atom_:

- ACID: we retrieve “What are the ACID properties?” (review question) but the actual definitions are in adjacent chunks.
- B\+‑trees: we may land on “Complexity of B\+‑tree updates” while the detailed insertion steps live just before/after.

To address that we have:

- `eval/rag/context_window.py`:
  - `build_book_index(chunks)` → per‑book, ordered lists of chunks.
  - `expand_with_neighbors(results, by_book, window=1)` → for each hit, also pull in its ±`window` neighbours.

This is meant for the **answer‑construction layer**:

- retrieval/reranking picks the _anchor_ chunks;
- `expand_with_neighbors` provides a slightly wider **section‑level context** that you hand to the model or to the evaluator.

We haven’t yet wired this into a full RAG generation loop, but the building blocks are in place.

### 0.4 Evaluation harness (for retrieval only)

We have a small, opinionated eval layer under `eval/evaluate/`:

- `test_queries.py`:
  - defines a handful of canonical OS/DBMS/CN questions:
    - page replacement algorithms
    - TCP 3‑way handshake
    - B\+‑tree insertion/deletion
    - deadlocks
    - compare TCP vs UDP
    - process scheduling algorithms
    - ACID properties
    - virtual memory
  - for each query we annotate:
    - expected **chunk types** to see (`definition`, `section`, `algorithm`, `protocol`, …)
    - patterns that should **never** appear (e.g. TLS for TCP handshake queries)
    - minimal expectations like “at least one `algorithm` chunk in the top‑k”.

- `run_evaluation.py`:
  - builds the **full hybrid + reranker** stack.
  - for each test query:
    - prints the top‑k with type, header, short text snippet
    - checks:
      - **Noise@k**: how many results match `negative_patterns` → PASS / FAIL
      - **RequiredTypes@k**: how many hits have the required chunk types → PASS / FAIL

This is intentionally simple and human‑inspectable: it’s there to catch obvious regressions (e.g. TLS chunks creeping back into TCP handshake, references/appendices showing up for “page replacement algos”).

---

## Phase 1 – Reasoning Models (high‑level, future)

Once we’re happy with retrieval, we’ll add **small reasoning models** on top:

- Try base vs fine‑tuned **SLMs** for:
  - answering textbook‑aligned questions with **citations** into retrieved chunks,
  - gently “stepping through” definitions and algorithm steps.
- Evaluate:
  - accuracy against our question set,
  - how often cited evidence actually supports the answer,
  - latency and cost vs a pure RAG setup.

At the end of this phase we want a clear picture: “RAG only vs SLM only vs hybrid – which is better for this domain and our constraints?”

Details of architectures and training loops will be added when we’re ready to start this phase.

---

## Phase 2 – Product (high‑level, future)

With a solid retrieval + reasoning backbone, we’ll layer on the actual **Skill Decay Tracker**:

- **Knowledge base pipeline**
  - persist the chosen chunking/embedding/retrieval stack in a production‑friendly way (indices, caches, etc.)
- **Question bank + SRS**
  - a curated question set per topic, linked back to supporting chunks,
  - an SRS engine (likely FSRS / SM‑2‑style) that schedules reviews based on performance.
- **App**
  - a simple UI (CLI or web) to:
    - run quizzes,
    - surface textbook evidence,
    - visualise “what’s decaying” over time.

Those parts are deliberately only sketched out for now; we’ll refine and document them once the retrieval & eval layer is fully locked in.
