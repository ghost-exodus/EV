"""
Pytest fixtures for EV Battery Telemetry tests.

Uses an in-memory SQLite database for fast, isolated testing.
Overrides the FastAPI `get_db` dependency to inject the test session.

Key details:
  - StaticPool ensures all connections share the same in-memory SQLite DB
    (without this, each connection gets a separate empty database).
  - services.soh_service.SessionLocal is patched so that the background
    task uses the test DB instead of the production PostgreSQL.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base
from db.session import get_db
from main import app

# ── SQLite in-memory engine ──────────────────────────────────────────────
# StaticPool keeps a single connection alive so all sessions see the same
# in-memory database — without it each .connect() creates a fresh DB.
SQLALCHEMY_TEST_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


# Enable foreign key enforcement in SQLite (off by default)
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test, drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """Yield a test database session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """
    FastAPI TestClient that:
    1. Overrides get_db to inject the test DB session.
    2. Overrides verify_jwt to inject a mock authenticated admin user.
    3. Patches soh_service.SessionLocal so background tasks use the test DB.
    """
    from auth.dependencies import verify_jwt

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    def _override_verify_jwt():
        return {"username": "admin", "role": "fleet_admin"}

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[verify_jwt] = _override_verify_jwt

    with patch("services.soh_service.SessionLocal", return_value=db_session):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()
