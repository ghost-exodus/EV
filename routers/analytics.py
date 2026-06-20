"""
GET /api/v1/analytics/degradation — Battery health degradation analytics.
"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, Date, cast
from sqlalchemy.orm import Session

from db.models import Battery, SoHSnapshot
from db.session import get_db
from models.schemas import DegradationResponse, DegradationEntry, ErrorResponse

router = APIRouter()


@router.get(
    "/analytics/degradation",
    response_model=DegradationResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get daily battery health degradation metrics",
)
def get_degradation(
    battery_id: str = Query(..., description="Battery ID to query"),
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    Return daily average and minimum State of Health (SoH) for a battery.
    Supports filtering by date range.
    """
    # 1. Verify battery registry entry exists
    battery = db.query(Battery).filter(Battery.battery_id == battery_id).first()
    if not battery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Battery not found"},
        )

    # 2. Query snapshots grouped by day
    day_col = func.date(SoHSnapshot.snapshot_at).label("day")
    query = (
        db.query(
            day_col,
            func.avg(SoHSnapshot.soh_percent).label("avg_soh"),
            func.min(SoHSnapshot.soh_percent).label("min_soh"),
        )
        .filter(SoHSnapshot.battery_id == battery_id)
    )

    # Database-side date casting for safe timezone comparison
    if start_date:
        query = query.filter(func.date(SoHSnapshot.snapshot_at) >= start_date)
    if end_date:
        query = query.filter(func.date(SoHSnapshot.snapshot_at) <= end_date)


    query = query.group_by(day_col).order_by("day")
    results = query.all()

    # 3. Format results into response shape
    data = [
        DegradationEntry(
            date=str(row.day),
            avg_soh_percent=round(float(row.avg_soh), 2),
            min_soh_percent=round(float(row.min_soh), 2),
        )
        for row in results
        if row.day is not None
    ]

    return DegradationResponse(battery_id=battery_id, data=data)
