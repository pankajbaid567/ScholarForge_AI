# Engineering Testing Strategy

Testing an AI platform is fundamentally different from testing a traditional CRUD application. While we still rely on unit tests for the deterministic backend code, we must introduce stochastic evaluation pipelines to test the actual intelligence of the system.

## 1. Unit Testing (pytest)
Used to test the deterministic business logic and API contracts.
*   **Target Coverage:** 80%+
*   **Key Tests:**
    *   `test_hybrid_search_fusion`: Mocks the outputs of Chroma and BM25 and asserts that the Reciprocal Rank Fusion math strictly adheres to the $1 / (k + rank)$ formula.
    *   `test_semantic_cache_hit`: Mocks RedisVL and asserts that an HTTP 200 is returned instantly without the `openai` client ever being instantiated.
    *   `test_pdf_parser`: Asserts that a known PDF is parsed into exactly 45 chunks with the correct metadata attached.

## 2. Integration Testing
Used to test the microservice topology and database transactions.
*   **Key Tests:**
    *   `test_celery_ingestion_flow`: Uploads a test document to the API, asserts that a 202 is returned, waits for the Celery worker to finish, and asserts that the document status in Postgres is updated to `INDEXED`.
    *   `test_ragas_celery_dispatch`: Simulates a chat completion and asserts that the Celery task for evaluation was correctly pushed to the Redis broker.

## 3. RAG Evaluation Tests (LLM-as-a-judge)
This is the CI/CD pipeline for the prompt engineering and retrieval logic.
*   **The Golden Dataset:** A frozen dataset of 100 heavily vetted academic questions.
*   **Execution:** Run nightly or on major PRs (e.g., swapping embedding models).
*   **Quality Gates:**
    *   `assert metrics.faithfulness >= 0.87`
    *   `assert metrics.context_recall >= 0.80`
    *   If a developer alters the Context Builder logic and the recall drops to 75%, the CI pipeline fails the build, preventing a regression in AI intelligence from reaching production.

## 4. Load Testing & Benchmarking (Locust)
Used to ensure the infrastructure can handle scale.
*   **Scenario 1: API Gateway Flood.** Simulates 500 concurrent users sending semantic cache hits. Verifies that the API maintains < 50ms latency without crashing.
*   **Scenario 2: Worker Queue Saturation.** Simulates uploading 50 massive PDFs concurrently. Verifies that the FastAPI event loop remains unblocked and that the Celery workers successfully chew through the queue without OOMing (Out of Memory).

## 5. Security Testing
*   **Prompt Injection Suite:** A suite of 50 adversarial prompts (e.g., "Ignore previous instructions") is run against the API. The test passes only if the LLM refuses to execute the injection and maintains its academic persona.
