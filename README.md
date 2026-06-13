# EV Battery Telemetry & Diagnostics Platform

A FastAPI backend for ingesting, querying, and analysing EV battery telemetry data.  
Uses **PostgreSQL + TimescaleDB** for time-series storage and **Docker Compose** for orchestration.

## Architecture

```
┌────────────┐     POST /ingest      ┌───────────┐     ┌──────────────────┐
│  Simulator │ ────────────────────▶  │  FastAPI   │────▶│ PostgreSQL       │
│  / Client  │                        │  (8000)    │     │ + TimescaleDB    │
│            │ ◀──── GET /telemetry   │            │     │ (5432)           │
│            │ ◀──── GET /soh         │            │     │                  │
└────────────┘                        └───────────┘     └──────────────────┘
                                           │
                                      Background Task
                                      ➜ calculate_soh()
```

## Quick Start

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env if needed (defaults work out of the box)
```

### 2. Start services

```bash
docker compose up -d --build
```

### 3. Run database migrations

```bash
docker compose exec fastapi alembic upgrade head
```

### 4. Verify

```bash
# Health check
curl http://localhost:8000/health

# Should return: {"status": "ok"}
```

## API Endpoints

### POST /api/v1/ingest — Ingest telemetry reading

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": "1.0",
    "source": "ev_simulator_local",
    "battery_id": "EV_B0005_001",
    "vehicle_id": "VH_TESLA_042",
    "timestamp": "2024-01-15T14:23:45.123Z",
    "cycle_number": 147,
    "cycle_type": "discharge",
    "measurements": {
      "voltage_v": 3.8124,
      "current_a": -1.9987,
      "temperature_c": 24.5,
      "capacity_mah": 1823.4,
      "internal_resistance_ohm": 0.0214
    },
    "metadata": {
      "simulator_version": "1.0.0",
      "replay_speed": 1.0,
      "source_file": "B0005.csv"
    }
  }'

# Response (202):
# {"ingested": true, "battery_id": "EV_B0005_001"}
```

### GET /api/v1/telemetry/{battery_id} — Query readings

```bash
curl "http://localhost:8000/api/v1/telemetry/EV_B0005_001?limit=5"

# Response (200):
# {
#   "battery_id": "EV_B0005_001",
#   "total_records": 1,
#   "cursor": null,
#   "has_more": false,
#   "readings": [...]
# }
```

Pagination: pass the `cursor` value from a previous response to get the next page.

### GET /api/v1/soh/{battery_id} — State of Health

```bash
curl http://localhost:8000/api/v1/soh/EV_B0005_001

# Response (200):
# {
#   "battery_id": "EV_B0005_001",
#   "current_soh_percent": 91.17,
#   "status": "healthy",
#   "nominal_capacity_mah": 2000.0,
#   "current_capacity_mah": 1823.4,
#   "last_calculated_at": "2024-01-15T14:23:45.123000Z",
#   "trend": { ... }
# }
```

## Running Tests

Tests use an in-memory SQLite database (no Docker required):

```bash
# Inside the container
docker compose exec fastapi pytest tests/ -v

# Or locally with a virtual environment
pip install -r requirements.txt
pytest tests/ -v
```

## Project Structure

```
ev-battery-platform/
├── main.py                  # FastAPI app entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # FastAPI container
├── docker-compose.yml       # Postgres + FastAPI
├── .env / .env.example      # Environment variables
├── alembic.ini              # Alembic config
├── alembic/
│   ├── env.py               # Migration environment
│   └── versions/
│       └── 001_*.py         # Initial schema migration
├── db/
│   ├── models.py            # SQLAlchemy ORM models
│   └── session.py           # Engine + session factory
├── models/
│   └── schemas.py           # Pydantic request/response schemas
├── routers/
│   ├── ingest.py            # POST /api/v1/ingest
│   ├── telemetry.py         # GET /api/v1/telemetry/{battery_id}
│   └── soh.py               # GET /api/v1/soh/{battery_id}
├── services/
│   └── soh_service.py       # SoH calculation logic
└── tests/
    ├── conftest.py           # Test fixtures (SQLite)
    ├── test_ingest.py
    ├── test_telemetry.py
    └── test_soh.py
```

## Database Schema

- **batteries** — Master battery registry (battery_id, vehicle_id, nominal_capacity_mah, ...)
- **telemetry** — Raw streaming data, stored as a TimescaleDB hypertable partitioned by `recorded_at`
- **soh_snapshots** — Computed State-of-Health per cycle, with UNIQUE constraint on (battery_id, cycle_number)
