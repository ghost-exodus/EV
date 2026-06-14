"""
GET /api/v1/soh/{battery_id} — State-of-Health endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.models import Battery, SoHSnapshot
from db.session import get_db
from models.schemas import SoHResponse, SoHTrend, SoHTrendEntry, ErrorResponse
from services.soh_service import get_soh_status

router = APIRouter()


@router.get(
    "/soh/{battery_id}",
    response_model=SoHResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get State-of-Health for a battery",
)
def get_soh(
    battery_id: str,
    db: Session = Depends(get_db),
):
    """
    Return the current SoH, status classification, and trend over
    the last 10 charge/discharge cycles.
    """
    # ── Verify battery exists ────────────────────────────────────────────
    battery = db.query(Battery).filter(Battery.battery_id == battery_id).first()
    if battery is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Battery not found"},
        )

    # ── Fetch last 10 SoH snapshots ─────────────────────────────────────
    snapshots = (
        db.query(SoHSnapshot)
        .filter(SoHSnapshot.battery_id == battery_id)
        .order_by(SoHSnapshot.cycle_number.desc())
        .limit(10)
        .all()
    )

    if not snapshots:
        battery = db.query(Battery).filter(Battery.battery_id == battery_id).first()
        if battery is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Battery not found"},
            )
        return SoHResponse(
            battery_id=battery_id,
            current_soh_percent=None,
            status="unknown",
            nominal_capacity_mah=float(battery.nominal_capacity_mah),
            current_capacity_mah=None,
            last_calculated_at=None,
            trend=None,
            message="No SoH data available yet — capacity_mah not received"
        )

    # Latest snapshot is first (desc order)
    latest = snapshots[0]
    oldest_in_window = snapshots[-1]

    current_soh = float(latest.soh_percent)
    status_label = get_soh_status(current_soh)

    # ── Trend calculation ────────────────────────────────────────────────
    delta = float(latest.soh_percent) - float(oldest_in_window.soh_percent)

    if delta < -0.1:
        direction = "degrading"
    elif delta > 0.1:
        direction = "improving"
    else:
        direction = "stable"

    # History in ascending cycle order for the response
    history = [
        SoHTrendEntry(
            cycle=s.cycle_number,
            soh_percent=float(s.soh_percent),
            snapshot_at=s.snapshot_at,
        )
        for s in reversed(snapshots)
    ]

    return SoHResponse(
        battery_id=battery_id,
        current_soh_percent=current_soh,
        status=status_label,
        nominal_capacity_mah=float(battery.nominal_capacity_mah),
        current_capacity_mah=float(latest.capacity_mah),
        last_calculated_at=latest.snapshot_at,
        trend=SoHTrend(
            direction=direction,
            delta_last_10_cycles=round(delta, 2),
            history=history,
        ),
    )
