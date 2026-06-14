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


def _calculate_soh_with_session(battery_id: str, db: Session) -> float | None:
    """Core logic — separated so tests can inject their own session."""

    import logging
    logger = logging.getLogger("soh_service")

    # ── Get nominal capacity ─────────────────────────────────────────────
    battery = db.query(Battery).filter(Battery.battery_id == battery_id).first()
    if battery is None:
        return None  # nothing to compute

    nominal = float(battery.nominal_capacity_mah)
    if nominal <= 0:
        return None

    # ── Get latest telemetry reading ─────────────────────────────────────
    latest_reading = (
        db.query(Telemetry)
        .filter(Telemetry.battery_id == battery_id)
        .order_by(desc(Telemetry.recorded_at))
        .first()
    )
    if latest_reading is None:
        logger.info(f"Skipping SoH calc for {battery_id} — no telemetry records found")
        return None

    if latest_reading.capacity_mah is None:
        logger.info(f"Skipping SoH calc for {battery_id} — no capacity_mah yet")
        return None

    current_capacity = float(latest_reading.capacity_mah)
    soh_percent = round((current_capacity / nominal) * 100, 2)

    # ── Upsert into soh_snapshots ────────────────────────────────────────
    # Use PostgreSQL ON CONFLICT DO UPDATE to eliminate the TOCTOU race
    # condition that occurred with the old select-then-insert pattern under
    # concurrent ingestion for the same (battery_id, cycle_number).
    try:
        dialect = db.bind.dialect.name if db.bind else "unknown"
    except Exception:
        dialect = "unknown"

    if dialect == "postgresql":
        # Atomic upsert — safe under concurrent writes
        stmt = pg_insert(SoHSnapshot).values(
            battery_id=battery_id,
            snapshot_at=latest_reading.recorded_at,
            cycle_number=latest_reading.cycle_number,
            soh_percent=soh_percent,
            capacity_mah=current_capacity,
        ).on_conflict_do_update(
            constraint="uq_soh_battery_cycle",
            set_={
                "snapshot_at": latest_reading.recorded_at,
                "soh_percent": soh_percent,
                "capacity_mah": current_capacity,
            },
        )
        db.execute(stmt)
    else:
        # SQLite fallback for unit tests (no ON CONFLICT support via pg_insert)
        from sqlalchemy.exc import IntegrityError
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
    return soh_percent
