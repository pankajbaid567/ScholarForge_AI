"""
Metrics and Evaluation Dashboard API routes.

Provides:
  - Aggregated dashboard metrics (document count, quality scores, P95 latency)
  - Paginated evaluation history
"""
import logging
from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.session import get_db
from src.database.models import Document, Chunk, Evaluation

logger = logging.getLogger("scholarforge.api.metrics")
router = APIRouter()


@router.get("/dashboard")
async def get_metrics_dashboard(db: Session = Depends(get_db)) -> Dict:
    """
    Returns aggregated metrics for the evaluation dashboard.
    All values are safe defaults if no data exists yet.
    """
    try:
        docs_indexed = db.query(Document).count()
        total_chunks = db.query(Chunk).count()

        # Calculate averages, handling None values gracefully
        avg_metrics = db.query(
            func.avg(Evaluation.faithfulness).label("avg_faith"),
            func.avg(Evaluation.answer_rel).label("avg_rel"),
            func.avg(Evaluation.context_rec).label("avg_rec"),
        ).first()

        # Helper for P95 calculation
        def get_p95(column) -> int:
            latencies = [
                row[0]
                for row in db.query(column)
                .filter(column.isnot(None))
                .order_by(column.asc())
                .all()
            ]
            if latencies:
                idx = min(int(len(latencies) * 0.95), len(latencies) - 1)
                return latencies[idx]
            return 0

        total_evaluations = db.query(Evaluation).count()

        return {
            "system_health": "healthy",
            "inventory": {
                "documents_indexed": docs_indexed,
                "total_chunks": total_chunks,
            },
            "performance": {
                "p95_chat_latency_ms": get_p95(Evaluation.chat_latency_ms),
                "p95_eval_latency_ms": get_p95(Evaluation.latency_ms),
                "p95_retrieval_latency_ms": get_p95(Evaluation.retrieval_latency_ms),
                "p95_llm_latency_ms": get_p95(Evaluation.llm_latency_ms),
                "total_evaluations": total_evaluations,
            },
            "quality": {
                "avg_faithfulness": (
                    float(avg_metrics.avg_faith)
                    if avg_metrics and avg_metrics.avg_faith
                    else 0.0
                ),
                "avg_answer_relevance": (
                    float(avg_metrics.avg_rel)
                    if avg_metrics and avg_metrics.avg_rel
                    else 0.0
                ),
                "avg_context_recall": (
                    float(avg_metrics.avg_rec)
                    if avg_metrics and avg_metrics.avg_rec
                    else 0.0
                ),
            },
        }
    except Exception as e:
        logger.error("Failed to fetch dashboard metrics: %s", e, exc_info=True)
        return {
            "system_health": "degraded",
            "inventory": {"documents_indexed": 0, "total_chunks": 0},
            "performance": {
                "p95_chat_latency_ms": 0,
                "p95_eval_latency_ms": 0,
                "p95_retrieval_latency_ms": 0,
                "p95_llm_latency_ms": 0,
                "total_evaluations": 0,
            },
            "quality": {
                "avg_faithfulness": 0.0,
                "avg_answer_relevance": 0.0,
                "avg_context_recall": 0.0,
            },
        }


@router.get("/")
async def get_evaluations(
    skip: int = 0, limit: int = 50, db: Session = Depends(get_db)
) -> List[Dict]:
    """Returns paginated evaluation history, newest first."""
    try:
        evals = (
            db.query(Evaluation)
            .order_by(Evaluation.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        results = []
        for e in evals:
            results.append({
                "id": str(e.id),
                "faithfulness": e.faithfulness,
                "answer_relevance": e.answer_rel,
                "context_recall": e.context_rec,
                "eval_latency_ms": e.latency_ms,
                "chat_latency_ms": e.chat_latency_ms,
                "retrieval_latency_ms": e.retrieval_latency_ms,
                "llm_latency_ms": e.llm_latency_ms,
                "cache_hit": e.cache_hit,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            })
        return results
    except Exception as e:
        logger.error("Failed to fetch evaluations: %s", e, exc_info=True)
        return []
