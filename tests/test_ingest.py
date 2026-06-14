"""
Tests for POST /api/v1/ingest endpoint.
"""

from db.models import Battery, Telemetry


VALID_PAYLOAD = {
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
        "internal_resistance_ohm": 0.0214,
    },
    "metadata": {
        "simulator_version": "1.0.0",
        "replay_speed": 1.0,
        "source_file": "B0005.csv",
    },
}


def test_ingest_valid_payload(client, db_session):
    """Valid payload should return 202 and insert a telemetry row."""
    response = client.post("/api/v1/ingest", json=VALID_PAYLOAD)
    assert response.status_code == 202
    body = response.json()
    assert body["ingested"] is True
    assert body["battery_id"] == "EV_B0005_001"

    # Verify row exists in DB
    row = db_session.query(Telemetry).first()
    assert row is not None
    assert row.battery_id == "EV_B0005_001"
    assert float(row.voltage_v) == 3.8124


def test_ingest_auto_creates_battery(client, db_session):
    """If the battery doesn't exist, ingest should auto-create it."""
    response = client.post("/api/v1/ingest", json=VALID_PAYLOAD)
    assert response.status_code == 202

    battery = db_session.query(Battery).filter_by(battery_id="EV_B0005_001").first()
    assert battery is not None
    assert battery.vehicle_id == "VH_TESLA_042"
    assert float(battery.nominal_capacity_mah) == 2000.0


def test_ingest_missing_voltage_returns_422(client):
    """Missing required field voltage_v should return 422."""
    payload = {
        **VALID_PAYLOAD,
        "measurements": {
            # voltage_v intentionally omitted
            "current_a": -1.9987,
            "temperature_c": 24.5,
            "capacity_mah": 1823.4,
        },
    }
    response = client.post("/api/v1/ingest", json=payload)
    assert response.status_code == 422


def test_ingest_missing_battery_id_returns_422(client):
    """Missing required field battery_id should return 422."""
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "battery_id"}
    response = client.post("/api/v1/ingest", json=payload)
    assert response.status_code == 422


def test_ingest_duplicate_battery_id_reuses_existing(client, db_session):
    """Ingesting twice with the same battery_id should not create a duplicate battery."""
    client.post("/api/v1/ingest", json=VALID_PAYLOAD)

    # Second ingest — same battery_id, different cycle
    second_payload = {**VALID_PAYLOAD, "cycle_number": 148}
    response = client.post("/api/v1/ingest", json=second_payload)
    assert response.status_code == 202

    battery_count = db_session.query(Battery).count()
    assert battery_count == 1

    telemetry_count = db_session.query(Telemetry).count()
    assert telemetry_count == 2


def test_ingest_minimal_payload(client, db_session):
    """Minimal payload with only required fields should return 202 and insert a telemetry row."""
    minimal_payload = {
        "battery_id": "EV_MINIMAL_001",
        "timestamp": "2024-01-15T14:23:45.123Z",
        "cycle_number": 1,
        "cycle_type": "discharge",
        "measurements": {
            "voltage_v": 3.8,
            "current_a": -2.0,
            "temperature_c": 25.0,
            "capacity_mah": 1900.0,
        }
    }
    response = client.post("/api/v1/ingest", json=minimal_payload)
    assert response.status_code == 202
    body = response.json()
    assert body["ingested"] is True
    assert body["battery_id"] == "EV_MINIMAL_001"

    # Verify telemetry row exists in DB
    row = db_session.query(Telemetry).filter_by(battery_id="EV_MINIMAL_001").first()
    assert row is not None
    assert float(row.voltage_v) == 3.8
    assert float(row.capacity_mah) == 1900.0


def test_ingest_minimal_payload_auto_creates_battery_with_unknown_vehicle(client, db_session):
    """Ingesting a minimal payload without vehicle_id should auto-create the battery with vehicle_id = 'UNKNOWN'."""
    minimal_payload = {
        "battery_id": "EV_MINIMAL_002",
        "timestamp": "2024-01-15T14:23:45.123Z",
        "cycle_number": 1,
        "cycle_type": "discharge",
        "measurements": {
            "voltage_v": 3.8,
            "current_a": -2.0,
            "temperature_c": 25.0,
            "capacity_mah": 1900.0,
        }
    }
    response = client.post("/api/v1/ingest", json=minimal_payload)
    assert response.status_code == 202

    battery = db_session.query(Battery).filter_by(battery_id="EV_MINIMAL_002").first()
    assert battery is not None
    assert battery.vehicle_id == "UNKNOWN"
