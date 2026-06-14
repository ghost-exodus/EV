"""
Database session factory and engine configuration.

Reads DATABASE_URL from environment variables. Provides:
  - engine:       SQLAlchemy engine instance
  - SessionLocal: Session factory for request-scoped sessions
  - get_db():     FastAPI dependency that yields a session per request
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://ev_user:ev_password@localhost:5432/ev_telemetry",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
