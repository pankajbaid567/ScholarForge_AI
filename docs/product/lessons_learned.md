# Lessons Learned & Engineering Tradeoffs

Building ScholarForge AI from a theoretical concept into a production-grade RAG platform revealed several critical failure points that are often glossed over in tutorials. This document logs the mistakes made, the architectural pivots, and the unexpected findings discovered during development.

## 1. The Async Event Loop Catastrophe
**The Mistake:** Initially, document ingestion was built using FastAPI's native `BackgroundTasks`. We assumed that because it was running in the background, it wouldn't block the user.
**The Failure:** When we stress-tested the system by uploading 50 large PDFs, the API gateway completely locked up. Chat requests started timing out with 502 errors.
**The Lesson:** FastAPI `BackgroundTasks` still run on the same asyncio event loop as the web server. Heavy CPU-bound tasks (like recursive character splitting and matrix multiplications for embeddings) block the event loop.
**The Pivot:** We entirely ripped out `BackgroundTasks` and migrated to a distributed **Celery + Redis** queue. This correctly decoupled the CPU-heavy tasks to separate worker containers, ensuring the API remained blazingly fast regardless of ingestion load.

## 2. The Vector-Only Delusion
**The Mistake:** Our MVP relied exclusively on ChromaDB and Dense Vector embeddings (Cosine Similarity). 
**The Failure:** During testing with the Golden Dataset, we realized the system was failing spectacularly on specific acronyms. A search for "CRISPR-Cas9" was returning chunks about general gene editing that never mentioned the exact protein.
**The Lesson:** Dense vectors compress meaning into an array of floats. In doing so, they lose the exact string representations. Academic texts are hyper-reliant on exact lexical acronyms.
**The Pivot:** We implemented a Hybrid Retrieval system, fusing dense vectors with the probabilistic exact-match algorithm **BM25**, merging them mathematically via Reciprocal Rank Fusion (RRF). Context Recall jumped from 62% to 79%.

## 3. The "Lost in the Middle" Syndrome
**The Mistake:** To ensure we captured all context, we initially passed the Top 20 retrieved chunks directly into the LLM prompt.
**The Failure:** The system started hallucinating more. We discovered that when LLMs are fed massive context windows (10k+ tokens), they often ignore facts located in the middle of the prompt.
**The Lesson:** More context is not better context. Precision is superior to volume.
**The Pivot:** We introduced a Cross-Encoder Reranker (`ms-marco-MiniLM`). This model re-scores the 20 chunks based on pairwise attention and filters it down to the absolute Top 5 chunks. Token costs plummeted, and Faithfulness jumped to nearly 90%.

## 4. The Cache Hit Threshold Sensitivity
**The Mistake:** When implementing Semantic Caching via `redisvl`, we set the distance threshold to `0.02` (extremely strict).
**The Failure:** The cache hit ratio was essentially 0%. Even a user adding a question mark to the end of a sentence altered the embedding vector enough to cause a cache miss.
**The Lesson:** Semantic distance is highly sensitive.
**The Pivot:** We carefully adjusted the threshold to `0.10`. This was the "Goldilocks" zone—it successfully caught identical conceptual questions (e.g., "Explain attention" vs "What is attention") without accidentally returning cached answers for distinct questions.

## 5. Unexpected Finding: HyDE Hallucinations as a Feature
We initially viewed LLM hallucinations purely as a negative. However, implementing Query Expansion (HyDE) forced us to intentionally ask the LLM to hallucinate a fake document. We discovered that an LLM's latent knowledge, even when "hallucinating", contains the precise academic vocabulary needed to drastically improve vector retrieval density. We learned to harness hallucination as a powerful search tool.
