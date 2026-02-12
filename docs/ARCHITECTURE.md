# Architecture

This document describes the CoreCS Interview Lab architecture: how the frontend, API, database, RAG pipeline, and quiz system fit together.

## Overview

The app has three main subsystems:

1. **RAG API** — Hybrid retrieval (BM25 + dense embeddings) with citation-backed chat and search
2. **Quiz system** — Spaced repetition sessions, LLM grading, learning path ordering
3. **Offline pipeline** — Generate questions from chunks, score and validate, seed into the database

All of this sits behind a FastAPI backend and a React SPA frontend.

## System Architecture

```mermaid
flowchart TB
    subgraph Frontend [Frontend SPA]
        Landing[LandingPage]
        Dashboard[DashboardPage]
        Setup[ReviewSetupPage]
        Path[LearningPathPage]
        Review[ReviewPage]
        Summary[ReviewSummaryPage]
        Auth[LoginPage SignupPage]
    end

    subgraph API [FastAPI Backend]
        AuthRoutes[auth routes]
        RAGRoutes[RAG routes]
        QuizRoutes[quiz routes]
        Agent[RAGAgent]
        SessionService[QuizSessionService]
        PathPlanner[LearningPathPlanner]
    end

    subgraph Data [Data Layer]
        Postgres[(PostgreSQL)]
        Chunks[(chunks.jsonl)]
        Embeddings[(embeddings_cache)]
    end

    Frontend --> AuthRoutes
    Frontend --> RAGRoutes
    Frontend --> QuizRoutes
    AuthRoutes --> Postgres
    RAGRoutes --> Agent
    QuizRoutes --> SessionService
    SessionService --> PathPlanner
    SessionService --> Postgres
    PathPlanner --> Postgres
    Agent --> Chunks
    Agent --> Embeddings
```

## Quiz Session Flow

When a user starts a review session, the frontend sends topics (and optionally an ordered list of topic keys from the learning path). The backend loads cards, fetches review states, builds a path order, sorts cards by that order, and serves them one at a time. Each answer is graded by the LLM and the scheduler updates the review state.

```mermaid
sequenceDiagram
    participant User
    participant ReviewPage
    participant QuizAPI
    participant SessionService
    participant PathPlanner
    participant QuizService
    participant Grader
    participant DB

    User->>ReviewPage: Start session from path
    ReviewPage->>QuizAPI: POST /sessions/start with path_topics_ordered
    QuizAPI->>SessionService: start_session
    SessionService->>DB: Load cards, review states
    SessionService->>PathPlanner: build_path
    PathPlanner->>DB: UserTopicMastery, UserTopicSWOT, Taxonomy, Prereqs
    PathPlanner-->>SessionService: ordered path nodes
    SessionService->>QuizService: get_next_cards
    QuizService-->>SessionService: due cards
    SessionService->>SessionService: Sort by path_rank
    SessionService-->>QuizAPI: QuizSessionState
    QuizAPI-->>ReviewPage: session_id, current_card, path

    User->>ReviewPage: Submit answer
    ReviewPage->>QuizAPI: POST /sessions/id/answer
    QuizAPI->>SessionService: answer_card
    SessionService->>Grader: grade_answer
    Grader-->>SessionService: GradeResult
    SessionService->>DB: Update ReviewState, create ReviewAttempt
    SessionService-->>QuizAPI: next_card, feedback
    QuizAPI-->>ReviewPage: answer, verdict, next_card
```

## RAG Pipeline

The RAG system uses hybrid retrieval: BM25 for lexical search, dense embeddings for semantic search, and RRF (Reciprocal Rank Fusion) to merge results. Optional components include a cross-encoder reranker, query rewriting, and HYDE (hypothetical document embeddings). The orchestrator agent decides whether retrieval is needed and runs single-hop or multi-hop retrieval before generating the answer.

```mermaid
flowchart LR
    subgraph Input
        Query[User Query]
    end

    subgraph Agent [RAG Agent]
        Analyzer[QueryAnalyzer]
        Retriever[HybridSearcher]
        Generator[AnswerGenerator]
    end

    subgraph Hybrid [Hybrid Searcher]
        BM25[BM25 Index]
        Dense[Dense Index]
        RRF[RRF Merge]
        Reranker[CrossEncoder Reranker]
    end

    Query --> Analyzer
    Analyzer -->|needs retrieval| Retriever
    Retriever --> BM25
    Retriever --> Dense
    BM25 --> RRF
    Dense --> RRF
    RRF --> Reranker
    Reranker --> Generator
    Generator --> Answer[Answer with Citations]
```

