"""
GET /api/v1/rul/{battery_id} — Get Remaining Useful Life prediction details.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.models import Battery, RULPrediction, SoHSnapshot
from db.session import get_db
from models.schemas import RULResponse, ConfidenceInterval, ErrorResponse

router = APIRouter()


@router.get(
    "/rul/{battery_id}",
    response_model=RULResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get latest RUL prediction details for a battery",
)
def get_rul(battery_id: str, db: Session = Depends(get_db)):
    """
    Return the latest computed RUL prediction, confidence interval, and alert classification.
    Available to authenticated fleet_admin and operator users.

    If no RUL prediction has been computed yet (LSTM runs every 10th ingest),
    returns a graceful 200 with alert_level="none" and a diagnostic message.
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
        # Graceful fallback: battery exists but LSTM hasn't run yet
        # (matches the soh.py pattern of returning 200 + message)
        latest_soh = (
            db.query(SoHSnapshot)
            .filter(SoHSnapshot.battery_id == battery_id)
            .order_by(SoHSnapshot.cycle_number.desc())
            .first()
        )
        current_soh = float(latest_soh.soh_percent) if latest_soh else 100.0

        return RULResponse(
            battery_id=battery_id,
            predicted_rul_cycles=0,
            confidence_interval=ConfidenceInterval(
                lower_bound=0, upper_bound=0, confidence_percent=0.0
            ),
            current_soh_percent=current_soh,
            eol_threshold_soh=70.0,
            model_version="pending",
            predicted_at=datetime.now(timezone.utc),
            alert_level="none",
            message="No RUL prediction available yet — LSTM runs every 10th ingest",
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

