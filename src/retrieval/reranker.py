"""
Cross-Encoder Reranker with async support.

Uses sentence-transformers CrossEncoder for semantic reranking of
hybrid search candidates. The predict() call is CPU-bound (PyTorch),
so it is offloaded to a thread pool via run_in_executor to prevent
blocking the FastAPI async event loop.
"""
import asyncio
import logging
from typing import List, Dict

from sentence_transformers import CrossEncoder

from src.core.config import get_settings

logger = logging.getLogger("scholarforge.retrieval.reranker")
settings = get_settings()


class CrossEncoderReranker:
    def __init__(self, model_name: str = None):
        """
        Initializes the Cross-Encoder.
        ms-marco-MiniLM-L-6-v2 is fast and effective.
        For absolute highest accuracy (at the cost of latency), use 'BAAI/bge-reranker-large'.
        """
        model = model_name or settings.RERANKER_MODEL_NAME
        logger.info("Loading Cross-Encoder reranker model: %s", model)
        self.model = CrossEncoder(model, max_length=512)

    def _sync_rerank(self, query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
        """
        Synchronous reranking logic. Separated so it can be dispatched
        to a thread pool by the async wrapper.
        """
        if not candidates:
            return []

        # The CrossEncoder expects input as a list of pairs: [[query, text1], [query, text2], ...]
        sentence_pairs = [[query, candidate['text']] for candidate in candidates]

        # Predict logits (this is the CPU-bound operation)
        scores = self.model.predict(sentence_pairs)

        # Attach scores back to candidates
        for i, candidate in enumerate(candidates):
            candidate['rerank_score'] = float(scores[i])

        # Sort by rerank score descending
        reranked = sorted(candidates, key=lambda x: x['rerank_score'], reverse=True)

        logger.debug(
            "Reranked %d candidates → top %d (best score: %.4f)",
            len(candidates),
            top_k,
            reranked[0]['rerank_score'] if reranked else 0.0,
        )
        return reranked[:top_k]

    def rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Synchronous rerank interface (for Celery workers or non-async contexts).
        """
        return self._sync_rerank(query, candidates, top_k)

    async def arerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Async rerank that offloads the CPU-bound CrossEncoder.predict()
        to a thread pool, preventing it from blocking the FastAPI event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,  # Uses the default ThreadPoolExecutor
            self._sync_rerank,
            query,
            candidates,
            top_k,
        )
