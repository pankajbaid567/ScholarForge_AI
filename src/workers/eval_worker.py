"""
RAGAS Evaluation Background Worker.

Runs LLM-as-a-judge evaluation metrics (Faithfulness, Answer Relevancy,
Context Recall) and persists the results to PostgreSQL. This worker is
invoked asynchronously via Celery so user-facing latency is not impacted
by the heavy evaluation calls.
"""
import logging
import time

from src.evaluation.ragas_evaluator import RagasEvaluator
from src.database.models import Evaluation
from src.database.session import SessionLocal

logger = logging.getLogger("scholarforge.workers.eval")


async def run_evaluation_task(
    message_id: str,
    question: str,
    answer: str,
    contexts: list[str],
    chat_latency_ms: int = None,
    retrieval_latency_ms: int = None,
    llm_latency_ms: int = None,
):
    """
    Background worker that runs the RAGAS evaluation and saves the result to the DB.
    This ensures that user latency is not impacted by the heavy LLM-as-a-judge calls.
    """
    start_time = time.time()
    evaluator = RagasEvaluator()

    # Run evaluation
    results = evaluator.evaluate_single_interaction(
        question=question,
        answer=answer,
        contexts=contexts,
    )

    eval_duration_ms = int((time.time() - start_time) * 1000)

    if not results:
        logger.warning(
            "RAGAS evaluation returned empty results for message %s", message_id
        )
        return

    logger.info(
        "RAGAS evaluation for message %s: faithfulness=%.3f, relevancy=%.3f (took %dms)",
        message_id,
        results.get("faithfulness", 0.0),
        results.get("answer_relevancy", 0.0),
        eval_duration_ms,
    )

    # Persist evaluation results to PostgreSQL
    db = SessionLocal()
    try:
        # Check if evaluation already exists for this message
        existing = (
            db.query(Evaluation)
            .filter(Evaluation.message_id == message_id)
            .first()
        )
        if existing:
            logger.info(
                "Evaluation already exists for message %s; updating", message_id
            )
            existing.faithfulness = results.get("faithfulness")
            existing.answer_rel = results.get("answer_relevancy")
            existing.context_rec = results.get("context_recall")
            existing.latency_ms = eval_duration_ms
            existing.chat_latency_ms = chat_latency_ms
            existing.retrieval_latency_ms = retrieval_latency_ms
            existing.llm_latency_ms = llm_latency_ms
        else:
            new_eval = Evaluation(
                message_id=message_id,
                faithfulness=results.get("faithfulness"),
                answer_rel=results.get("answer_relevancy"),
                context_rec=results.get("context_recall"),
                latency_ms=eval_duration_ms,
                chat_latency_ms=chat_latency_ms,
                retrieval_latency_ms=retrieval_latency_ms,
                llm_latency_ms=llm_latency_ms,
            )
            db.add(new_eval)

        db.commit()
        logger.info("Evaluation results saved to DB for message %s", message_id)
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to save evaluation for message %s: %s",
            message_id,
            e,
            exc_info=True,
        )
    finally:
        db.close()
