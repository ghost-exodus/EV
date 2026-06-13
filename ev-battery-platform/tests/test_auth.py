"""
Tests for JWT Authentication, RBAC, and Token endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from db.models import Battery
from db.session import get_db
from main import app


@pytest.fixture()
def auth_client(db_session):
    """
    TestClient that only overrides the database session,
    leaving the verify_jwt dependency active for security testing.
    """

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── 1. Token Invalidation and Retrieval ──────────────────────────────────────


def test_auth_token_success_admin(auth_client):
    """POST /auth/token returns 200 and a token for admin/secret."""
    response = auth_client.post(
        "/auth/token",
        data={"username": "admin", "password": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["role"] == "fleet_admin"


def test_auth_token_success_operator(auth_client):
    """POST /auth/token returns 200 and a token for operator/secret."""
    response = auth_client.post(
        "/auth/token",
        data={"username": "operator", "password": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["role"] == "operator"


def test_auth_token_invalid_credentials(auth_client):
    """POST /auth/token returns 401 for incorrect credentials."""
    response = auth_client.post(
        "/auth/token",
        data={"username": "admin", "password": "wrong_password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


# ── 2. Route Protection (Authentication) ───────────────────────────────────


def test_route_requires_auth(auth_client):
    """Protected routes return 401 if no authorization header is provided."""
    response = auth_client.get("/api/v1/telemetry/EV_B0005_001")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_route_rejects_invalid_token(auth_client):
    """Protected routes return 401 for malformed / invalid JWT tokens."""
    response = auth_client.get(
        "/api/v1/telemetry/EV_B0005_001",
        headers={"Authorization": "Bearer invalid_token_value"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


# ── 3. Role-Based Access Control (Authorization) ──────────────────────────


def test_fleet_summary_admin_allowed(auth_client, db_session):
    """Admin role is allowed to view the fleet summary."""
    # Insert a dummy battery so fleet summary returns something
    battery = Battery(
        battery_id="EV_BATT_001",
        vehicle_id="VH_TESLA_1",
        nominal_capacity_mah=2000.0,
    )
    db_session.add(battery)
    db_session.commit()

    # Get admin token
    login_resp = auth_client.post(
        "/auth/token",
        data={"username": "admin", "password": "secret"},
    )
    token = login_resp.json()["access_token"]

    # Request summary
    response = auth_client.get(
        "/api/v1/fleet/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_batteries"] == 1
    assert body["fleet_avg_soh_percent"] is None  # no snapshots yet


def test_fleet_summary_operator_forbidden(auth_client, db_session):
    """Operator role is forbidden from viewing the fleet summary (403)."""
    # Get operator token
    login_resp = auth_client.post(
        "/auth/token",
        data={"username": "operator", "password": "secret"},
    )
    token = login_resp.json()["access_token"]

    # Request summary
    response = auth_client.get(
        "/api/v1/fleet/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Forbidden: insufficient permissions for this operation"
    )
