"""
Unit tests for internal key verification on the POST /api/v1/ingest endpoint.
"""

import os
from unittest.mock import patch
import pytest
from routers.ingest import verify_internal_key


@pytest.fixture()
def internal_auth_client(client):
    """Bypasses the mock internal key validation to test the actual verification logic."""
    original = client.app.dependency_overrides.pop(verify_internal_key, None)
    yield client
    if original is not None:
        client.app.dependency_overrides[verify_internal_key] = original


def test_ingest_internal_correct_key(internal_auth_client):

    """POST /ingest with matching X-Internal-API-Key returns 202."""
    payload = {
        "schema_version": "1.0",
        "source": "ev_simulator_local",
        "battery_id": "EV_B0005_001",
        "vehicle_id": "VH_TESLA_042",
        "timestamp": "2024-01-15T14:23:45.123Z",
        "cycle_number": 147,
        "cycle_type": "discharge",
        "measurements": {
            "voltage_v": 3.8124,
            "current_a": -1.9987,
            "temperature_c": 24.5,
            "capacity_mah": 1823.4,
        },
    }

    with patch.dict(os.environ, {"INTERNAL_API_KEY": "test_internal_key_123"}):
        response = internal_auth_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-Internal-API-Key": "test_internal_key_123"},
        )

        assert response.status_code == 202
        assert response.json()["ingested"] is True
        assert response.json()["battery_id"] == "EV_B0005_001"


def test_ingest_internal_wrong_key(internal_auth_client):
    """POST /ingest with wrong API key returns 403."""
    payload = {
        "schema_version": "1.0",
        "source": "ev_simulator_local",
        "battery_id": "EV_B0005_001",
        "vehicle_id": "VH_TESLA_042",
        "timestamp": "2024-01-15T14:23:45.123Z",
        "cycle_number": 147,
        "cycle_type": "discharge",
        "measurements": {
            "voltage_v": 3.8124,
            "current_a": -1.9987,
            "temperature_c": 24.5,
            "capacity_mah": 1823.4,
        },
    }

    with patch.dict(os.environ, {"INTERNAL_API_KEY": "test_internal_key_123"}):
        response = internal_auth_client.post(
            "/api/v1/ingest",
            json=payload,
            headers={"X-Internal-API-Key": "incorrect_key"},
        )
        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]


def test_ingest_internal_missing_header(internal_auth_client):
    """POST /ingest with missing header returns 403."""
    payload = {
        "schema_version": "1.0",
        "source": "ev_simulator_local",
        "battery_id": "EV_B0005_001",
        "vehicle_id": "VH_TESLA_042",
        "timestamp": "2024-01-15T14:23:45.123Z",
        "cycle_number": 147,
        "cycle_type": "discharge",
        "measurements": {
            "voltage_v": 3.8124,
            "current_a": -1.9987,
            "temperature_c": 24.5,
            "capacity_mah": 1823.4,
        },
    }

    with patch.dict(os.environ, {"INTERNAL_API_KEY": "test_internal_key_123"}):
        response = internal_auth_client.post(
            "/api/v1/ingest",
            json=payload,
        )
        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]
