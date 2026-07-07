"""
Centralized configuration for ScholarForge_AI.

All settings are loaded from environment variables (via .env file)
with sensible defaults. No magic strings should exist outside this module.
"""
import logging
import sys
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    # --- Project ---
    PROJECT_NAME: str = "ScholarForge_AI"
    LOG_LEVEL: str = "INFO"

    # --- Database ---
    DATABASE_URL: str = "postgresql://scholarforge:scholarforge@localhost:15432/scholarforge"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:16379/0"

    # --- Vector Store ---
    CHROMA_DB_DIR: str = "./chroma_data"
    CHROMA_HOST: str = ""
    CHROMA_PORT: int = 8000

    # --- API Keys ---
    OPENAI_API_KEY: str = ""
    HUGGINGFACE_API_KEY: str = ""
    SCHOLARFORGE_API_KEY: str = ""

    # --- Model Configuration ---
    LLM_MODEL_NAME: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- Chunking ---
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # --- Retrieval ---
    SEMANTIC_CACHE_THRESHOLD: float = 0.10
    RERANKER_TOP_K: int = 5
    HYBRID_SEARCH_K: int = 20
    BM25_TTL_SECONDS: int = 300  # Rebuild BM25 index every 5 minutes

    # --- API / Security ---
    CORS_ORIGINS: str = "*"  # Comma-separated list of allowed origins
    API_BASE_URL: str = "http://127.0.0.1:8000/api/v1"
    MAX_UPLOAD_SIZE_MB: int = 50
    RATE_LIMIT_MAX_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # --- LLM Parameters ---
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.3
    HYDE_MAX_TOKENS: int = 150

    # --- Memory ---
    MEMORY_MAX_TOKENS: int = 3000

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached singleton of the application settings."""
    return Settings()


def setup_logging() -> logging.Logger:
    """
    Configures structured logging for the entire application.
    Returns the root logger for the 'scholarforge' namespace.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Configure the root 'scholarforge' logger
    logger = logging.getLogger("scholarforge")
    logger.setLevel(log_level)

    # Prevent duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
