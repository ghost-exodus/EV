"""
Tests for GET /api/v1/telemetry/{battery_id} endpoint.
"""

import base64
import json


def _make_payload(cycle_number: int, capacity: float = 1800.0) -> dict:
    """Helper to build an ingest payload with a specific cycle number."""
    return {
        "schema_version": "1.0",
        "source": "test",
        "battery_id": "EV_TEST_001",
        "vehicle_id": "VH_TEST_001",
        "timestamp": f"2024-01-{15 + cycle_number:02d}T10:00:00Z",
        "cycle_number": cycle_number,
        "cycle_type": "discharge",
        "measurements": {
            "voltage_v": 3.8,
            "current_a": -2.0,
            "temperature_c": 25.0,
            "capacity_mah": capacity,
        },
    }


def test_telemetry_returns_readings(client):
    """Ingested rows should appear in GET telemetry response."""
    # Ingest 3 readings
    for i in range(1, 4):
        resp = client.post("/api/v1/ingest", json=_make_payload(i))
        assert resp.status_code == 202

    response = client.get("/api/v1/telemetry/EV_TEST_001")
    assert response.status_code == 200

    body = response.json()
    assert body["battery_id"] == "EV_TEST_001"
    assert body["total_records"] == 3
    assert len(body["readings"]) == 3
    assert body["has_more"] is False


def test_telemetry_pagination(client):
    """Cursor-based pagination should return correct pages."""
    # Ingest 5 readings
    for i in range(1, 6):
        client.post("/api/v1/ingest", json=_make_payload(i))

    # First page: limit=2
    response = client.get("/api/v1/telemetry/EV_TEST_001?limit=2")
    body = response.json()
    assert len(body["readings"]) == 2
    assert body["has_more"] is True
    assert body["cursor"] is not None

    # Second page using cursor
    cursor = body["cursor"]
    response = client.get(f"/api/v1/telemetry/EV_TEST_001?limit=2&cursor={cursor}")
    body = response.json()
    assert len(body["readings"]) == 2
    assert body["has_more"] is True

    # Third page — should have 1 remaining
    cursor = body["cursor"]
    response = client.get(f"/api/v1/telemetry/EV_TEST_001?limit=2&cursor={cursor}")
    body = response.json()
    assert len(body["readings"]) == 1
    assert body["has_more"] is False


def test_telemetry_response_shape(client):
    """Each reading should contain the expected fields."""
    client.post("/api/v1/ingest", json=_make_payload(1))

    response = client.get("/api/v1/telemetry/EV_TEST_001")
    body = response.json()

    reading = body["readings"][0]
    expected_keys = {
        "id", "recorded_at", "cycle_number", "cycle_type",
        "voltage_v", "current_a", "temperature_c", "capacity_mah",
    }
    assert expected_keys == set(reading.keys())


def test_telemetry_battery_not_found(client):
    """Requesting telemetry for a non-existent battery should return 404."""
    response = client.get("/api/v1/telemetry/DOES_NOT_EXIST")
    assert response.status_code == 404
