from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List

from src.database.session import get_db
from src.database.models import Document, Chunk, Evaluation

router = APIRouter()

@router.get("/dashboard")
async def get_metrics_dashboard(db: Session = Depends(get_db)) -> Dict:
    """
    Returns aggregated metrics from PostgreSQL.
    """
    
    docs_indexed = db.query(Document).count()
    total_chunks = db.query(Chunk).count()
    
    # Calculate averages, handling None values gracefully
    avg_metrics = db.query(
        func.avg(Evaluation.faithfulness).label('avg_faith'),
        func.avg(Evaluation.answer_rel).label('avg_rel'),
        func.avg(Evaluation.context_rec).label('avg_rec')
    ).first()
    
    # Simple P95 calculation for MVP (In prod, use percentile_cont if available or specialized query)
    latencies = [l[0] for l in db.query(Evaluation.latency_ms).filter(Evaluation.latency_ms.isnot(None)).order_by(Evaluation.latency_ms.asc()).all()]
    p95_latency = 0
    if latencies:
        idx = int(len(latencies) * 0.95)
        p95_latency = latencies[idx] if idx < len(latencies) else latencies[-1]
    
    return {
        "system_health": "healthy",
        "inventory": {
            "documents_indexed": docs_indexed,
            "total_chunks": total_chunks,
        },
        "performance": {
            "p95_latency_ms": p95_latency,
        },
        "quality": {
            "avg_faithfulness": float(avg_metrics.avg_faith) if avg_metrics and avg_metrics.avg_faith else 0.0,
            "avg_answer_relevance": float(avg_metrics.avg_rel) if avg_metrics and avg_metrics.avg_rel else 0.0,
            "avg_context_recall": float(avg_metrics.avg_rec) if avg_metrics and avg_metrics.avg_rec else 0.0
        }
    }

@router.get("/")
async def get_evaluations(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)) -> List[Dict]:
    evals = db.query(Evaluation).order_by(Evaluation.created_at.desc()).offset(skip).limit(limit).all()
    
    results = []
    for e in evals:
        results.append({
            "id": str(e.id),
            "faithfulness": e.faithfulness,
            "answer_relevance": e.answer_rel,
            "context_recall": e.context_rec,
            "latency_ms": e.latency_ms,
            "created_at": e.created_at.isoformat()
        })
    return results
