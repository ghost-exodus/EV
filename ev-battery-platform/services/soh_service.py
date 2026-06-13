"""
SoH (State of Health) calculation service.

Computes SoH as a percentage of current capacity vs. nominal capacity,
and upserts the result into the soh_snapshots table.
"""

from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from db.models import Battery, SoHSnapshot, Telemetry
from db.session import SessionLocal


def get_soh_status(soh_percent: float) -> str:
    """Classify SoH percentage into a status label."""
    if soh_percent >= 80:
        return "healthy"
    elif soh_percent >= 60:
        return "warning"
    else:
        return "critical"


def calculate_soh(battery_id: str) -> None:
    """
    Compute the current State-of-Health for a battery and upsert
    the result into soh_snapshots.

    This function creates its own DB session so it can run safely
    as a FastAPI BackgroundTask (which executes after the response
    is sent and the request session is closed).
    """
    db: Session = SessionLocal()
    try:
        _calculate_soh_with_session(battery_id, db)
    finally:
        db.close()


def _calculate_soh_with_session(battery_id: str, db: Session) -> None:
    """Core logic — separated so tests can inject their own session."""

    # ── Get nominal capacity ─────────────────────────────────────────────
    battery = db.query(Battery).filter(Battery.battery_id == battery_id).first()
    if battery is None:
        return  # nothing to compute

    nominal = float(battery.nominal_capacity_mah)
    if nominal <= 0:
        return

    # ── Get latest telemetry reading ─────────────────────────────────────
    latest_reading = (
        db.query(Telemetry)
        .filter(Telemetry.battery_id == battery_id)
        .order_by(desc(Telemetry.recorded_at))
        .first()
    )
    if latest_reading is None or latest_reading.capacity_mah is None:
        return

    current_capacity = float(latest_reading.capacity_mah)
    soh_percent = round((current_capacity / nominal) * 100, 2)

    # ── Upsert into soh_snapshots (database-agnostic select-then-update) ──
    existing = (
        db.query(SoHSnapshot)
        .filter(
            SoHSnapshot.battery_id == battery_id,
            SoHSnapshot.cycle_number == latest_reading.cycle_number,
        )
        .first()
    )
    if existing:
        existing.snapshot_at = latest_reading.recorded_at
        existing.soh_percent = soh_percent
        existing.capacity_mah = current_capacity
    else:
        snapshot = SoHSnapshot(
            battery_id=battery_id,
            snapshot_at=latest_reading.recorded_at,
            cycle_number=latest_reading.cycle_number,
            soh_percent=soh_percent,
            capacity_mah=current_capacity,
        )
        db.add(snapshot)

    db.commit()
