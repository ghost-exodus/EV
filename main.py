import asyncio
from contextlib import asynccontextmanager
import logging
import os
import time
import structlog
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

# Configure structlog globally to output JSON
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

request_logger = structlog.get_logger().bind(logger="request")
from auth.dependencies import verify_jwt
from auth.limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from db.session import get_db
from routers import auth, fleet, ingest, telemetry, soh, rul, analytics
from services.sqs_poller import init_queues, poll_loop, get_sqs_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    testing = os.getenv("TESTING", "false").lower() == "true"
    stop_event = asyncio.Event()
    poll_task = None

    if not testing:
        # Startup: auto-create queues in dev and run polling loop
        init_queues()

        queue_url = os.getenv("SQS_QUEUE_URL")
        dlq_url = os.getenv("SQS_DLQ_URL")

        if queue_url and dlq_url:
            poll_task = asyncio.create_task(poll_loop(queue_url, dlq_url, stop_event))
            app.state.sqs_poll_task = poll_task
            app.state.sqs_stop_event = stop_event
            logger.info("SQS Poller task spawned successfully.")
        else:
            logger.warning("SQS environment variables not set. Poller loop skipped.")

    yield

    # Shutdown: cleanly signal stop and wait for poller task
    if poll_task:
        logger.info("Stopping SQS Poller task...")
        stop_event.set()
        try:
            await asyncio.wait_for(poll_task, timeout=10.0)
            logger.info("SQS Poller stopped successfully.")
        except asyncio.TimeoutError:
            logger.warning("Timeout occurred while stopping SQS Poller.")
        except Exception as e:
            logger.error(f"Error while stopping SQS Poller: {e}")



app = FastAPI(
    title="EV Battery Telemetry & Diagnostics",
    description="Ingest, query, and analyse EV battery telemetry data.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    user = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            from auth.jwt_handler import decode_token
            payload = decode_token(token)
            user = payload.get("sub")
        except Exception:
            pass

    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    request_logger.info(
        "request_processed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
        user=user,
    )
    return response


@app.exception_handler(RateLimitExceeded)
def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    retry_after = getattr(exc, "retry_after", 60)
    if retry_after is None:
        retry_after = 60
    else:
        retry_after = int(retry_after)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "Rate limit exceeded",
            "retry_after_seconds": retry_after
        },
        headers={"Retry-After": str(retry_after)}
    )


# ── Routers ──────────────────────────────────────────────────────────────────
# Authentication (unprotected)
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Core endpoints
# Ingest is now internally verified using API Key (no verify_jwt constraint at router level)
app.include_router(ingest.router, prefix="/api/v1", tags=["Ingest"])
app.include_router(telemetry.router, prefix="/api/v1", tags=["Telemetry"], dependencies=[Depends(verify_jwt)])
app.include_router(soh.router, prefix="/api/v1", tags=["State of Health"], dependencies=[Depends(verify_jwt)])
app.include_router(rul.router, prefix="/api/v1", tags=["RUL Predictions"], dependencies=[Depends(verify_jwt)])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"], dependencies=[Depends(verify_jwt)])

# Fleet diagnostics (requires fleet_admin, handled via route-level dependency)
app.include_router(fleet.router, prefix="/api/v1", tags=["Fleet"])


@app.get("/health", tags=["Health"])
@limiter.exempt
def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
@limiter.exempt
def ready_check(db: Session = Depends(get_db)):
    """Readiness probe that checks database connectivity and SQS queue status."""
    db_connected = False
    sqs_reachable = False

    # 1. Database check
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    # 2. SQS check
    queue_url = os.getenv("SQS_QUEUE_URL")
    if not queue_url:
        sqs_reachable = False
    else:
        try:
            sqs = get_sqs_client()
            sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
            sqs_reachable = True
        except Exception:
            sqs_reachable = False

    # Return 200 if ready
    if db_connected and sqs_reachable:
        return {
            "status": "ready",
            "db": "connected",
            "sqs": "reachable",
        }

    # Otherwise return 503 Service Unavailable
    db_status = "connected" if db_connected else "disconnected"
    sqs_status = "reachable" if sqs_reachable else "unreachable"

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "status": "not ready",
            "db": db_status,
            "sqs": sqs_status,
        },
    )

