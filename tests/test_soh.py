"""
Tests for SoH service and GET /api/v1/soh/{battery_id} endpoint.
"""

from datetime import datetime, timezone

from db.models import Battery, Telemetry
from services.soh_service import _calculate_soh_with_session, get_soh_status


# ---------------------------------------------------------------------------
# Unit tests for soh_service
# ---------------------------------------------------------------------------


def test_get_soh_status():
    """Status labels should match the thresholds."""
    assert get_soh_status(100.0) == "healthy"
    assert get_soh_status(80.0) == "healthy"
    assert get_soh_status(79.9) == "warning"
    assert get_soh_status(60.0) == "warning"
    assert get_soh_status(59.9) == "critical"
    assert get_soh_status(0.0) == "critical"


def test_calculate_soh_basic(db_session):
    """SoH should be (current_capacity / nominal) * 100."""
    # Setup: battery with nominal 2000 mAh
    battery = Battery(
        battery_id="BAT_001",
        vehicle_id="VH_001",
        nominal_capacity_mah=2000.0,
    )
    db_session.add(battery)

    # Telemetry with capacity = 1600 mAh → SoH = 80%
    reading = Telemetry(
        battery_id="BAT_001",
        recorded_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        cycle_number=10,
        voltage_v=3.8,
        current_a=-2.0,
        temperature_c=25.0,
        capacity_mah=1600.0,
        cycle_type="discharge",
    )
    db_session.add(reading)
    db_session.commit()

    _calculate_soh_with_session("BAT_001", db_session)

    from db.models import SoHSnapshot
    snapshot = db_session.query(SoHSnapshot).first()
    assert snapshot is not None
    assert float(snapshot.soh_percent) == 80.0
    assert float(snapshot.capacity_mah) == 1600.0


# ---------------------------------------------------------------------------
# Integration tests for GET /api/v1/soh/{battery_id}
# ---------------------------------------------------------------------------


def _ingest(client, cycle: int, capacity: float):
    """Helper to ingest a reading with a given cycle and capacity."""
    return client.post("/api/v1/ingest", json={
        "schema_version": "1.0",
        "source": "test",
        "battery_id": "EV_SOH_001",
        "vehicle_id": "VH_SOH_001",
        "timestamp": f"2024-01-{10 + cycle:02d}T10:00:00Z",
        "cycle_number": cycle,
        "cycle_type": "discharge",
        "measurements": {
            "voltage_v": 3.7,
            "current_a": -1.5,
            "temperature_c": 23.0,
            "capacity_mah": capacity,
        },
    })


def test_soh_endpoint_degrading_trend(client, db_session):
    """
    Ingest readings with decreasing capacity → SoH should degrade.
    Since background tasks don't run synchronously in tests, we
    manually trigger SoH calculation.
    """
    # Ingest 5 readings with decreasing capacity (nominal = 2000 default)
    capacities = [1900, 1850, 1800, 1750, 1700]
    for i, cap in enumerate(capacities, start=1):
        resp = _ingest(client, cycle=i, capacity=cap)
        assert resp.status_code == 202

    # Manually trigger SoH for each cycle (background task won't run in tests)
    for i, cap in enumerate(capacities, start=1):
        _calculate_soh_with_session("EV_SOH_001", db_session)
        # We need to update the "latest" reading for each calc, but since
        # all readings are already in DB, the service will use the last one.
        # Let's calculate for each reading individually by adjusting approach.

    # Actually, the service always picks the LATEST reading.
    # So after all ingests, one call gives us the snapshot for cycle 5.
    # Let's insert snapshots properly for the test:
    from db.models import SoHSnapshot
    db_session.query(SoHSnapshot).delete()
    db_session.commit()

    for i, cap in enumerate(capacities, start=1):
        snapshot = SoHSnapshot(
            battery_id="EV_SOH_001",
            snapshot_at=datetime(2024, 1, 10 + i, 10, 0, 0, tzinfo=timezone.utc),
            cycle_number=i,
            soh_percent=(cap / 2000.0) * 100,
            capacity_mah=cap,
        )
        db_session.add(snapshot)
    db_session.commit()

    # Now query the SoH endpoint
    response = client.get("/api/v1/soh/EV_SOH_001")
    assert response.status_code == 200

    body = response.json()
    assert body["battery_id"] == "EV_SOH_001"
    assert body["current_soh_percent"] == 85.0  # 1700/2000 * 100
    assert body["status"] == "healthy"
    assert body["nominal_capacity_mah"] == 2000.0
    assert body["current_capacity_mah"] == 1700.0

    # Trend should be degrading
    assert body["trend"]["direction"] == "degrading"
    assert body["trend"]["delta_last_10_cycles"] < 0

    # History should be in ascending cycle order
    history = body["trend"]["history"]
    assert len(history) == 5
    assert history[0]["cycle"] == 1
    assert history[-1]["cycle"] == 5


def test_soh_battery_not_found(client):
    """Requesting SoH for a non-existent battery should return 404."""
    response = client.get("/api/v1/soh/DOES_NOT_EXIST")
    assert response.status_code == 404


def test_soh_no_snapshots(client, db_session):
    """Battery exists but no SoH data yet should return graceful 200 with message."""
    battery = Battery(
        battery_id="BAT_EMPTY",
        vehicle_id="VH_EMPTY",
        nominal_capacity_mah=2000.0,
    )
    db_session.add(battery)
    db_session.commit()

    response = client.get("/api/v1/soh/BAT_EMPTY")
    assert response.status_code == 200
    
    body = response.json()
    assert body["battery_id"] == "BAT_EMPTY"
    assert body["current_soh_percent"] is None
    assert body["status"] == "unknown"
    assert body["nominal_capacity_mah"] == 2000.0
    assert body["current_capacity_mah"] is None
    assert body["last_calculated_at"] is None
    assert body["trend"] is None
    assert body["message"] == "No SoH data available yet — capacity_mah not received"
