# Observability & Tracing

## 1. The "LLM Black Box" Problem
When a user complains, "The chatbot is slow today," a traditional backend engineer looks at the API gateway logs and sees a `200 OK` response taking 2.5 seconds. 

However, in an advanced Hybrid RAG system, that 2.5 seconds is a black box. Was ChromaDB slow? Did the Cross-Encoder reranker run out of memory? Did OpenAI rate-limit the generation? 

To solve this, ScholarForge AI implements **OpenTelemetry (OTLP)** tracing natively throughout the application, exporting data to **Arize Phoenix**, an open-source LLM observability platform.

## 2. Arize Phoenix Architecture
Phoenix runs as a dedicated sidecar container within our `docker-compose` topology, listening on port `6006`.

Instead of writing custom `start_timer()` and `stop_timer()` wrappers around every function, we utilize OpenTelemetry auto-instrumentation:
*   `FastAPIInstrumentor`: Automatically captures the HTTP Request latency, endpoint route, and status code.
*   `OpenAIInstrumentor`: Automatically intercepts every call made via the `openai` python package, logging the exact Prompt sent, the Tokens used, and the Time-To-First-Token (TTFT) latency.

## 3. Trace Spans in Production
When a cache miss occurs, Phoenix visualizes the waterfall of execution spans. A typical trace looks like this:

```text
POST /api/v1/chat/stream  [1450ms]
├── POST /embeddings (HyDE generation) [600ms]
│   └── "Prompt: Write a short paragraph..."
├── ChromaDB HNSW Search [45ms]
├── BM25 Keyword Search [20ms]
├── RRF Fusion Logic [5ms]
├── Cross-Encoder Reranking [280ms]
└── POST /chat/completions (Stream Generation) [500ms]
    └── "Tokens used: 1200 prompt, 400 completion"
```

This visualization allows Engineering Managers to pinpoint exactly where compute resources need to be allocated. For example, if the Cross-Encoder consistently takes >500ms, it is a signal to move the reranking worker to a GPU-backed instance.

## 4. Semantic Cache Monitoring
Observability is also critical for measuring the ROI of our architecture choices.

By filtering traces in Phoenix, we can monitor the **Cache Hit Ratio** of the `redisvl` Semantic Cache. 
*   If the Cache Hit Ratio is **> 40%**, we know the embedding distance threshold (e.g., `0.10`) is functioning perfectly.
*   If the Cache Hit Ratio is **0%**, it triggers an operational alert indicating that the Redis node might have evicted the vector index or the distance threshold is too strict.

## 5. Error Tracking & Alerting
Phoenix natively captures stack traces for failed LLM calls. If OpenAI throws a `429 Too Many Requests` error, the trace is painted red in the dashboard. 

In a true enterprise environment, this OTLP data can be seamlessly routed to Datadog, New Relic, or PagerDuty to trigger on-call alerts if the P95 latency exceeds our 1.5-second SLA.
