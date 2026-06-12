from functools import lru_cache
from src.retrieval.vector_store import VectorStore
from src.retrieval.sparse_store import SparseStore
from src.retrieval.hybrid_search import HybridSearch
from src.retrieval.reranker import CrossEncoderReranker
from src.core.config import get_settings

@lru_cache()
def get_vector_store():
    return VectorStore()

# For MVP, sparse store is kept in memory. In prod this would be Elasticsearch.
# We make it a singleton here.
sparse_store_instance = SparseStore()

def get_sparse_store():
    return sparse_store_instance

@lru_cache()
def get_hybrid_search():
    return HybridSearch(get_vector_store(), get_sparse_store())

@lru_cache()
def get_reranker():
    return CrossEncoderReranker()
