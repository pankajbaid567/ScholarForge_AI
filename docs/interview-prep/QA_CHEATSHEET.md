# AI Engineering Interview Cheat Sheet

This document translates the architectural decisions of ScholarForge AI into concise, high-impact answers for Technical Interviews. Use this guide to explicitly demonstrate Senior/Staff-level engineering maturity to recruiters and hiring managers.

## System Architecture & Tradeoffs

### 1. "Why did you use Hybrid Retrieval instead of just a Vector Database?"
> **Answer:** "Dense vectors (Cosine Similarity) are great for capturing semantic meaning, but they fail catastrophically on exact keyword matching, especially for academic acronyms or specific IDs. BM25 (Sparse) is excellent for exact keywords but misses semantic relationships. I implemented a Hybrid Search because relying purely on vectors for an academic dataset drops recall accuracy significantly. Fusing both methods covers all edge cases."

### 2. "How do you combine BM25 and Dense Vector scores?"
> **Answer:** "You can't just add them together because they operate on completely different mathematical scales (BM25 is probabilistic, Cosine is distance). I used **Reciprocal Rank Fusion (RRF)**. RRF ignores the raw scores and merges the chunks based purely on their *rank* in the lists using the formula `1 / (k + rank)`. It's mathematically elegant and highly robust."

### 3. "Why do you need a Cross-Encoder Reranker if Hybrid search is so good?"
> **Answer:** "Hybrid search might return 20 good candidates, but feeding 20 chunks into an LLM causes 'Lost in the Middle' syndrome and wastes massive amounts of tokens. I use a Cross-Encoder (`ms-marco-MiniLM`) to re-score those 20 candidates. Cross-Encoders are slower than Bi-Encoders, but they are vastly more precise because they compute the attention between the query and the document simultaneously. It guarantees the LLM only receives the absolute top 5 chunks."

### 4. "What is Semantic Caching and why did you build it?"
> **Answer:** "Hitting OpenAI costs money and takes ~1.5 seconds. Standard exact-string caching fails if a user adds a single extra space or word to their query. I implemented Semantic Caching using **RedisVL**. We embed the user's query and do a rapid vector search against previously answered queries. If the similarity is > 95%, we bypass the LLM completely and return the cached answer in < 50ms. It's the highest ROI feature in the platform."

### 5. "What is HyDE and how does it help?"
> **Answer:** "Users often type terrible, short queries like 'attention mechanism'. Searching that against long academic paragraphs yields poor vector matches due to length disparity. I built a **HyDE (Hypothetical Document Embeddings)** expander. Before searching, we pass the short query to a fast LLM to write a 'hallucinated' academic paragraph. We then use that rich, hallucinated paragraph to search the database. Recall accuracy skyrockets."

## Production Engineering & Scale

### 6. "Why did you use Celery instead of FastAPI Background Tasks?"
> **Answer:** "FastAPI's `BackgroundTasks` run in the same memory space and event loop as the web server. If 50 users upload massive PDFs simultaneously, the CPU-bound chunking process will block the event loop, and the entire API will start throwing 502 Bad Gateway errors. I decoupled the system using **Celery and Redis**. Ingestion tasks are pushed to a Redis broker, and separate Celery worker containers process them asynchronously. The API stays perfectly responsive."

### 7. "How do you know your RAG system is actually good?"
> **Answer:** "I don't rely on 'vibes'. I implemented the **RAGAS (Retrieval Augmented Generation Assessment)** framework. Every generation is asynchronously evaluated by an LLM-as-a-judge for Faithfulness, Answer Relevance, and Context Recall. I track these metrics in PostgreSQL. I also built a human-in-the-loop Upvote/Downvote API to ensure the automated judge correlates with actual human preference."

### 8. "How do you debug an LLM application?"
> **Answer:** "Standard logs are insufficient for RAG pipelines because a 2-second response is a black box. I instrumented the entire application with **OpenTelemetry** and exported the traces to **Arize Phoenix**. This allows me to visually inspect the waterfall of spans. I can see exactly if the latency bottleneck was the ChromaDB search, the Cross-Encoder, or OpenAI's Time-To-First-Token."

## Database & Tech Stack Decisions

### 9. "Why PostgreSQL and ChromaDB instead of an all-in-one Vector DB like pgvector?"
> **Answer:** "Separation of concerns. PostgreSQL is optimized for ACID-compliant relational data (User Sessions, Conversation History, RAGAS scores). ChromaDB is highly optimized for fast, in-memory HNSW vector search. Decoupling them allows me to scale the relational state independently from the vector compute."

### 10. "Why FastAPI?"
> **Answer:** "FastAPI is natively asynchronous, making it perfect for IO-bound LLM applications. It also provides automatic Pydantic validation and Swagger documentation, which accelerated the development of the REST contracts."
