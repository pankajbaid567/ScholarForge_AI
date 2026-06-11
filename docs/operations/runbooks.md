# Operations Runbooks

This document outlines standard operating procedures (SOPs) for recovering the ScholarForge AI system during critical incidents. 

## 1. Incident: Redis Cache Down

**Symptoms:**
*   API throws `ConnectionError` when attempting to connect to port `6379`.
*   Cache Hit Ratio drops to 0%.
*   Celery tasks fail to enqueue.

**Impact:** HIGH. Ingestion stops, Background evaluation stops, Latency increases significantly due to cache misses.

**Recovery Steps:**
1.  Check container logs: `docker logs scholarforge_redis`
2.  If OOM (Out of Memory), flush the cache temporarily: `docker exec -it scholarforge_redis redis-cli FLUSHALL`
3.  Restart the container: `docker restart scholarforge_redis`
4.  *Prevention:* Adjust the eviction policy in `redis.conf` to `allkeys-lru` and increase the container memory limit.

## 2. Incident: OpenAI API Down (or Rate Limited)

**Symptoms:**
*   FastAPI logs show `429 Too Many Requests` or `500 Internal Server Error` originating from `openai.AsyncOpenAI`.
*   Arize Phoenix traces show LLM generation spans turning red.

**Impact:** CRITICAL. Chat functionality completely breaks for cache misses.

**Recovery Steps:**
1.  Verify OpenAI status at `status.openai.com`.
2.  If it is a rate limit (429), verify the Redis Rate Limiter is functioning properly to block abusive users.
3.  *Fallback Action:* Update `src/core/config.py` to point `OPENAI_API_BASE` to a local fallback model (e.g., vLLM or Ollama serving LLaMa-3) and perform a rolling restart of the API containers.

## 3. Incident: Celery Worker Queue Backlog

**Symptoms:**
*   Users report that uploaded PDFs are stuck in `PENDING` status for hours.
*   Dashboard evaluations are not updating.
*   Redis memory usage is slowly climbing as the queue builds.

**Impact:** MEDIUM. Core chat functionality remains active, but background processing is stalled.

**Recovery Steps:**
1.  Check queue depth: `docker exec -it scholarforge_redis redis-cli LLEN scholarforge_tasks`
2.  Check worker logs: `docker logs scholarforge_worker`
3.  If the worker is stuck parsing a corrupted PDF, restart the worker container: `docker restart scholarforge_worker`
4.  *Scaling Action:* If the backlog is legitimate (e.g., 5,000 PDFs uploaded), scale the worker horizontally: `docker-compose up -d --scale worker=3`

## 4. Incident: ChromaDB Corruption

**Symptoms:**
*   API throws `IndexError` or `ValueError` during Hybrid Search.
*   FastAPI logs indicate ChromaDB cannot find the collection `scholarforge_chunks`.

**Impact:** CRITICAL. Retrieval pipeline is dead.

**Recovery Steps:**
1.  Verify the integrity of the mounted volume: `ls -la /app/chroma_data`
2.  If the SQLite index is corrupted, it must be rebuilt. 
3.  *Recovery Action:* Delete the volume `docker volume rm scholarforge_chroma_data`, restart the ChromaDB container, and trigger a re-ingestion script that pulls all raw text from the `chunks` table in PostgreSQL and re-embeds them into Chroma.
