from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.config import get_settings

settings = get_settings()

# For MVP we'll use a sync engine since we're not heavily optimizing the DB yet
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
