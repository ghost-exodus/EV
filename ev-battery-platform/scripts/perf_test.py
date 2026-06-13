"""
Asynchronous performance load test script for the EV Battery Telemetry platform.
Simulates a constant load of 50 requests/second for 60 seconds (3,000 total requests).
Measures latency percentiles and asserts performance SLAs.
"""

import asyncio
import time
import os
import sys
from datetime import datetime, timezone
import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TARGET_RPS = 50
DURATION_SECONDS = 60
TOTAL_REQUESTS = TARGET_RPS * DURATION_SECONDS

latencies = []
status_codes = {}
errors = 0


async def send_request(client: httpx.AsyncClient, payload: dict, headers: dict):
    global errors
    start_time = time.perf_counter()
    try:
        response = await client.post(
            "/api/v1/ingest", json=payload, headers=headers, timeout=10.0
        )
        duration = (time.perf_counter() - start_time) * 1000  # in ms
        latencies.append(duration)

        code = response.status_code
        status_codes[code] = status_codes.get(code, 0) + 1
        if code != 202:
            errors += 1
    except Exception as e:
        duration = (time.perf_counter() - start_time) * 1000
        latencies.append(duration)
        errors += 1
        status_codes["Error"] = status_codes.get("Error", 0) + 1


async def run_load_test():
    print("======================================================================")
    print("                    EV TELEMETRY PERFORMANCE TEST                     ")
    print("======================================================================")
    print(f"Target URL:  {API_BASE_URL}")
    print(f"RPS Target:  {TARGET_RPS} req/sec")
    print(f"Duration:    {DURATION_SECONDS} seconds")
    print(f"Total Reqs:  {TOTAL_REQUESTS}")
    print("----------------------------------------------------------------------")

    # 1. Authenticate to get valid JWT token
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        try:
            auth_resp = await client.post(
                "/auth/token",
                data={"username": "admin", "password": "secret"},
                timeout=5.0,
            )
            if auth_resp.status_code != 200:
                print(
                    f"CRITICAL: Authentication failed with status {auth_resp.status_code}"
                )
                sys.exit(1)
            token = auth_resp.json()["access_token"]
            print("Successfully authenticated as admin.")
        except Exception as e:
            print(f"CRITICAL: Failed to connect to auth endpoint: {e}")
            sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Spawn requests with precise timing
    print("Starting load test...")
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        start_time = time.time()
        tasks = []

        for i in range(TOTAL_REQUESTS):
            # Vary battery_id and cycle_number to simulate realistic load
            battery_id = f"PERF_BATT_{i % 100:03d}"
            cycle_number = i // 100

            payload = {
                "schema_version": "1.0",
                "source": "perf_test_script",
                "battery_id": battery_id,
                "vehicle_id": f"VH_PERF_{i % 100:03d}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cycle_number": cycle_number,
                "cycle_type": "discharge" if i % 2 == 0 else "charge",
                "measurements": {
                    "voltage_v": 3.85,
                    "current_a": -2.0,
                    "temperature_c": 25.4,
                    "capacity_mah": 1920.0,
                },
            }

            # Fire request
            tasks.append(
                asyncio.create_task(send_request(client, payload, headers))
            )

            # Control rate: sleep to maintain 50 requests/second (1 every 20ms)
            elapsed = time.time() - start_time
            expected_elapsed = (i + 1) / TARGET_RPS
            sleep_time = expected_elapsed - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

            if (i + 1) % 500 == 0:
                print(f" -> Sent {i + 1} / {TOTAL_REQUESTS} requests...")

        print("All requests dispatched. Waiting for final responses...")
        await asyncio.gather(*tasks)

    # 3. Calculate metrics
    total_completed = len(latencies)
    if total_completed == 0:
        print("CRITICAL: No requests completed.")
        sys.exit(1)

    latencies.sort()
    avg_latency = sum(latencies) / total_completed
    min_latency = latencies[0]
    max_latency = latencies[-1]

    # Percentiles
    p50_idx = int(total_completed * 0.50)
    p90_idx = int(total_completed * 0.90)
    p95_idx = int(total_completed * 0.95)
    p99_idx = int(total_completed * 0.99)

    p50_latency = latencies[min(p50_idx, total_completed - 1)]
    p90_latency = latencies[min(p90_idx, total_completed - 1)]
    p95_latency = latencies[min(p95_idx, total_completed - 1)]
    p99_latency = latencies[min(p99_idx, total_completed - 1)]

    # Print summary report
    print("\n======================================================================")
    print("                           SUMMARY REPORT                             ")
    print("======================================================================")
    print(f"Total Requests Sent: {TOTAL_REQUESTS}")
    print(f"Completed Responses: {total_completed}")
    print(f"Failed Requests:     {errors}")
    print("Status Code Counts:")
    for status, count in status_codes.items():
        print(f"  Status {status}: {count}")
    print("----------------------------------------------------------------------")
    print("Latency Metrics (ms):")
    print(f"  Min:      {min_latency:.2f} ms")
    print(f"  Average:  {avg_latency:.2f} ms")
    print(f"  p50 (Med): {p50_latency:.2f} ms")
    print(f"  p90:      {p90_latency:.2f} ms")
    print(f"  p95:      {p95_latency:.2f} ms (Target < 150.00 ms)")
    print(f"  p99:      {p99_latency:.2f} ms")
    print(f"  Max:      {max_latency:.2f} ms")
    print("======================================================================")

    # 4. Performance SLA Assertions
    print("\nVerifying SLAs...")
    sla_passed = True

    if p95_latency >= 150.0:
        print(
            f"❌ FAIL: p95 latency is {p95_latency:.2f} ms (exceeds SLA limit of 150.0 ms)"
        )
        sla_passed = False
    else:
        print(f"✅ PASS: p95 latency is {p95_latency:.2f} ms (< 150.0 ms)")

    if errors > 0:
        print(
            f"❌ FAIL: Detected {errors} request failures / non-202 responses"
        )
        sla_passed = False
    else:
        print("✅ PASS: 0 request errors detected (100% success rate)")

    if sla_passed:
        print("\n🎉 ALL PERFORMANCE SLAs PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\n❌ PERFORMANCE SLA VERIFICATION FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_load_test())
