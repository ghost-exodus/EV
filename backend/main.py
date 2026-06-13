"""
EV Battery Telemetry & Diagnostics Platform — FastAPI application entry point.
"""

from fastapi import FastAPI

from routers import ingest, telemetry, soh

app = FastAPI(
    title="EV Battery Telemetry & Diagnostics",
    description="Ingest, query, and analyse EV battery telemetry data.",
    version="1.0.0",
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(ingest.router, prefix="/api/v1", tags=["Ingest"])
app.include_router(telemetry.router, prefix="/api/v1", tags=["Telemetry"])
app.include_router(soh.router, prefix="/api/v1", tags=["State of Health"])


@app.get("/health", tags=["Health"])
def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}
