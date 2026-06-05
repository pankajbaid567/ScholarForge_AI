from redisvl.extensions.llmcache import SemanticCache
from src.core.config import get_settings

settings = get_settings()

class CacheManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
            cls._instance._init_cache()
        return cls._instance
        
    def _init_cache(self):
        # We initialize the Semantic Cache with an appropriate distance threshold
        # 0.05 is highly strict, 0.10 is moderate.
        self.cache = SemanticCache(
            name="scholarforge_cache",
            redis_url=settings.REDIS_URL,
            distance_threshold=0.10
        )
        # Assuming the cache index needs to be created on first boot if not exists
        try:
            self.cache.create_index()
        except Exception:
            pass # Index already exists
            
    def check_cache(self, query: str):
        """Returns the cached response if available."""
        results = self.cache.check(prompt=query)
        if results:
            return results[0] # Return the closest cached response
        return None
        
    def store_cache(self, query: str, response: str):
        """Stores the query and response in the semantic cache."""
        self.cache.store(prompt=query, response=response)
        
def get_semantic_cache():
    return CacheManager()
