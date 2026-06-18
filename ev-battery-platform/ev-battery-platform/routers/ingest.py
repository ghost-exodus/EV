"""
POST /api/v1/ingest — Battery telemetry ingestion endpoint (Internal Only).
"""

import os
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_db
from models.schemas import IngestPayload, IngestResponse, ErrorResponse
from services.ingest_service import ingest_telemetry_shared
from auth.limiter import limiter

router = APIRouter()


def verify_internal_key(
    x_internal_api_key: str = Header(None, alias="X-Internal-API-Key")
) -> None:
    """
    Ensure the request contains the correct internal API key.
    Raises 403 Forbidden if missing or incorrect.
    """
    expected_key = os.getenv("INTERNAL_API_KEY")
    if not expected_key or x_internal_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing internal API key",
        )


@router.post(
    "/ingest",
    response_model=IngestResponse,
    responses={403: {"model": ErrorResponse}},
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_internal_key)],
    summary="Ingest a single telemetry reading (internal only)",
)
@limiter.exempt
def ingest_telemetry(
    payload: IngestPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Validate and persist a telemetry reading via HTTP.
    Requires the 'X-Internal-API-Key' header.
    """
    battery_id = ingest_telemetry_shared(payload, db, background_tasks)
    return IngestResponse(ingested=True, battery_id=battery_id)
