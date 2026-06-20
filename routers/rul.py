"""
GET /api/v1/rul/{battery_id} — Get Remaining Useful Life prediction details.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.models import Battery, RULPrediction
from db.session import get_db
from models.schemas import RULResponse, RULPendingResponse, ConfidenceInterval, ErrorResponse

router = APIRouter()


@router.get(
    "/rul/{battery_id}",
    response_model=RULResponse | RULPendingResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get latest RUL prediction details for a battery",
)
def get_rul(battery_id: str, db: Session = Depends(get_db)):
    """
    Return the latest computed RUL prediction, confidence interval, and alert classification.
    Available to authenticated fleet_admin and operator users.

    Returns a 200 with status="pending" if the battery exists but no prediction
    has been computed yet (e.g. fewer than 10 telemetry messages ingested).
    """
    # 1. Check if battery registry entry exists
    battery = db.query(Battery).filter(Battery.battery_id == battery_id).first()
    if not battery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Battery not found"},
        )

    # 2. Query latest prediction
    pred = (
        db.query(RULPrediction)
        .filter(RULPrediction.battery_id == battery_id)
        .order_by(RULPrediction.predicted_at.desc())
        .first()
    )
    if not pred:
        # Battery exists but no prediction yet — return 200 with pending status
        return RULPendingResponse(
            battery_id=battery_id,
            status="pending",
            message="RUL prediction not yet available — insufficient telemetry data ingested.",
        )

    # 3. Calculate alert level
    soh = float(pred.input_soh_percent) if pred.input_soh_percent is not None else 100.0
    if soh >= 70.0:
        alert_level = "none"
    elif soh >= 65.0:
        alert_level = "warning"
    else:
        alert_level = "critical"

    return RULResponse(
        battery_id=battery_id,
        status="ready",
        predicted_rul_cycles=pred.predicted_rul_cycles,
        confidence_interval=ConfidenceInterval(
            lower_bound=pred.confidence_lower or 0,
            upper_bound=pred.confidence_upper or 0,
            confidence_percent=90.0,
        ),
        current_soh_percent=soh,
        eol_threshold_soh=70.0,
        model_version=pred.model_version,
        predicted_at=pred.predicted_at,
        alert_level=alert_level,
    )

