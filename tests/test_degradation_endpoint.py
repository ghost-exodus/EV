"""
Unit tests for the GET /api/v1/analytics/degradation endpoint.
"""

from datetime import datetime, timezone
from db.models import Battery, SoHSnapshot


def test_degradation_endpoint_success(client, db_session):
    """GET /analytics/degradation groups snapshots by day and calculates averages."""
    # Setup database
    battery = Battery(
        battery_id="EV_B0005_001",
        vehicle_id="VH_TESLA_042",
        nominal_capacity_mah=2000.0,
    )
    db_session.add(battery)

    # Day 1: 2024-01-14 (2 snapshots)
    dt1 = datetime(2024, 1, 14, 10, 0, 0, tzinfo=timezone.utc)
    dt2 = datetime(2024, 1, 14, 15, 0, 0, tzinfo=timezone.utc)
    # Day 2: 2024-01-15 (1 snapshot)
    dt3 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    snap1 = SoHSnapshot(
        battery_id="EV_B0005_001",
        snapshot_at=dt1,
        cycle_number=1,
        soh_percent=85.0,
        capacity_mah=1700.0,
    )
    snap2 = SoHSnapshot(
        battery_id="EV_B0005_001",
        snapshot_at=dt2,
        cycle_number=2,
        soh_percent=83.0,
        capacity_mah=1660.0,
    )
    snap3 = SoHSnapshot(
        battery_id="EV_B0005_001",
        snapshot_at=dt3,
        cycle_number=3,
        soh_percent=80.0,
        capacity_mah=1600.0,
    )

    db_session.add_all([snap1, snap2, snap3])
    db_session.commit()

    # Query metrics
    response = client.get(
        "/api/v1/analytics/degradation?battery_id=EV_B0005_001"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["battery_id"] == "EV_B0005_001"
    assert len(data["data"]) == 2

    # Verify Day 1 aggregation (avg: 84.0, min: 83.0)
    day1 = data["data"][0]
    assert day1["date"] == "2024-01-14"
    assert day1["avg_soh_percent"] == 84.0
    assert day1["min_soh_percent"] == 83.0

    # Verify Day 2 aggregation (avg: 80.0, min: 80.0)
    day2 = data["data"][1]
    assert day2["date"] == "2024-01-15"
    assert day2["avg_soh_percent"] == 80.0
    assert day2["min_soh_percent"] == 80.0


def test_degradation_endpoint_date_filtering(client, db_session):
    """GET /analytics/degradation filters output based on start_date and end_date."""
    # Setup database
    battery = Battery(
        battery_id="EV_B0005_001",
        vehicle_id="VH_TESLA_042",
        nominal_capacity_mah=2000.0,
    )
    db_session.add(battery)

    # 3 snapshots on 3 consecutive days
    dt1 = datetime(2024, 1, 14, 10, 0, 0, tzinfo=timezone.utc)
    dt2 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    dt3 = datetime(2024, 1, 16, 14, 0, 0, tzinfo=timezone.utc)

    snap1 = SoHSnapshot(
        battery_id="EV_B0005_001",
        snapshot_at=dt1,
        cycle_number=1,
        soh_percent=85.0,
        capacity_mah=1700.0,
    )
    snap2 = SoHSnapshot(
        battery_id="EV_B0005_001",
        snapshot_at=dt2,
        cycle_number=2,
        soh_percent=83.0,
        capacity_mah=1660.0,
    )
    snap3 = SoHSnapshot(
        battery_id="EV_B0005_001",
        snapshot_at=dt3,
        cycle_number=3,
        soh_percent=80.0,
        capacity_mah=1600.0,
    )

    db_session.add_all([snap1, snap2, snap3])
    db_session.commit()

    # Query only for 2024-01-15
    response = client.get(
        "/api/v1/analytics/degradation?battery_id=EV_B0005_001"
        "&start_date=2024-01-15&end_date=2024-01-15"
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["date"] == "2024-01-15"
    assert data["data"][0]["avg_soh_percent"] == 83.0


def test_degradation_endpoint_not_found(client):
    """GET /analytics/degradation returns 404 if battery is not registered."""
    response = client.get("/api/v1/analytics/degradation?battery_id=NON_EXISTING")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Battery not found"
