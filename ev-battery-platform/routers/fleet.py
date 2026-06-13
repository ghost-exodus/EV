"""
Fleet Router — GET /api/v1/fleet/summary for admin diagnostics overview.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.dependencies import require_role
from db.models import Battery, SoHSnapshot, Telemetry
from db.session import get_db
from models.schemas import FleetSummaryResponse, FleetBatteryEntry, StatusSummary
from services.soh_service import get_soh_status

router = APIRouter()


@router.get(
    "/fleet/summary",
    response_model=FleetSummaryResponse,
    dependencies=[Depends(require_role("fleet_admin"))],
    summary="Get fleet battery diagnostic status summary",
)
def get_fleet_summary(db: Session = Depends(get_db)):
    """
    Query diagnostics summary across all batteries.
    Available to fleet_admin only.
    """
    # ── 1. Fetch latest SoH snapshot per battery ─────────────────────────
    subq_soh = (
        db.query(
            SoHSnapshot.battery_id,
            func.max(SoHSnapshot.cycle_number).label("max_cycle"),
        )
        .group_by(SoHSnapshot.battery_id)
        .subquery()
    )

    latest_soh = (
        db.query(
            SoHSnapshot.battery_id,
            SoHSnapshot.soh_percent,
            SoHSnapshot.capacity_mah,
        )
        .join(
            subq_soh,
            (SoHSnapshot.battery_id == subq_soh.c.battery_id)
            & (SoHSnapshot.cycle_number == subq_soh.c.max_cycle),
        )
        .subquery()
    )

    # ── 2. Fetch latest telemetry reading recorded_at per battery ──────────
    subq_tel = (
        db.query(
            Telemetry.battery_id,
            func.max(Telemetry.recorded_at).label("max_recorded"),
        )
        .group_by(Telemetry.battery_id)
        .subquery()
    )

    latest_tel = (
        db.query(Telemetry.battery_id, Telemetry.recorded_at)
        .join(
            subq_tel,
            (Telemetry.battery_id == subq_tel.c.battery_id)
            & (Telemetry.recorded_at == subq_tel.c.max_recorded),
        )
        .subquery()
    )

    # ── 3. Join Battery registry with subqueries ──────────────────────────
    results = (
        db.query(
            Battery.battery_id,
            Battery.vehicle_id,
            latest_soh.c.soh_percent,
            latest_tel.c.recorded_at,
        )
        .outerjoin(latest_soh, Battery.battery_id == latest_soh.c.battery_id)
        .outerjoin(latest_tel, Battery.battery_id == latest_tel.c.battery_id)
        .all()
    )

    # ── 4. Aggregate metrics ──────────────────────────────────────────────
    total_batteries = len(results)
    healthy_count = 0
    warning_count = 0
    critical_count = 0
    soh_sum = 0.0
    soh_count = 0

    battery_entries = []

    for r in results:
        soh_pct = float(r.soh_percent) if r.soh_percent is not None else None
        last_seen = r.recorded_at

        if soh_pct is not None:
            status = get_soh_status(soh_pct)
            soh_sum += soh_pct
            soh_count += 1
            if status == "healthy":
                healthy_count += 1
            elif status == "warning":
                warning_count += 1
            elif status == "critical":
                critical_count += 1
        else:
            status = "unknown"

        battery_entries.append(
            FleetBatteryEntry(
                battery_id=r.battery_id,
                vehicle_id=r.vehicle_id,
                current_soh_percent=soh_pct,
                predicted_rul_cycles=None,  # Placeholder for LSTM prediction in later milestones
                status=status,
                last_seen=last_seen,
            )
        )

    fleet_avg = round(soh_sum / soh_count, 1) if soh_count > 0 else None

    return FleetSummaryResponse(
        total_batteries=total_batteries,
        status_summary=StatusSummary(
            healthy=healthy_count,
            warning=warning_count,
            critical=critical_count,
        ),
        fleet_avg_soh_percent=fleet_avg,
        batteries=battery_entries,
    )
