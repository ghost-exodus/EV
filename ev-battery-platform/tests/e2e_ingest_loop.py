"""
Step 6: Full E2E Pipeline Test — Ingestion Loop

Sends 15 telemetry messages to POST /api/v1/ingest for the same battery_id
with declining capacity, triggering LSTM prediction on the 10th message.

Usage:
    python tests/e2e_ingest_loop.py

Requires the FastAPI container to be running with DB migrated.
"""

import sys
import json
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

BASE_URL = "http://localhost:8000"
INTERNAL_API_KEY = "super_secret_internal_api_key_123"
BATTERY_ID = "E2E_TEST_BATT_001"
NUM_MESSAGES = 15


def get_jwt_token() -> str:
    """Authenticate and retrieve a JWT token."""
    print("\n[1/4] Authenticating to get JWT token ...")
    resp = httpx.post(
        f"{BASE_URL}/auth/token",
        data={"username": "admin", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        print(f"       FAILED to get token: {resp.status_code} {resp.text}")
        sys.exit(1)

    token = resp.json().get("access_token")
    print(f"       Got JWT token: {token[:20]}...")
    return token


def send_telemetry(cycle: int, capacity_mah: float, voltage_v: float,
                   current_a: float, temperature_c: float, index: int) -> dict:
    """Send one telemetry ingest message."""
    from datetime import datetime, timedelta
    # Generate valid timestamps by offsetting from a base date
    base = datetime(2024, 6, 10, 10, 0, 0)
    ts = base + timedelta(hours=index)

    payload = {
        "battery_id": BATTERY_ID,
        "vehicle_id": "TEST_VEHICLE_001",
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cycle_number": cycle,
        "cycle_type": "discharge",
        "measurements": {
            "voltage_v": round(voltage_v, 4),
            "current_a": round(current_a, 4),
            "temperature_c": round(temperature_c, 2),
            "capacity_mah": round(capacity_mah, 1),
            "internal_resistance_ohm": None,
        }
    }

    resp = httpx.post(
        f"{BASE_URL}/api/v1/ingest",
        json=payload,
        headers={"X-Internal-API-Key": INTERNAL_API_KEY},
        timeout=10.0,
    )
    if resp.status_code != 202:
        print(f"\n       ERROR {resp.status_code}: {resp.text}")
    return {"status": resp.status_code, "body": resp.json()}


def check_rul_prediction(token: str) -> dict:
    """Query the RUL prediction endpoint."""
    resp = httpx.get(
        f"{BASE_URL}/api/v1/rul/{BATTERY_ID}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return {"status": resp.status_code, "body": resp.json()}


def main():
    print("=" * 60)
    print("  E2E Pipeline Test - LSTM RUL Integration")
    print("=" * 60)

    # 0. Health check (with retries — uvicorn may be reloading)
    print("\n[0/4] Checking /health ...")
    for attempt in range(5):
        try:
            health = httpx.get(f"{BASE_URL}/health", timeout=10.0)
            print(f"       /health -> {health.status_code}: {health.json()}")
            if health.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            if attempt < 4:
                print(f"       Attempt {attempt+1}/5 failed, retrying in 3s ...")
                time.sleep(3)
            else:
                print("       FAILED: Cannot connect to API after 5 attempts.")
                sys.exit(1)

    # 1. Get JWT
    token = get_jwt_token()

    # 2. Send telemetry messages
    print(f"\n[2/4] Sending {NUM_MESSAGES} telemetry messages for battery '{BATTERY_ID}' ...")
    print(f"       (LSTM prediction should trigger on message #10)")
    print()

    for i in range(1, NUM_MESSAGES + 1):
        frac = (i - 1) / (NUM_MESSAGES - 1)  # 0.0 -> 1.0

        # Simulate degradation: capacity declines, voltage drops, temp rises
        capacity = 2000.0 - 400.0 * frac   # 2000 -> 1600 mAh
        voltage = 4.15 - 0.35 * frac        # 4.15 -> 3.80 V
        current = -1.5 + 0.1 * frac          # discharge current
        temp = 23.0 + 5.0 * frac             # 23 -> 28 C

        result = send_telemetry(
            cycle=100 + i,
            capacity_mah=capacity,
            voltage_v=voltage,
            current_a=current,
            temperature_c=temp,
            index=i,
        )

        marker = " <-- LSTM should trigger!" if i == 10 else ""
        print(f"       Message #{i:2d}: cycle={100+i}, capacity={capacity:.0f}mAh "
              f"-> {result['status']}{marker}")

        # Small delay to let background tasks process
        time.sleep(0.3)

    # Give the background task a moment to complete
    # Give the background task time to complete (model cold-start on first call
    # includes loading PyTorch + scalers from disk, which can take 5-8 seconds)
    print("\n       Waiting 10s for background LSTM task to complete (includes model cold-start) ...")
    time.sleep(10)

    # 3. Query the RUL prediction
    print(f"\n[3/4] Querying GET /api/v1/rul/{BATTERY_ID} ...")
    rul_result = check_rul_prediction(token)
    print(f"       Status: {rul_result['status']}")
    print(f"       Response: {json.dumps(rul_result['body'], indent=2, default=str)}")

    # 4. Validate
    print(f"\n[4/4] Validating prediction ...")
    if rul_result["status"] == 404:
        print("       FAILED: No RUL prediction found. The LSTM task may not have triggered.")
        print("       Check logs: docker compose logs fastapi --tail 50")
        sys.exit(1)

    body = rul_result["body"]
    rul_cycles = body.get("predicted_rul_cycles")
    model_ver = body.get("model_version")

    errors = []

    # Not the old stub
    if rul_cycles == 213:
        errors.append(f"predicted_rul_cycles={rul_cycles} matches the OLD STUB value!")

    if model_ver == "v2.0":
        errors.append(f"model_version='{model_ver}' matches the OLD STUB version!")

    if model_ver == "unavailable":
        errors.append("model_version='unavailable' — model failed to load in container!")

    if rul_cycles is not None and rul_cycles < 0:
        errors.append(f"predicted_rul_cycles is negative: {rul_cycles}")

    if errors:
        print("       FAILED:")
        for e in errors:
            print(f"         - {e}")
        sys.exit(1)

    print(f"       predicted_rul_cycles = {rul_cycles} (NOT the old stub 213)")
    print(f"       model_version        = {model_ver} (NOT the old stub 'v2.0')")
    print(f"       confidence_interval  = [{body.get('confidence_interval', {}).get('lower_bound')}, "
          f"{body.get('confidence_interval', {}).get('upper_bound')}]")

    print("\n" + "=" * 60)
    print("  E2E PIPELINE TEST PASSED")
    print("=" * 60)
    print()
    sys.exit(0)


if __name__ == "__main__":
    main()