## Data Model

Core entities for the quiz system: users, topics, cards, review states, and review attempts. The learning path depends on taxonomy, prerequisites, per-user mastery, and per-user SWOT scores.

```mermaid
erDiagram
    User ||--o{ ReviewState : has
    User ||--o{ ReviewAttempt : has
    User ||--o{ UserTopicMastery : has
    User ||--o{ UserTopicSWOT : has

    Topic ||--o{ Card : has
    Card ||--o{ ReviewState : has
    Card ||--o{ ReviewAttempt : "answered"
    Card ||--o{ ReviewAttempt : "served_as"

    TopicTaxonomyNode ||--o{ TopicPrerequisite : "prereq_for"
    TopicPrerequisite }o--|| TopicTaxonomyNode : "prereq_of"

    User {
        int id PK
        string email
        string username
    }

    Topic {
        int id PK
        string name
    }

    Card {
        int id PK
        int topic_id FK
        string question
        string answer
        string topic_key
    }

    ReviewState {
        int id PK
        int user_id FK
        int card_id FK
        int interval_days
        datetime due_at
    }

    UserTopicMastery {
        int user_id FK
        string subject
        string topic_key
        float mastery_score
    }

    UserTopicSWOT {
        int user_id FK
        string subject
        string topic_key
        string primary_bucket
    }
```

## Frontend Routes

The app uses React Router with nested routes. Protected routes (dashboard, review flow) require authentication. The review flow is: setup (pick topics/limit) -> learning path (optional, shows node graph) -> review (answer questions) -> summary.

```mermaid
flowchart TD
    Root
    Landing[LandingPage]

    Protected[ProtectedRoute]
    Dashboard[DashboardPage]
    Setup[ReviewSetupPage]
    Path[LearningPathPage]
    Review[ReviewPage]
    Summary[ReviewSummaryPage]

    Auth[Auth Shell]
    Login[LoginPage]
    Signup[SignupPage]

    Root --> Landing
    Root --> Protected
    Root --> Auth

    Protected --> Dashboard
    Protected --> Setup
    Protected --> Path
    Protected --> Review
    Protected --> Summary

    Auth --> Login
    Auth --> Signup

    Setup -->|navigate| Path
    Path -->|click node| Review
    Review -->|finish| Summary
```

## Offline QA Pipeline

Cards are not written by hand. The pipeline generates candidate questions from chunks, scores them with an LLM, validates format and quality, and seeds the database. The topic dependency graph (taxonomy and prerequisites) is built and synced separately.

```mermaid
flowchart LR
    subgraph Input
        Chunks[chunks.jsonl]
        Taxonomy[topic_graph JSON]
    end

    subgraph Eval [eval.generation]
        Generate[batch_generate]
        Score[score_questions]
        Validate[validate_qa]
    end

    subgraph Scripts
        BuildGraph[build_topic_dependency_graph]
        SyncGraph[sync_topic_dependency_graph]
        Seed[seed_cards]
    end

    subgraph Output
        DB[(PostgreSQL)]
    end

    Chunks --> Generate
    Generate --> Score
    Score --> Validate
    Validate --> Seed
    Seed --> DB

    Taxonomy --> BuildGraph
    BuildGraph --> SyncGraph
    SyncGraph --> DB
```

## Key Directories

| Path                | Purpose                                             |
| ------------------- | --------------------------------------------------- |
| `src/api/`          | FastAPI app, routes, CORS, lifespan                 |
| `src/auth/`         | JWT auth, signup, login, session                    |
| `src/db/`           | SQLAlchemy models, async session                    |
| `src/rag/`          | BM25, dense index, hybrid search, reranker          |
| `src/orchestrator/` | RAG agent, query analysis, answer generation        |
| `src/skills/`       | Quiz session, path planner, grader, scheduler, SWOT |
| `src/generation/`   | Answer generation, context building, citations      |
| `eval/generation/`  | Offline QA generation, scoring, validation          |
| `scripts/`          | Chunking, graph building, seeding                   |
| `frontend/src/`     | React app, routes, API client, UI components        |
