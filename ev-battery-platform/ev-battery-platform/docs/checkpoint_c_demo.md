# Checkpoint C: Pivot Gate Demo Run-Sheet

This run-sheet contains the exact `curl` commands needed to demonstrate the full Phase 1 capability of the EV Battery Telemetry platform. 

Make sure the Docker services are running: `docker compose up -d` before starting.

---

## 1. Health and Readiness Checks (Public)

### GET `/health`
Verify that the service is alive.
```bash
curl -X GET http://localhost:8000/health
```
* **Expected Code**: `200 OK`
* **Expected Response**: `{"status": "ok"}`

### GET `/ready`
Verify that the service has connected to PostgreSQL/TimescaleDB.
```bash
curl -X GET http://localhost:8000/ready
```
* **Expected Code**: `200 OK`
* **Expected Response**: `{"status": "ready", "db": "connected"}`

---

## 2. Authentication & Token Issuance

### Login as `fleet_admin`
```bash
curl -X POST http://localhost:8000/auth/token \
  -F "username=admin" \
  -F "password=secret"
```
* **Expected Code**: `200 OK`
* **Expected Response**: Returns a valid signed JWT with role `fleet_admin`.
* **Action**: Save the `access_token` to `ADMIN_TOKEN` environment variable.

### Login as `operator`
```bash
curl -X POST http://localhost:8000/auth/token \
  -F "username=operator" \
  -F "password=secret"
```
* **Expected Code**: `200 OK`
* **Expected Response**: Returns a valid signed JWT with role `operator`.
* **Action**: Save the `access_token` to `OPERATOR_TOKEN` environment variable.

### Login with Invalid Credentials
```bash
curl -i -X POST http://localhost:8000/auth/token \
  -F "username=admin" \
  -F "password=wrongpassword"
```
* **Expected Code**: `401 Unauthorized`
* **Expected Response**: `{"detail": "Incorrect username or password"}`

---

## 3. Protected Telemetry Ingestion (Both Roles Allowed)

Let's ingest 10 telemetry readings for a new battery `EV_DEMO_001` using the `operator` token.
Replace `$OPERATOR_TOKEN` with the operator token value.

```bash
# Ingest 10 sequential cycles
for i in {1..10}; do
  capacity=$((2000 - i * 15)) # Degrade slightly each cycle
  curl -s -X POST http://localhost:8000/api/v1/ingest \
    -H "Authorization: Bearer $OPERATOR_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"schema_version\": \"1.0\",
      \"source\": \"manual_curl_demo\",
      \"battery_id\": \"EV_DEMO_001\",
      \"vehicle_id\": \"VH_FORD_F150\",
      \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",
      \"cycle_number\": $i,
      \"cycle_type\": \"discharge\",
      \"measurements\": {
        \"voltage_v\": 3.82,
        \"current_a\": -2.1,
        \"temperature_c\": 26.5,
        \"capacity_mah\": $capacity
      }
    }"
  echo " - Cycle $i response status above"
done
```
* **Expected Code**: `202 Accepted` x10
* **Expected Response**: `{"ingested": true, "battery_id": "EV_DEMO_001"}`

---

## 4. Telemetry Query & Cursor Pagination

Query the ingested telemetry. Let's ask for a limit of 3 to show pagination:
```bash
curl -X GET "http://localhost:8000/api/v1/telemetry/EV_DEMO_001?limit=3" \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
```
* **Expected Code**: `200 OK`
* **Expected Response**:
  - `total_records`: `10`
  - `has_more`: `true`
  - `cursor`: A base64 string
  - `readings`: List of 3 telemetry readings (descending order, starting with cycle 10)

To retrieve the next page, query with the cursor returned:
```bash
# Replace CURSOR_VAL with the cursor string from the previous response
curl -X GET "http://localhost:8000/api/v1/telemetry/EV_DEMO_001?limit=3&cursor=CURSOR_VAL" \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
```

---

## 5. State of Health (SoH) Diagnostics

Wait 1 second for the background calculation task to write to the DB, then query SoH:
```bash
curl -X GET http://localhost:8000/api/v1/soh/EV_DEMO_001 \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
```
* **Expected Code**: `200 OK`
* **Expected Response**:
  - `current_soh_percent`: `92.5` (since cycle 10 capacity was 1850 mAh; 1850 / 2000 * 100 = 92.5)
  - `status`: `"healthy"`
  - `trend`: `{"direction": "degrading", "delta_last_10_cycles": -6.75, "history": [...]}` (shows trend over the 10 cycles we ingested)

---

## 6. Fleet Diagnostics & RBAC Restriction

### Call as `operator` (Should Fail)
Operators are restricted from fleet-wide diagnostics.
```bash
curl -i -X GET http://localhost:8000/api/v1/fleet/summary \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
```
* **Expected Code**: `403 Forbidden`
* **Expected Response**: `{"detail": "Forbidden: insufficient permissions for this operation"}`

### Call as `fleet_admin` (Should Succeed)
Admins have access to fleet overview.
```bash
curl -X GET http://localhost:8000/api/v1/fleet/summary \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```
* **Expected Code**: `200 OK`
* **Expected Response**:
  ```json
  {
    "total_batteries": 1,
    "status_summary": {
      "healthy": 1,
      "warning": 0,
      "critical": 0
    },
    "fleet_avg_soh_percent": 92.5,
    "batteries": [
      {
        "battery_id": "EV_DEMO_001",
        "vehicle_id": "VH_FORD_F150",
        "current_soh_percent": 92.5,
        "predicted_rul_cycles": null,
        "status": "healthy",
        "last_seen": "2026-..."
      }
    ]
  }
  ```

---

## 7. Error Handling & Validation Rules

### Query a Non-Existent Battery (404)
```bash
curl -i -X GET http://localhost:8000/api/v1/telemetry/DOES_NOT_EXIST \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```
* **Expected Code**: `404 Not Found`
* **Expected Response**: `{"detail": {"error": "Battery not found"}}`

### Post Ingest with Missing Voltage (422)
```bash
curl -i -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"schema_version\": \"1.0\",
    \"source\": \"bad_data_test\",
    \"battery_id\": \"EV_DEMO_001\",
    \"vehicle_id\": \"VH_FORD_F150\",
    \"timestamp\": \"2024-01-15T14:23:45Z\",
    \"cycle_number\": 11,
    \"cycle_type\": \"discharge\",
    \"measurements\": {
      \"current_a\": -2.1,
      \"temperature_c\": 26.5,
      \"capacity_mah\": 1800.0
    }
  }"
```
* **Expected Code**: `422 Unprocessable Entity`
* **Expected Response**: Returns Pydantic validation error details pointing to the missing `voltage_v` field.
