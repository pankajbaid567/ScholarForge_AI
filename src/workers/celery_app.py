"""
Celery application configuration and task definitions.

Uses two separate queues to prevent task starvation:
  - 'ingestion': Heavy, long-running document indexing tasks
  - 'evaluation': Lightweight RAGAS evaluation tasks

This ensures that a 10-minute ingestion job won't block quick
evaluation tasks from running.
"""
import asyncio
import logging

from celery import Celery

from src.core.config import get_settings

logger = logging.getLogger("scholarforge.workers")
settings = get_settings()

celery_app = Celery(
    "scholarforge_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    # Route tasks to dedicated queues
    task_routes={
        "task_run_ingestion": {"queue": "ingestion"},
        "task_run_ragas": {"queue": "evaluation"},
    },
    # Default queue for any unrouted tasks
    task_default_queue="evaluation",
)


@celery_app.task(name="task_run_ingestion", bind=True, max_retries=2)
def task_run_ingestion(self, file_bytes_hex: str, filename: str, doc_id: str):
    """
    Celery wrapper for document ingestion.
    We pass bytes as hex string because Celery requires JSON serializable arguments.
    """
    logger.info("Starting ingestion for document %s (%s)", doc_id, filename)
    try:
        from src.ingestion.pipeline import run_ingestion
        file_bytes = bytes.fromhex(file_bytes_hex)
        run_ingestion(file_bytes, filename, doc_id)
        logger.info("Ingestion complete for document %s", doc_id)
        return f"Ingestion complete for {doc_id}"
    except Exception as e:
        logger.error("Ingestion failed for %s: %s", doc_id, e, exc_info=True)
        raise self.retry(exc=e, countdown=30)


@celery_app.task(name="task_run_ragas", bind=True, max_retries=1)
def task_run_ragas(
    self,
    message_id: str,
    question: str,
    answer: str,
    contexts: list,
    chat_latency_ms: int = None,
    retrieval_latency_ms: int = None,
    llm_latency_ms: int = None,
):
    """
    Celery wrapper for RAGAS evaluation.
    Uses asyncio.run() instead of the deprecated get_event_loop().
    """
    logger.info("Starting RAGAS evaluation for message %s", message_id)
    try:
        from src.workers.eval_worker import run_evaluation_task
        asyncio.run(
            run_evaluation_task(
                message_id,
                question,
                answer,
                contexts,
                chat_latency_ms,
                retrieval_latency_ms,
                llm_latency_ms,
            )
        )
        logger.info("RAGAS evaluation complete for message %s", message_id)
        return f"Evaluation complete for {message_id}"
    except Exception as e:
        logger.error("RAGAS evaluation failed for %s: %s", message_id, e, exc_info=True)
        # Don't retry evaluation tasks aggressively — they're not critical
        return f"Evaluation failed for {message_id}: {e}"
