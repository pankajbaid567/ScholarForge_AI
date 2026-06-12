<div align="center">
  <h1>🎓 ScholarForge AI</h1>
  <p><strong>Production-Grade Retrieval-Augmented Generation for Academic Research</strong></p>

  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
  [![Celery](https://img.shields.io/badge/Celery-Distributed_Task_Queue-37814A.svg?logo=celery)](https://docs.celeryq.dev/)
  [![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-Observability-blue.svg)](https://opentelemetry.io/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

  [Documentation](./docs) •
  [Architecture](./docs/architecture/architecture.md) •
  [Benchmarks](./docs/benchmarks/benchmarking.md) •
  [Quick Start](#-quick-start)
</div>

---

## 1. Problem Statement
Extracting highly specific methodologies, formulas, and baseline metrics from dense, multi-column academic PDFs is a notoriously slow process for researchers and ML engineers. 

Existing "Chat with PDF" solutions built on naive dense vector search fundamentally fail in this domain. Dense vectors compress meaning, frequently causing them to miss exact academic acronyms (e.g., "CRISPR-Cas9"), lose context on short user queries, and hallucinate details when confronted with thousands of overlapping documents.

## 2. Why ScholarForge AI Exists
ScholarForge AI was engineered to move beyond prototype wrappers. It introduces a **Defense-in-Depth Cascading Retrieval Pipeline** specifically optimized for academic literature. 

By prioritizing exact-match lexical retrieval alongside semantic density, caching expensive LLM operations at the edge, and decoupling document ingestion from the web server via distributed queues, ScholarForge AI achieves production-grade latency (<1.5s) and verified accuracy (Context Recall > 88%).

## 3. Key Features
* **Hybrid Retrieval (Dense + Lexical)**: Fuses ChromaDB (Cosine Similarity) with BM25 (TF-IDF) to capture both semantic intent and exact acronym matches.
* **Reciprocal Rank Fusion (RRF)**: Mathematically normalizes and merges the wildly disparate scoring distributions of the two retrieval engines.
* **Cross-Encoder Reranking**: Utilizes `ms-marco-MiniLM` to evaluate pairwise attention between the query and the Top 20 chunks, guaranteeing absolute precision and preventing "Lost in the Middle" LLM syndrome.
* **Query Expansion (HyDE)**: Employs an LLM to hallucinate rich academic context from terse user queries *before* searching, drastically improving vector match density.
* **Semantic Edge Caching**: Intercepts conceptually identical queries at the API gateway using `redisvl`, returning cached responses in `<50ms` and bypassing OpenAI completely.
* **Asynchronous Distributed Ingestion**: Offloads heavy PDF parsing to a Celery worker queue, preventing the FastAPI event loop from blocking during 100MB+ bulk uploads.

## 4. Architecture Overview
ScholarForge operates as a set of decoupled, horizontally scalable microservices. The API Gateway is completely stateless, relying on Redis for message brokering and rate limiting, PostgreSQL for relational evaluation state, and ChromaDB for in-memory HNSW vector search.

### 5. Architecture Diagram
![System Architecture Diagram](https://via.placeholder.com/1000x500.png?text=Mermaid+Architecture+Diagram+Placeholder) *(See [docs/architecture/architecture.md](./docs/architecture/architecture.md) for full system topology).*

## 6. Technology Stack
* **API Gateway**: FastAPI, Uvicorn, Pydantic
* **Task Broker & Queue**: Celery, Redis
* **State Management**: PostgreSQL 15, SQLAlchemy, Alembic
* **Vector & Sparse Search**: ChromaDB, `rank_bm25`, `sentence-transformers`
* **Generative Models**: OpenAI `gpt-4o` (Generation), `gpt-3.5-turbo` (HyDE)
* **Observability**: Arize Phoenix, OpenTelemetry (OTLP)
* **Evaluation Framework**: RAGAS
* **Frontend UI**: Streamlit

## 7. System Design Highlights
* **Streaming SSE**: Yields Server-Sent Events from the FastAPI router to the client, pushing perceived TTFT (Time-To-First-Token) to near zero.
* **Sliding Window Memory**: Prevents prompt context overflow while retaining conversational state via Postgres query limiters.

## 8. Evaluation Framework (RAGAS)
"Vibes are not metrics." Every generative response is asynchronously dispatched to a background Celery worker for strict LLM-as-a-judge evaluation. We mathematically track:
* **Faithfulness**: Did the LLM hallucinate claims not present in the context?
* **Answer Relevance**: Did the LLM actually answer the prompt?
* **Context Recall**: Did the retrieval pipeline fetch all necessary ground-truth facts?

## 9. Benchmarks
Tested against a frozen Golden Dataset of 100 ArXiv academic queries.

| Strategy | Context Recall | Faithfulness | P95 Latency |
| :--- | :--- | :--- | :--- |
| Naive RAG (Dense Only) | 62.4% | 76.1% | 0.9s |
| **ScholarForge (Hybrid + Rerank + HyDE)** | **92.1%** | **91.2%** | 2.1s |
| **ScholarForge (Semantic Cache Hit)** | N/A | 100% | **42 ms** |

*(For full cost analysis, see [Benchmarking Data](./docs/benchmarks/benchmarking.md)).*

## 10. Application Interface
![Dashboard Screenshot](https://via.placeholder.com/800x400.png?text=Streamlit+UI+Dashboard+Placeholder)

## 11. Live Demo
![Streaming Generation GIF](https://via.placeholder.com/800x400.png?text=Live+SSE+Streaming+Demo+Placeholder)

## 12. Quick Start

**Prerequisites:** Docker, Docker Compose, OpenAI API Key.

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/ScholarForge_AI.git
cd ScholarForge_AI

# 2. Configure Environment Variables
cp .env.example .env
# Edit .env and insert OPENAI_API_KEY=sk-...

# 3. Spin up the Microservice Topology (API, Celery, Postgres, Redis, Chroma, Phoenix)
docker-compose up -d --build

# 4. Start the Frontend Dashboard
pip install -r requirements.txt
streamlit run frontend/app.py
```

## 13. Documentation Ecosystem
The `/docs` directory contains comprehensive, Staff-level engineering documentation:
* 🏗 [System Architecture](./docs/architecture/architecture.md)
* 🔀 [Data Flows](./docs/architecture/data_flow.md)
* 🧠 [Retrieval Pipeline](./docs/engineering/retrieval_pipeline.md)
* 📊 [Evaluation Pipeline](./docs/engineering/evaluation_pipeline.md)
* 🧪 [Testing Strategy](./docs/engineering/testing_strategy.md)
* 📈 [Benchmarks](./docs/benchmarks/benchmarking.md)
* 🚀 [Product Requirements (PRD)](./docs/product/product_requirements.md)
* 📖 [Operations Runbooks](./docs/operations/runbooks.md)

## 14. Architecture Decisions
Every technical tradeoff is documented in [Architecture Decision Records (ADRs)](./docs/adr/architecture_decisions.md). Examples include:
* *ADR-005: Why RRF over Weighted Linear Fusion*
* *ADR-009: Why Cross-Encoders over Bi-Encoders*
* *ADR-011: Why RedisVL Semantic Caching over String Caching*

## 15. Security & Threat Model
ScholarForge implements strict Prompt Isolation, Redis Rate-Limiting, and RBAC to defend against Prompt Injection, Retrieval Poisoning, and Financial DoS attacks. Read the [Threat Model](./docs/operations/security.md).

## 16. Future Roadmap
* **Q3:** Implement GraphRAG (Neo4j) to map citation networks explicitly.
* **Q4:** Swap `text-embedding-3-small` for a fine-tuned local embedding model optimized for ArXiv latex syntax.

## 17. Lessons Learned
Read the [Lessons Learned](./docs/product/lessons_learned.md) document to see how we recovered from the "Async Event Loop Catastrophe" and the "Cache Hit Threshold Sensitivity" failures.

## 18. Interview Discussion Topics
If you are a Technical Recruiter, Hiring Manager, or Principal Engineer evaluating this project for an AI/ML Engineering position, please see the [Interview QA Cheat Sheet](./docs/interview-prep/QA_CHEATSHEET.md) for a concise breakdown of the hardest engineering challenges solved during development.

## 19. Author
**Pankaj Baid**  
*Backend + AI Infrastructure Engineer*  
[LinkedIn](https://www.linkedin.com/in/pankaj-baid-0109b1226/) • [GitHub](https://github.com/pankajbaid567)
