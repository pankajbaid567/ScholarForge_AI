import os
from celery import Celery
from src.core.config import get_settings
from src.ingestion.pipeline import run_ingestion
from src.workers.eval_worker import async_evaluation_task
import asyncio

settings = get_settings()

celery_app = Celery(
    "scholarforge_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery_app.task(name="task_run_ingestion")
def task_run_ingestion(file_bytes_hex: str, filename: str, doc_id: str):
    """
    Celery wrapper for document ingestion.
    We pass bytes as hex string because Celery requires JSON serializable arguments.
    """
    file_bytes = bytes.fromhex(file_bytes_hex)
    run_ingestion(file_bytes, filename, doc_id)
    return f"Ingestion complete for {doc_id}"

@celery_app.task(name="task_run_ragas")
def task_run_ragas(message_id: str, question: str, answer: str, contexts: list):
    """
    Celery wrapper for RAGAS evaluation.
    """
    # Run the async evaluation task in a new event loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_evaluation_task(message_id, question, answer, contexts))
    return f"Evaluation complete for {message_id}"
