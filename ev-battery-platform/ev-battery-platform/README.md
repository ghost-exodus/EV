# EV Battery Telemetry & Diagnostics Platform

This repository contains the complete FastAPI + PostgreSQL/TimescaleDB backend for EV battery telemetry ingestion, diagnostics, and predictive analytics.

---

## Repository Structure

* **[ev-battery-platform/](file:///d:/open%20source/ev-battery-platform/)**: The core backend application, container configurations, migrations, and test suite.
* **[cleaned_dataset/](file:///d:/open%20source/cleaned_dataset/)**: Dataset directory (contains battery charge/discharge data such as `B0005.csv` used for simulator testing).

To run the application, navigate to the backend directory:
```bash
cd ev-battery-platform
```

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

## Quick Start (Backend)

Run these commands inside the `ev-battery-platform/` directory:

### 1. Configure Environment
```bash
cd ev-battery-platform
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

### 6. Get Fleet Summary (JWT Protected - fleet_admin Only)
* **Endpoint:** `GET /api/v1/fleet/summary`
* **Response (200):** Fleet overview diagnostics including active RUL calculations.

---

## AWS SQS FIFO Integration
* **Production Queue:** `ev-telemetry.fifo`
* **Production DLQ:** `ev-telemetry-dlq.fifo`
* **Processing Rule:** Telemetry parsing/validation errors are retried up to 3 times in-memory. On the 3rd fail, they are routed to the DLQ with an attached `Error` attribute and deleted from the main queue.
* **Local Emulator Console:** SQS emulator admin UI is available at `http://localhost:9325`.

---

## Production Hardening (Week 7)

### 1. Rate Limiting (`slowapi`)
Rate limiting is enforced globally at **100 requests/minute** per authenticated user on all `/api/v1/*` routes.
* **User Extraction**: Keys are bound to the JWT token's subject (`sub`/username) rather than client IP.
* **Exemptions**: Health checks (`/health`, `/ready`) and internal telemetry ingestion (`/api/v1/ingest`) are exempted.
* **Error Response**: Rejections return HTTP `429 Too Many Requests` with a JSON payload: `{"error": "Rate limit exceeded", "retry_after_seconds": X}` and a `Retry-After` header.

### 2. Structured JSON Logging (`structlog`)
All application logs are printed in JSON format to `stdout` for compatibility with modern log routers.
* **Request Middleware**: Logs every processed request with method, path, HTTP status, duration (ms), and authenticated user.
* **Ingestion Metrics**: Ingestion workflows log combined write and SoH calculation latency (`latency_ms`), battery ID, cycle, and source (`http`/`poller`).

### 3. TimescaleDB Compression Policy
TimescaleDB data compression is enabled on the `telemetry` table. Chunks are ordered by `recorded_at DESC` and segmented by `battery_id`.
* An automated database compression policy compresses telemetry records older than **7 days**.

### 4. JWT Key Rotation & Token Refresh
* **Key Rotation**: Archive older RSA public keys under `previous_keys/`. The authentication module scans this folder to allow previously-signed tokens to validate successfully.
* **Token Reissue**: Call `POST /auth/refresh` with a valid active access token to receive a re-signed token.
* **Manual Rotation**: Run the rotation script:
  ```bash
  python scripts/rotate_keys.py
  ```

---

## Verification & Load Testing (Week 8)

### 1. Running Tests
The Python unit/integration tests run against an in-memory SQLite database:
```bash
cd ev-battery-platform
pip install -r requirements.txt
python -m pytest tests/ -v
```

### 2. Backup & Restore Validation
Simulate PostgreSQL/TimescaleDB backup and restoration using `pg_dump`, execute TimescaleDB restore pre-hooks and post-hooks, and verify row count synchronization:
```bash
# On Linux/macOS
./scripts/backup_restore_test.sh

# On Windows (PowerShell)
powershell -File ./scripts/backup_restore_test.ps1
```

### 3. Performance Benchmark (Load Testing)
Simulate a concurrent load of **50 RPS for 60 seconds (3,000 total requests)** with a weighted, read-heavy API distribution (15% Ingest, 25% Telemetry, 20% SoH, 15% RUL, 15% Degradation, 10% Fleet Summary) to assert performance SLAs (p95 < 150ms, p99 < 300ms, 0% failure rate):
```bash
python scripts/perf_test.py
```

