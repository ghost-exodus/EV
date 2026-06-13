from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth.dependencies import verify_jwt
from db.session import get_db
from routers import auth, fleet, ingest, telemetry, soh

app = FastAPI(
    title="EV Battery Telemetry & Diagnostics",
    description="Ingest, query, and analyse EV battery telemetry data.",
    version="1.0.0",
)

# ── Routers ──────────────────────────────────────────────────────────────────
# Authentication (unprotected)
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Core endpoints (requires verification, both fleet_admin and operator allowed)
app.include_router(ingest.router, prefix="/api/v1", tags=["Ingest"], dependencies=[Depends(verify_jwt)])
app.include_router(telemetry.router, prefix="/api/v1", tags=["Telemetry"], dependencies=[Depends(verify_jwt)])
app.include_router(soh.router, prefix="/api/v1", tags=["State of Health"], dependencies=[Depends(verify_jwt)])

# Fleet diagnostics (requires fleet_admin, handled via route-level dependency)
app.include_router(fleet.router, prefix="/api/v1", tags=["Fleet"])


@app.get("/health", tags=["Health"])
def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
def ready_check(db: Session = Depends(get_db)):
    """Readiness probe that checks database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "db": "connected"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not ready", "db": "disconnected"},
        )
