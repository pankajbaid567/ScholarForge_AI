"""
Database session management.

Provides both sync engine (for current use) and connection pool
configuration. The sync engine is used by SQLAlchemy ORM for all
database operations.
"""
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import get_settings

logger = logging.getLogger("scholarforge.database")
settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=3600,  # Recycle connections after 1 hour
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger.info(
    "Database engine configured (pool_size=%d, max_overflow=%d)",
    settings.DB_POOL_SIZE,
    settings.DB_MAX_OVERFLOW,
)


def get_db():
    """
    FastAPI dependency that provides a database session.
    Ensures the session is properly closed after each request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
