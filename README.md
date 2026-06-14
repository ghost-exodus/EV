# EV Battery Telemetry & Diagnostics Platform

A FastAPI backend for ingesting, querying, and analysing EV battery telemetry data.  
Uses **PostgreSQL + TimescaleDB** for time-series storage, **ElasticMQ** for SQS FIFO queue emulation, and **Docker Compose** for orchestration.

---

## Architecture

```
                                  ┌─────────────┐
                                  │ EV Sim/AWS  │
                                  └─────────────┘
                                         │ SQS Message (Phase 2 FIFO)
                                         ▼
   ┌─────────────┐   HTTP Ingest   ┌───────────┐ (Polls)   ┌───────────┐
   │ Sim/Internal│ ──────────────▶ │  FastAPI  │ ◀──────── │ ElasticMQ │
   │ Client      │  (X-API-Key)    │  (8000)   │           └───────────┘
   └─────────────┘                 └───────────┘
                                         │
                                         ├─────▶ ┌──────────────────┐
                                         │       │ PostgreSQL       │
                                         │       │ + TimescaleDB    │
                                         │       │ (5432)           │
                                         │       └──────────────────┘
                                         ▼
                                  Background Tasks
                                  ➜ calculate_soh()
                                  ➜ predict_rul() (LSTM Inference every 10th message)
```

---

## Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
# Default environment parameters work out of the box.
```

### 2. Start Services
This starts PostgreSQL (TimescaleDB), FastAPI, and ElasticMQ (SQS simulator):
```bash
docker compose up -d --build
```

### 3. Run Database Migrations
```bash
docker compose exec fastapi alembic upgrade head
```

### 4. Verify API Readiness
```bash
# Health check (Liveness)
curl http://localhost:8000/health
# Response: {"status": "ok"}

# Readiness check (Checks database connectivity and SQS reachability)
curl http://localhost:8000/ready
# Response: {"status": "ready", "db": "connected", "sqs": "reachable"}
```

---

## API Endpoints

### 1. Ingest Telemetry (Internal Only)
* **Endpoint:** `POST /api/v1/ingest`
* **Headers:** `X-Internal-API-Key: super_secret_internal_api_key_123`
* **Response (202):** `{"ingested": true, "battery_id": "EV_B0005_001"}`
* **Example:**
```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-Internal-API-Key: super_secret_internal_api_key_123" \
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
    }
  }'
```

### 2. Get RUL Prediction (JWT Protected)
* **Endpoint:** `GET /api/v1/rul/{battery_id}`
* **Headers:** `Authorization: Bearer <JWT_TOKEN>`
* **Response (200):**
```json
{
  "battery_id": "EV_B0005_001",
  "predicted_rul_cycles": 213,
  "confidence_interval": {
    "lower_bound": 188,
    "upper_bound": 238,
    "confidence_percent": 90.0
  },
  "current_soh_percent": 82.4,
  "eol_threshold_soh": 70.0,
  "model_version": "v2.0",
  "predicted_at": "2024-01-15T14:20:00.000Z",
  "alert_level": "none"
}
```

### 3. Get Degradation Analytics (JWT Protected)
* **Endpoint:** `GET /api/v1/analytics/degradation`
* **Query Params:** `battery_id` (required), `start_date` (optional), `end_date` (optional)
* **Headers:** `Authorization: Bearer <JWT_TOKEN>`
* **Response (200):**
```json
{
  "battery_id": "EV_B0005_001",
  "data": [
    {"date": "2024-01-14", "avg_soh_percent": 83.2, "min_soh_percent": 82.9},
    {"date": "2024-01-15", "avg_soh_percent": 82.4, "min_soh_percent": 82.1}
  ]
}
```

### 4. Query Telemetry (JWT Protected)
* **Endpoint:** `GET /api/v1/telemetry/{battery_id}`
* **Query Params:** `limit` (optional), `cursor` (optional)
* **Response (200):** Lists telemetry entries using cursor-based pagination.

### 5. Get SOH Status (JWT Protected)
* **Endpoint:** `GET /api/v1/soh/{battery_id}`
* **Response (200):** Returns current SOH, state classification (healthy, warning, critical), and trend direction.

---

## AWS SQS FIFO Integration
* **Production Queue:** `ev-telemetry.fifo`
* **Production DLQ:** `ev-telemetry-dlq.fifo`
* **Processing Rule:** Telemetry parsing/validation errors are retried up to 3 times before routing to DLQ with an attached `Error` attribute.
* **Local Emulator Console:** SQS emulator admin UI is available at `http://localhost:9325`.

---

## Running Tests

Tests use an in-memory SQLite database (no external Docker dependency required):
```bash
# Locally with virtualenv
pip install -r requirements.txt
python -m pytest tests/ -v
```
