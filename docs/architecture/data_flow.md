# System Data Flows

This document maps the exact flow of data through the microservice topology during critical system operations.

## 1. Document Ingestion Flow

This flow illustrates how massive PDF workloads are handled asynchronously to prevent blocking the web server.

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant Redis as Redis Broker
    participant Celery as Worker Node
    participant DB as PostgreSQL
    participant Vector as ChromaDB
    
    User->>API: POST /documents/bulk (PDF Bytes)
    API->>DB: Create Document Record (Status: PENDING)
    API->>Redis: Enqueue Task (doc_id, bytes_hex)
    API-->>User: 202 Accepted (job_ids)
    
    Note over Celery: Worker consumes task from Redis
    Redis->>Celery: Dequeue Task
    Celery->>DB: Update Status (INDEXING)
    
    Celery->>Celery: PyMuPDF Parse
    Celery->>Celery: Recursive Character Split
    
    Celery->>Vector: Generate Embeddings & Upsert
    
    Celery->>DB: Update Status (INDEXED)
```

## 2. Advanced Query Flow

This flow illustrates the defensive retrieval mechanisms and semantic caching strategy utilized to guarantee speed and relevance.

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant Cache as RedisVL Cache
    participant HyDE as LLM Expander
    participant DB as Postgres (Memory)
    participant Vector as Chroma + BM25
    participant LLM as OpenAI
    
    User->>API: POST /chat/stream {query}
    API->>DB: Fetch Conversation History
    
    API->>Cache: KNN Search (query_embedding)
    alt Similarity > 0.95
        Cache-->>API: Cached Response Text
        API-->>User: Instant SSE Stream (<50ms)
    else Cache Miss
        API->>HyDE: Generate Hypothetical Document
        HyDE-->>API: Expanded Text Block
        
        API->>Vector: RRF Search (Expanded Text)
        Vector-->>API: Top 20 Chunks
        
        API->>API: Cross-Encoder Rerank (Top 5)
        
        API->>LLM: Stream Completions (Context + Query)
        LLM-->>API: Token Stream
        API-->>User: SSE Stream
        
        API->>Cache: Upsert (query_embedding, response)
    end
```

## 3. Asynchronous Evaluation Flow

This flow illustrates how automated LLM-as-a-judge (RAGAS) evaluation occurs without impacting user perceived latency.

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Redis as Redis Broker
    participant Celery as Worker Node
    participant Judge as OpenAI (gpt-4o-mini)
    
    Note over API: After Chat Stream completes
    
    API->>DB: Save Assistant Message
    API->>Redis: Enqueue RAGAS Task (message_id, context, answer)
    
    Redis->>Celery: Dequeue Task
    
    Celery->>Judge: Prompt: Evaluate Faithfulness
    Judge-->>Celery: Score (0.0 - 1.0)
    
    Celery->>Judge: Prompt: Evaluate Relevance
    Judge-->>Celery: Score (0.0 - 1.0)
    
    Celery->>DB: Upsert Evaluation Record (message_id, scores)
```
