"""
Step 5: Isolated ML Integration Test

Standalone script that validates the LSTM RUL model loads and produces
sane predictions WITHOUT touching the FastAPI app or database.

Run from project root:
    python tests/test_ml_integration.py

Expected: prints raw prediction output, validates it's a sane number.
Exit code 0 = pass, 1 = fail.
"""

import sys
import os

# Fix Windows console encoding (cp1252 can't handle unicode markers)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ensure project root is on sys.path so `services.ml_service` can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np


def generate_synthetic_readings(n: int = 50) -> list[dict]:
    """
    Generate N synthetic telemetry readings with realistic NASA B0005-range values.

    Simulates a battery degrading over cycles:
      - voltage_v:      3.0 - 4.2 V (slight decline)
      - current_a:      -2.0 to 2.0 A (discharge cycles, so mostly negative)
      - temperature_c:  20 - 30 °C (slight warming trend)
      - capacity_mah:   2000 → 1600 mAh (steady decline, the key degradation signal)
    """
    readings = []
    for i in range(n):
        frac = i / max(n - 1, 1)  # 0.0 → 1.0 over the sequence

        readings.append({
            "recorded_at": f"2024-01-{15 + i // 3:02d}T{10 + i % 12:02d}:00:00.000Z",
            "cycle_number": 100 + i,
            "voltage_v": round(4.2 - 0.4 * frac + np.random.normal(0, 0.02), 4),
            "current_a": round(-1.5 + np.random.normal(0, 0.3), 4),
            "temperature_c": round(22.0 + 6.0 * frac + np.random.normal(0, 0.5), 2),
            "capacity_mah": round(2000 - 400 * frac + np.random.normal(0, 10), 1),
            "cycle_type": "discharge",
        })

    return readings


def main():
    print("=" * 60)
    print("  LSTM RUL Model — Isolated Integration Test")
    print("=" * 60)

    # 1. Import the adapter
    print("\n[1/4] Importing ml_service.predict_rul ...")
    try:
        from services.ml_service import predict_rul
        print("       ✅ Import successful")
    except Exception as e:
        print(f"       ❌ Import FAILED: {e}")
        sys.exit(1)

    # 2. Generate synthetic readings
    print("\n[2/4] Generating 50 synthetic telemetry readings ...")
    readings = generate_synthetic_readings(50)
    print(f"       Generated {len(readings)} readings")
    print(f"       First: voltage={readings[0]['voltage_v']}V, "
          f"capacity={readings[0]['capacity_mah']}mAh")
    print(f"       Last:  voltage={readings[-1]['voltage_v']}V, "
          f"capacity={readings[-1]['capacity_mah']}mAh")

    # 3. Call predict_rul with a realistic SoH
    soh = 80.0  # Battery at 80% health
    print(f"\n[3/4] Calling predict_rul('TEST_BATT_001', readings, soh_percent={soh}) ...")

    result = predict_rul("TEST_BATT_001", readings, soh_percent=soh)

    print(f"\n       Raw output: {result}")

    # 4. Validate the result
    print("\n[4/4] Validating prediction ...")
    errors = []

    rul = result.get("predicted_rul_cycles")
    lower = result.get("confidence_lower")
    upper = result.get("confidence_upper")
    version = result.get("model_version")

    # Check model actually loaded (not fallback)
    if version == "unavailable":
        errors.append(f"Model did not load — version is 'unavailable'. "
                      f"Check that ml/models/rul_lstm_v1.pt and scaler.pkl exist.")

    # Check RUL is an integer
    if not isinstance(rul, int):
        errors.append(f"predicted_rul_cycles is not int: {type(rul)} = {rul}")

    # Check RUL is non-negative
    if rul is not None and rul < 0:
        errors.append(f"predicted_rul_cycles is negative: {rul}")

    # Check RUL is not absurdly large (NASA B0005 has ~168 total cycles)
    if rul is not None and rul > 5000:
        errors.append(f"predicted_rul_cycles is suspiciously large: {rul} (>5000)")

    # Check confidence bounds are ordered
    if lower is not None and upper is not None and lower > upper:
        errors.append(f"Confidence bounds inverted: lower={lower} > upper={upper}")

    # Check it's not the old stub values
    if rul == 213 and lower == 188 and upper == 238:
        errors.append("Output matches the OLD STUB values (213/188/238)! "
                      "The real model may not be loading.")

    if errors:
        print("\n       ❌ VALIDATION FAILED:")
        for e in errors:
            print(f"          - {e}")
        sys.exit(1)
    else:
        print(f"       ✅ predicted_rul_cycles = {rul}")
        print(f"       ✅ confidence_interval  = [{lower}, {upper}]")
        print(f"       ✅ model_version        = {version}")
        print(f"       ✅ Not NaN, not negative, not absurdly large, not stub values")
        print("\n" + "=" * 60)
        print("  ALL CHECKS PASSED — Model loads and produces sane output.")
        print("=" * 60)

    # Also test edge case: fewer than 50 readings
    print("\n--- Edge case test: 5 readings (should pad without crashing) ---")
    short_readings = generate_synthetic_readings(5)
    short_result = predict_rul("TEST_BATT_002", short_readings, soh_percent=90.0)
    print(f"    Result with 5 readings: {short_result}")
    if short_result.get("model_version") == "unavailable":
        print("    ❌ Padding test produced fallback (model issue)")
        sys.exit(1)
    print("    ✅ Padding worked correctly")

    # Edge case: null capacity_mah in some rows
    print("\n--- Edge case test: null capacity_mah in some readings ---")
    null_cap_readings = generate_synthetic_readings(50)
    for i in [0, 1, 2, 10, 20]:
        null_cap_readings[i]["capacity_mah"] = None
    null_cap_result = predict_rul("TEST_BATT_003", null_cap_readings, soh_percent=75.0)
    print(f"    Result with null capacities: {null_cap_result}")
    if null_cap_result.get("model_version") == "unavailable":
        print("    ❌ Null capacity test produced fallback (model issue)")
        sys.exit(1)
    print("    ✅ Null capacity handling worked correctly")

    print("\n✅ All isolated tests passed. Safe to proceed to Step 6 (E2E pipeline).\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
