"""
BM25 Sparse Retrieval Store with lazy-loading from PostgreSQL.

Solves the critical process isolation bug: Celery workers and FastAPI
run in separate processes, so an in-memory-only BM25 index built by
Celery is invisible to FastAPI. This implementation lazily loads the
corpus from PostgreSQL on first search and periodically refreshes it.
"""
import logging
import re
import time
from typing import List, Dict

from rank_bm25 import BM25Okapi

logger = logging.getLogger("scholarforge.retrieval.sparse")


class SparseStore:
    def __init__(self, ttl_seconds: int = 300):
        self.corpus: List[Dict] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25 = None
        self._last_built: float = 0.0
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple tokenizer: lowercase and split by non-alphanumeric characters."""
        return [word for word in re.split(r'\W+', text.lower()) if word]

    def build_index(self, chunks: List[Dict]) -> None:
        """
        Builds the BM25 index from a list of chunk dictionaries.
        Expected format: {'id': str, 'text': str, 'metadata': dict}
        """
        self.corpus = chunks
        self.tokenized_corpus = [self._tokenize(chunk['text']) for chunk in chunks]

        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
            self._last_built = time.time()
            logger.info("BM25 index built with %d documents", len(chunks))
        else:
            logger.warning("BM25 index built with 0 documents (empty corpus)")

    def _is_stale(self) -> bool:
        """Returns True if the index needs to be rebuilt."""
        if self.bm25 is None:
            return True
        return (time.time() - self._last_built) > self._ttl_seconds

    def _lazy_load_from_db(self) -> None:
        """
        Lazily loads the full chunk corpus from PostgreSQL and rebuilds the
        BM25 index. This is the fix for the Celery/FastAPI process isolation
        bug: FastAPI's in-memory BM25 was always empty because only the
        Celery worker ever called build_index().
        """
        try:
            # Import here to avoid circular imports at module load time
            from src.database.session import SessionLocal
            from src.database.models import Chunk

            db = SessionLocal()
            try:
                all_chunks = db.query(Chunk).all()
                if not all_chunks:
                    logger.info("No chunks found in database; BM25 index will be empty")
                    return

                corpus = [
                    {
                        "id": str(c.id),
                        "text": c.text,
                        "metadata": c.metadata_ or {},
                    }
                    for c in all_chunks
                ]
                self.build_index(corpus)
                logger.info(
                    "BM25 index lazily loaded from PostgreSQL (%d chunks)",
                    len(corpus),
                )
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to lazy-load BM25 index from DB: %s", e, exc_info=True)

    def search(self, query: str, k: int = 20) -> List[Dict]:
        """
        Performs a sparse (keyword) search using BM25.
        Automatically rebuilds the index from PostgreSQL if stale or missing.
        """
        # Lazy-load / refresh the index if needed
        if self._is_stale():
            logger.debug("BM25 index is stale or missing; triggering lazy load")
            self._lazy_load_from_db()

        if not self.bm25:
            logger.warning("BM25 index is empty; returning no sparse results")
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Pair scores with the corpus
        results = [
            {"chunk": self.corpus[i], "score": scores[i]}
            for i in range(len(self.corpus))
        ]

        # Sort by score descending
        results = sorted(results, key=lambda x: x["score"], reverse=True)

        # Return top k, only documents that actually matched
        formatted_results = []
        for res in results[:k]:
            if res["score"] > 0:
                formatted_results.append({
                    "id": res["chunk"]["id"],
                    "text": res["chunk"]["text"],
                    "metadata": res["chunk"].get("metadata", {}),
                    "score": res["score"],
                })

        return formatted_results
