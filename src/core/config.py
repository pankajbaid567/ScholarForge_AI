from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "ScholarForge_AI"
    DATABASE_URL: str = "postgresql://scholarforge:scholarforge@localhost:5432/scholarforge"
    REDIS_URL: str = "redis://localhost:6379/0"
    CHROMA_DB_DIR: str = "./chroma_data"
    OPENAI_API_KEY: str = ""
    SCHOLARFORGE_API_KEY: str = ""

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
