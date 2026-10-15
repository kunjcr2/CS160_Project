"""Database engine and session."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings  # pydantic-settings; reads DATABASE_URL from .env

# timezone=UTC: PostgreSQL gives every time back in UTC, whatever the computer's own time
# zone is (plan §6.5: the backend works in UTC; we change to local time only for the user).
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"options": "-c timezone=UTC"},
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    """FastAPI dependency: one session per request."""
    with SessionLocal() as session:
        yield session
