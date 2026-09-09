"""
database.py — SQLAlchemy engine, session factory, and Base declarative.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from backend.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,          # detect stale connections
    pool_size=10,
    max_overflow=20,
    echo=False,                  # set True for SQL debug logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables defined via ORM models."""
    Base.metadata.create_all(bind=engine)
