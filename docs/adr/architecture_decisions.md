# Architecture Decision Records (ADRs)

This document tracks the foundational technology choices made for ScholarForge AI. It acts as a historical record of *why* certain frameworks were chosen over alternatives.

## Core Backend & Infrastructure
*   **ADR-001 Why FastAPI**: Chose over Flask/Django. FastAPI is async-native, handling highly concurrent IO-bound LLM streams efficiently without worker thread exhaustion.
*   **ADR-002 Why PostgreSQL**: Chose over MongoDB. Evaluation tracking and conversational session state require strict ACID compliance and relational integrity.
*   **ADR-003 Why Celery & Redis Queue**: Chose over FastAPI `BackgroundTasks`. Required a decoupled, persistent worker queue to prevent the main API event loop from crashing during bulk PDF uploads.
*   **ADR-004 Why Docker Compose**: Chose over raw shell scripts. Guarantees deterministic, reproducible environments across Mac/Linux and provides an instant one-click spin-up for recruiters evaluating the project.

## Retrieval Engine
*   **ADR-005 Why ChromaDB**: Chose over Pinecone/Milvus for MVP. It runs locally without requiring external cloud credentials or SaaS latency, but exposes an API easily migratable to managed Chroma later.
*   **ADR-006 Why BM25**: Chose over dense-only retrieval. Essential for capturing exact keyword matches, academic acronyms, and specific document IDs where cosine similarity fails.
*   **ADR-007 Why Hybrid Retrieval (Dense + Sparse)**: Chose over single-mode search. Maximizes recall by covering both semantic intent and lexical precision.
*   **ADR-008 Why RRF (Reciprocal Rank Fusion)**: Chose over weighted linear combination. RRF mathematically normalizes the wildly different score distributions of TF-IDF and Cosine algorithms.
*   **ADR-009 Why Cross-Encoder Reranking (`ms-marco-MiniLM`)**: Chose over Bi-Encoders. Bi-Encoders compress meaning too aggressively. Cross-Encoders are slower but vastly more accurate for absolute Top-5 precision.
*   **ADR-010 Why HyDE (Hypothetical Document Embeddings)**: Chose over standard querying. Dramatically improves recall for short queries by leveraging LLM latent knowledge to "hallucinate" rich context before searching.
*   **ADR-011 Why Semantic Caching (RedisVL)**: Chose over standard exact-match Redis strings. Prevents redundant OpenAI API calls and latency for queries that are conceptually identical but phrased slightly differently.

## Data Processing
*   **ADR-012 Why PyMuPDF**: Chose over PyPDF2. Significantly faster parsing speed and better handling of academic multi-column layouts.
*   **ADR-013 Why RecursiveCharacterTextSplitter**: Chose over naive character splitting. Attempts to keep paragraphs and sentences intact, preserving semantic boundaries for the embedding model.
*   **ADR-014 Why Hash Deduplication (SHA-256)**: Implemented on file upload. Prevents duplicate PDFs from polluting the vector space and degrading retrieval accuracy.

## Evaluation & Observability
*   **ADR-015 Why RAGAS**: Chose over custom heuristic evaluation. RAGAS is the industry standard LLM-as-a-judge framework, providing standardized Faithfulness and Relevance metrics.
*   **ADR-016 Why Human-in-the-Loop**: Added Upvote/Downvote APIs. RAGAS is imperfect; capturing true human preference acts as the ultimate ground truth.
*   **ADR-017 Why Arize Phoenix**: Chose over LangSmith. Phoenix is open-source and runs completely locally via a Docker container, avoiding SaaS lock-in and pricing tiers.
*   **ADR-018 Why OpenTelemetry**: Chose over custom logging wrappers. Vendor-neutral tracing standard that allows dropping Phoenix for Datadog or New Relic in the future with zero code changes.

## AI / LLM Interaction
*   **ADR-019 Why OpenAI `gpt-4o`**: Chose over local LLaMa 3 for generation. Maximum reasoning capability and speed for the RAG generation phase.
*   **ADR-020 Why OpenAI `gpt-3.5-turbo` for HyDE**: Chose over `gpt-4o`. Query expansion requires high speed and low cost; deep reasoning is unnecessary for hallucinating keywords.
*   **ADR-021 Why `text-embedding-3-small`**: Chose over `text-embedding-ada-002`. Higher MTEB benchmark scores and cheaper cost-per-token.
*   **ADR-022 Why Server-Sent Events (SSE)**: Chose over WebSockets. Simpler to implement over standard HTTP/1.1 for unidirectional streaming of LLM tokens to the client.
*   **ADR-023 Why Sliding Window Memory**: Chose over full conversation injection. Prevents context overflow and reduces token costs by only passing the last N messages to the LLM.

## Coding Standards & Libraries
*   **ADR-024 Why Pydantic Settings**: Chose over `os.environ`. Type-safe environment variable management that fails fast at boot if critical keys (like `OPENAI_API_KEY`) are missing.
*   **ADR-025 Why SQLAlchemy ORM**: Chose over raw SQL. Database agnostic, allowing easy transition from SQLite to Postgres, and mitigates SQL injection risks.
*   **ADR-026 Why Alembic**: Chose for schema migrations. Ensures production database upgrades are tracked in version control alongside the ORM models.
*   **ADR-027 Why Streamlit**: Chose over React/Next.js for the MVP frontend. Fastest time-to-value for demonstrating python backends and rendering pandas dataframes visually.
*   **ADR-028 Why UUIDs for Primary Keys**: Chose over auto-incrementing Integers. Prevents ID enumeration attacks and avoids ID collisions in distributed sharding scenarios.
*   **ADR-029 Why Dependency Injection (`Depends`)**: Chose over global state. Makes unit testing FastAPI routes trivial and manages singleton instances of heavy models safely.
*   **ADR-030 Why AsyncOpenAI**: Chose over synchronous `openai` client. Native integration with FastAPI's event loop, maximizing concurrent HTTP connections without blocking.
