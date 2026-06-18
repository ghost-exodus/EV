"""
GET /api/v1/telemetry/{battery_id} — Query telemetry readings with cursor-based pagination.
"""

import base64
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import Battery, Telemetry
from db.session import get_db
from models.schemas import TelemetryReading, TelemetryResponse, ErrorResponse

router = APIRouter()

cursor_logger = logging.getLogger("telemetry_cursor")


def _decode_cursor(cursor: str | None, battery_id: str) -> int | None:
    """Decode a base64-encoded cursor into the last seen id.
    
    Validates that the cursor's embedded battery_id matches the requested
    battery_id. Returns None (page 1 reset) on mismatch or any parse error.
    """
    if cursor is None:
        return None
    try:
        decoded = base64.b64decode(cursor)
        data = json.loads(decoded)
        cursor_bid = data.get("bid")
        if cursor_bid and cursor_bid != battery_id:
            cursor_logger.warning(
                f"Cross-battery cursor rejected: cursor battery_id={cursor_bid!r} "
                f"vs requested battery_id={battery_id!r}"
            )
            return None
        return int(data["last_id"])
    except Exception:
        return None


def _encode_cursor(last_id: int, battery_id: str) -> str:
    """Encode the last seen id and battery_id into a base64 cursor."""
    payload = json.dumps({"last_id": last_id, "bid": battery_id})
    return base64.b64encode(payload.encode()).decode()


@router.get(
    "/telemetry/{battery_id}",
    response_model=TelemetryResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Query telemetry readings for a battery",
)
def get_telemetry(
    battery_id: str,
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return telemetry readings with cursor-based pagination.

    - `limit`: number of records per page (max 1000)
    - `cursor`: base64-encoded cursor from a previous response
    """
    # ── Verify battery exists ────────────────────────────────────────────
    battery = db.query(Battery).filter(Battery.battery_id == battery_id).first()
    if battery is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Battery not found"},
        )

    # ── Total record count ───────────────────────────────────────────────
    total_records = (
        db.query(func.count(Telemetry.id))
        .filter(Telemetry.battery_id == battery_id)
        .scalar()
    )

    # ── Query with cursor ────────────────────────────────────────────────
    query = (
        db.query(Telemetry)
        .filter(Telemetry.battery_id == battery_id)
        .order_by(Telemetry.id.desc())
    )

    last_id = _decode_cursor(cursor, battery_id)
    if last_id is not None:
        query = query.filter(Telemetry.id < last_id)

    rows = query.limit(limit + 1).all()  # fetch one extra to check has_more

    has_more = len(rows) > limit
    rows = rows[:limit]

    # ── Build response ───────────────────────────────────────────────────
    readings = [
        TelemetryReading(
            id=r.id,
            recorded_at=r.recorded_at,
            cycle_number=r.cycle_number,
            cycle_type=r.cycle_type,
            voltage_v=float(r.voltage_v),
            current_a=float(r.current_a),
            temperature_c=float(r.temperature_c),
            capacity_mah=float(r.capacity_mah) if r.capacity_mah else None,
        )
        for r in rows
    ]

    next_cursor = _encode_cursor(rows[-1].id, battery_id) if has_more and rows else None

    return TelemetryResponse(
        battery_id=battery_id,
        total_records=total_records,
        cursor=next_cursor,
        has_more=has_more,
        readings=readings,
    )
