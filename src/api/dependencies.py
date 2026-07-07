"""
Dependency injection for RAG pipeline components.

All heavy components (VectorStore, Reranker, etc.) are cached as
singletons via @lru_cache to avoid re-initializing ML models on
every request.
"""
from functools import lru_cache

from src.retrieval.vector_store import VectorStore
from src.retrieval.sparse_store import SparseStore
from src.retrieval.hybrid_search import HybridSearch
from src.retrieval.reranker import CrossEncoderReranker
from src.core.config import get_settings

settings = get_settings()


@lru_cache()
def get_vector_store() -> VectorStore:
    """Returns a cached singleton VectorStore instance."""
    return VectorStore()


@lru_cache()
def get_sparse_store() -> SparseStore:
    """
    Returns a cached singleton SparseStore instance.
    The BM25 index lazily loads from PostgreSQL on first search.
    """
    return SparseStore(ttl_seconds=settings.BM25_TTL_SECONDS)


@lru_cache()
def get_hybrid_search() -> HybridSearch:
    """Returns a cached singleton HybridSearch instance."""
    return HybridSearch(get_vector_store(), get_sparse_store())


@lru_cache()
def get_reranker() -> CrossEncoderReranker:
    """Returns a cached singleton CrossEncoderReranker instance."""
    return CrossEncoderReranker()
