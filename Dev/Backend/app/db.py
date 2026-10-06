"""Database engine and session."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings  # pydantic-settings; reads DATABASE_URL from .env

# DATABASE_URL example: postgresql+psycopg://cs160:password@localhost:5432/voice_assistant
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    """FastAPI dependency: one session per request."""
    with SessionLocal() as session:
        yield session
