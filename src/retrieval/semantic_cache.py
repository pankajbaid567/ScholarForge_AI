"""
Semantic Cache Manager backed by RedisVL.

Provides vector-similarity-based caching of LLM responses to avoid
redundant LLM calls for semantically similar queries. Uses cosine
distance with a configurable threshold.

Designed to fail gracefully — if Redis is unavailable, the cache
is simply bypassed rather than crashing the API.
"""
import logging

from redisvl.extensions.llmcache import SemanticCache
from src.core.config import get_settings

logger = logging.getLogger("scholarforge.retrieval.cache")
settings = get_settings()


class CacheManager:
    """Singleton semantic cache manager."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cache = None
        self._init_cache()

    def _init_cache(self):
        """Initializes the Semantic Cache with graceful fallback."""
        try:
            self._cache = SemanticCache(
                name="scholarforge_cache",
                redis_url=settings.REDIS_URL,
                distance_threshold=settings.SEMANTIC_CACHE_THRESHOLD,
            )
            try:
                self._cache.create_index()
                logger.info(
                    "Semantic cache initialized (threshold=%.2f)",
                    settings.SEMANTIC_CACHE_THRESHOLD,
                )
            except Exception:
                # Index already exists — this is expected on restarts
                logger.info("Semantic cache index already exists")
        except Exception as e:
            logger.warning(
                "Failed to initialize semantic cache: %s. "
                "Cache will be disabled — all requests will hit the LLM.",
                e,
            )
            self._cache = None

    def check_cache(self, query: str) -> str | None:
        """
        Returns the cached response if a semantically similar query exists.
        Returns None if no match or if cache is unavailable.
        """
        if not self._cache:
            return None

        try:
            results = self._cache.check(prompt=query)
            if results:
                response = results[0]["response"]
                logger.debug("Cache HIT for query: %.50s...", query)
                return response
        except Exception as e:
            logger.warning("Cache check failed: %s", e)

        return None

    def store_cache(self, query: str, response: str) -> None:
        """
        Stores a query-response pair in the semantic cache.
        Silently fails if cache is unavailable.
        """
        if not self._cache:
            return

        try:
            self._cache.store(prompt=query, response=response)
            logger.debug("Cached response for query: %.50s...", query)
        except Exception as e:
            logger.warning("Failed to store in cache: %s", e)


def get_semantic_cache() -> CacheManager:
    """Returns the singleton CacheManager instance."""
    return CacheManager()
