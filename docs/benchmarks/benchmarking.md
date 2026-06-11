# System Benchmarks & Performance Metrics

## 1. Benchmark Methodology
Production AI systems require quantitative proof of quality. "Vibes" and anecdotal testing are insufficient for enterprise deployments. ScholarForge AI uses the **RAGAS (Retrieval Augmented Generation Assessment)** framework to mathematically evaluate system permutations against a Golden Dataset.

### 1.1 The Golden Dataset
*   **Source:** 100 heavily vetted academic questions derived from a corpus of 50 ArXiv machine learning papers.
*   **Structure:** Each record contains `(question, ground_truth_answer, source_context)`.

### 1.2 Hardware Environment
*   **Compute:** Apple Silicon (M-Series) / AWS t3.xlarge equivalent.
*   **LLM API:** OpenAI `gpt-4o` (for generation) and `gpt-3.5-turbo` (for HyDE).
*   **Embeddings:** `text-embedding-3-small`.

## 2. Retrieval Quality Benchmarks

We tested four different retrieval architectures against the Golden Dataset to justify the final system design. 

*(Metrics generated via automated RAGAS LLM-as-a-judge pipelines).*

| Experiment Strategy | Context Recall | Faithfulness | Answer Relevance | Latency (P95) |
| :--- | :--- | :--- | :--- | :--- |
| **Naive RAG (Dense Only)** | 62.4% | 76.1% | 71.3% | 0.9s |
| **BM25 Only (Lexical)** | 58.1% | 65.2% | 68.9% | **0.8s** |
| **Hybrid (Dense + BM25)** | 79.5% | 85.3% | 82.1% | 1.1s |
| **Hybrid + Cross-Encoder**| **88.2%** | **89.7%** | **88.4%** | 1.4s |
| **Hybrid + Rerank + HyDE**| **92.1%** | **91.2%** | **90.5%** | 2.1s |

### 2.1 Analysis of Results
1.  **The Failure of Naive RAG:** Dense-only retrieval struggled severely with acronyms (e.g., "RNN", "CNN"). BM25 captured these acronyms perfectly but failed on conceptual questions.
2.  **The Hybrid Jump:** Fusing Dense and Lexical via RRF provided the most massive leap in quality (+17% Recall), proving that neither strategy is sufficient alone.
3.  **The Reranker Tax:** Adding the `ms-marco-MiniLM` Cross-Encoder pushed Faithfulness to ~90%, but added ~300ms of latency.
4.  **The HyDE Tradeoff:** Query Expansion achieved the highest possible scores, but the extra LLM call pushed P95 latency to 2.1s.

## 3. Latency & Caching Benchmarks

To combat the 1.4s - 2.1s latency introduced by the advanced retrieval pipeline, we introduced **Semantic Caching via RedisVL**.

We simulated 1,000 queries where 30% of the queries were semantically similar (e.g., "Explain Transformers" vs "How do Transformers work?") to previously asked questions.

| Metric | Without Semantic Cache | With Semantic Cache | Improvement |
| :--- | :--- | :--- | :--- |
| **Average Latency** | 1,450 ms | 1,020 ms | 30% Faster |
| **Cache Hit Latency**| N/A | **42 ms** | **97% Faster** |
| **Token Cost / 1k Queries**| ~$15.00 | ~$10.50 | 30% Cheaper |

### 3.1 Observability Spans (Arize Phoenix)
Trace analysis reveals the exact latency breakdown of a standard Cache Miss:
1.  **FastAPI Overhead:** 15ms
2.  **Query Expansion (HyDE):** 600ms
3.  **BM25 + Chroma Search:** 85ms
4.  **Cross-Encoder Reranking:** 280ms
5.  **OpenAI Generation (TTFT):** 450ms

## 4. Ingestion Throughput (Celery Queue)
Initial designs used FastAPI `BackgroundTasks` for PDF ingestion. During stress testing (uploading 100 MB of PDFs simultaneously), the web server event loop blocked, causing HTTP 502 Bad Gateway errors for chat users.

By migrating to **Redis + Celery**:
*   **API Response Time (during ingestion):** Remained stable at < 50ms (Returning `202 Accepted`).
*   **Worker Throughput:** Processed ~45 pages per second per Celery worker.
*   **System Reliability:** 0% dropped requests during max load.

## 5. Lessons Learned & Production Takeaways
1.  **Throwing vectors at a DB is not a product.** Reaching 90%+ faithfulness requires cascading defensive architectures.
2.  **Rerankers are mandatory** for academic contexts to filter out edge-case vector collisions.
3.  **Semantic Caching is the highest ROI feature** in the entire platform. The ability to bypass the LLM entirely drops latency to 40ms and saves massive amounts of capital at scale.
