"""
Integration tests for the EV Battery Telemetry & Diagnostics Platform.
Verifies the end-to-end data pipeline running against a live Postgres/TimescaleDB.
"""

import os
import time
import pytest
import httpx
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Battery, Telemetry, SoHSnapshot

# ── Configuration ────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DATABASE_URL = os.getenv(
    "INTEGRATION_DB_URL",
    "postgresql://ev_user:ev_password@localhost:5432/ev_telemetry",
)

UNIQUE_BATTERY_ID = "EV_INTEG_BATT_999"
UNIQUE_VEHICLE_ID = "VH_INTEG_VEHICLE_999"


@pytest.fixture(scope="module")
def db_engine():
    """Create engine to connect to the live PostgreSQL/TimescaleDB database."""
    # Ensure psycopg2 is installed or fall back gracefully with a message
    try:
        engine = create_engine(DATABASE_URL)
        # Try connection
        with engine.connect() as conn:
            pass
        return engine
    except Exception as e:
        pytest.skip(
            f"Skipping integration tests: Cannot connect to DB at {DATABASE_URL}. Error: {e}"
        )


@pytest.fixture(scope="module")
def api_client():
    """Create HTTPX client for calling the live API."""
    # Verify API is reachable
    try:
        with httpx.Client(base_url=API_BASE_URL) as client:
            resp = client.get("/health")
            if resp.status_code != 200:
                raise RuntimeError("API returned non-200")
            return client
    except Exception as e:
        pytest.skip(
            f"Skipping integration tests: API is not running at {API_BASE_URL}. Error: {e}"
        )


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Authenticate and return an access token for admin."""
    resp = api_client.post(
        "/auth/token",
        data={"username": "admin", "password": "secret"},
    )
    assert resp.status_code == 200, "Could not authenticate admin user"
    return resp.json()["access_token"]


def test_integration_pipeline(db_engine, api_client, admin_token):
    """
    E2E Pipeline Test:
    1. Clean up any previous test battery.
    2. POST telemetry ingest payloads for the battery.
    3. Assert rows are written in the database tables.
    4. Assert SoH recalculation background task successfully updates soh_snapshots.
    5. GET telemetry and GET SoH endpoints and assert shapes/contents.
    """
    # ── 1. DB Cleanup ────────────────────────────────────────────────────────
    Session = sessionmaker(bind=db_engine)
    with Session() as session:
        # Delete existing test telemetry and snapshots
        session.query(SoHSnapshot).filter_by(
            battery_id=UNIQUE_BATTERY_ID
        ).delete()
        session.query(Telemetry).filter_by(battery_id=UNIQUE_BATTERY_ID).delete()
        session.query(Battery).filter_by(battery_id=UNIQUE_BATTERY_ID).delete()
        session.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}

    # ── 2. Ingest Multiple Telemetry Readings ────────────────────────────────
    readings = [
        {"cycle": 10, "volts": 3.9, "current": -2.0, "temp": 25.0, "cap": 1950.0},
        {"cycle": 11, "volts": 3.8, "current": -2.0, "temp": 26.0, "cap": 1930.0},
        {"cycle": 12, "volts": 3.75, "current": -2.0, "temp": 27.0, "cap": 1900.0},
    ]

    for r in readings:
        payload = {
            "schema_version": "1.0",
            "source": "integration_test",
            "battery_id": UNIQUE_BATTERY_ID,
            "vehicle_id": UNIQUE_VEHICLE_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle_number": r["cycle"],
            "cycle_type": "discharge",
            "measurements": {
                "voltage_v": r["volts"],
                "current_a": r["current"],
                "temperature_c": r["temp"],
                "capacity_mah": r["cap"],
            },
        }
        resp = api_client.post("/api/v1/ingest", json=payload, headers=headers)
        assert resp.status_code == 202
        assert resp.json()["ingested"] is True

    # ── 3. Assert Rows Appear in DB (wait and poll for background task) ──────
    db_ok = False
    for attempt in range(5):
        time.sleep(0.5)  # wait for background task to execute
        with Session() as session:
            telemetry_count = (
                session.query(Telemetry)
                .filter_by(battery_id=UNIQUE_BATTERY_ID)
                .count()
            )
            snapshot_count = (
                session.query(SoHSnapshot)
                .filter_by(battery_id=UNIQUE_BATTERY_ID)
                .count()
            )

            # We ingested 3 readings, so we expect 3 telemetry rows and up to 3 snapshots
            if telemetry_count == 3 and snapshot_count >= 1:
                db_ok = True
                break

    assert db_ok, "Telemetry or SoH snapshots failed to populate in database within timeout"

    # Verify database contents
    with Session() as session:
        # Check battery registry exists and nominal capacity is defaulted
        battery = (
            session.query(Battery).filter_by(battery_id=UNIQUE_BATTERY_ID).first()
        )
        assert battery is not None
        assert float(battery.nominal_capacity_mah) == 2000.0

        # Check latest snapshot values (SoH: 1900 / 2000 * 100 = 95.0%)
        latest_snapshot = (
            session.query(SoHSnapshot)
            .filter_by(battery_id=UNIQUE_BATTERY_ID)
            .order_by(SoHSnapshot.cycle_number.desc())
            .first()
        )
        assert latest_snapshot.cycle_number == 12
        assert float(latest_snapshot.soh_percent) == 95.0
        assert float(latest_snapshot.capacity_mah) == 1900.0

    # ── 4. Verify API GET Endpoints ──────────────────────────────────────────
    # GET Telemetry
    tel_resp = api_client.get(
        f"/api/v1/telemetry/{UNIQUE_BATTERY_ID}", headers=headers
    )
    assert tel_resp.status_code == 200
    tel_data = tel_resp.json()
    assert tel_data["battery_id"] == UNIQUE_BATTERY_ID
    assert tel_data["total_records"] == 3
    assert len(tel_data["readings"]) == 3
    assert tel_data["readings"][0]["cycle_number"] == 12  # desc sorted

    # GET SoH
    soh_resp = api_client.get(
        f"/api/v1/soh/{UNIQUE_BATTERY_ID}", headers=headers
    )
    assert soh_resp.status_code == 200
    soh_data = soh_resp.json()
    assert soh_data["battery_id"] == UNIQUE_BATTERY_ID
    assert soh_data["current_soh_percent"] == 95.0
    assert soh_data["status"] == "healthy"
    assert len(soh_data["trend"]["history"]) >= 1

    # ── 5. Clean up DB after successful run ─────────────────────────────────
    with Session() as session:
        session.query(SoHSnapshot).filter_by(
            battery_id=UNIQUE_BATTERY_ID
        ).delete()
        session.query(Telemetry).filter_by(battery_id=UNIQUE_BATTERY_ID).delete()
        session.query(Battery).filter_by(battery_id=UNIQUE_BATTERY_ID).delete()
        session.commit()
    print("Integration tests completed successfully.")
