"""
NASA Lithium-Ion Battery Dataset Loader.
Parses metadata.csv and individual telemetry files in cleaned_dataset/,
downsamples the records, and ingests them into the EV Battery Telemetry API.

Runs with Python standard library only (no external dependencies).
"""

import argparse
import csv
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone


def parse_start_time(st_str: str) -> datetime:
    """
    Parse Numpy-style float arrays into standard Python datetimes.
    e.g. '[2010.       7.      21.      15.       0.      35.093]'
    """
    st_str = st_str.strip('[]')
    # Split by any whitespace
    parts = re.split(r'\s+', st_str.strip())
    parts = [float(p) for p in parts if p]
    if len(parts) < 6:
        parts += [0.0] * (6 - len(parts))
    
    year, month, day, hour, minute, second = parts[:6]
    microsecond = int(round((second - int(second)) * 1000000))
    microsecond = max(0, min(999999, microsecond))
    
    # Return timezone-aware datetime in UTC
    return datetime(
        int(year), int(month), int(day), int(hour), int(minute), int(second), microsecond
    ).replace(tzinfo=timezone.utc)


def downsample_list(lst: list, k: int) -> list:
    """Select k elements evenly spaced across the list including first and last."""
    if len(lst) <= k:
        return lst
    indices = [int(i * (len(lst) - 1) / (k - 1)) for i in range(k)]
    return [lst[idx] for idx in indices]


def load_real_data(
    dataset_path: str,
    api_url: str,
    internal_key: str,
    target_batteries: list[str],
    limit_cycles: int,
    downsample_factor: int,
):
    metadata_file = os.path.join(dataset_path, "metadata.csv")
    if not os.path.exists(metadata_file):
        print(f"Error: metadata.csv not found at {metadata_file}")
        return

    print(f"Reading metadata from {metadata_file}...")
    
    # 1. Read metadata.csv and filter discharge cycles for targeted batteries
    discharge_cycles = []
    with open(metadata_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            b_id = row["battery_id"]
            c_type = row["type"]
            if b_id in target_batteries and c_type == "discharge":
                discharge_cycles.append(row)

    print(f"Found {len(discharge_cycles)} total discharge cycles for target batteries {target_batteries}.")

    # 2. Group cycles by battery to assign clean sequential cycle numbers
    cycles_by_battery = {}
    for row in discharge_cycles:
        b_id = row["battery_id"]
        if b_id not in cycles_by_battery:
            cycles_by_battery[b_id] = []
        cycles_by_battery[b_id].append(row)

    # Sort each group by start_time
    for b_id, rows in cycles_by_battery.items():
        rows.sort(key=lambda r: parse_start_time(r["start_time"]))
        # Limit the number of cycles to process
        if len(rows) > limit_cycles:
            cycles_by_battery[b_id] = rows[:limit_cycles]
            print(f"Limiting battery {b_id} to first {limit_cycles} cycles.")

    # 3. Process each cycle and ingest
    total_ingested = 0
    total_errors = 0

    for b_id, rows in cycles_by_battery.items():
        print(f"\nProcessing battery {b_id} (cycles 1 to {len(rows)})...")
        for seq_idx, row in enumerate(rows, start=1):
            filename = row["filename"]
            csv_path = os.path.join(dataset_path, "data", filename)
            if not os.path.exists(csv_path):
                print(f"Warning: Telemetry file {csv_path} not found. Skipping cycle {seq_idx}.")
                continue

            # Parse start time and capacity
            start_time = parse_start_time(row["start_time"])
            # Capacity in metadata is in Ah. Convert to mAh.
            capacity_ah = float(row["Capacity"]) if row["Capacity"] else 2.0
            capacity_mah = capacity_ah * 1000.0

            # Read all lines from telemetry file
            readings = []
            with open(csv_path, "r") as cf:
                creader = csv.DictReader(cf)
                for crow in creader:
                    readings.append(crow)

            if not readings:
                continue

            # Downsample telemetry lines
            downsampled = downsample_list(readings, downsample_factor)

            # Ingest each downsampled reading
            for idx, reading in enumerate(downsampled):
                try:
                    # Calculate reading timestamp
                    elapsed_seconds = float(reading["Time"])
                    reading_time = start_time + timedelta(seconds=elapsed_seconds)

                    # Extract measurements
                    voltage = float(reading["Voltage_measured"])
                    current = float(reading["Current_measured"])
                    temp = float(reading["Temperature_measured"])

                    # Construct IngestPayload
                    payload = {
                        "schema_version": "1.0",
                        "source": "nasa_dataset_loader",
                        "battery_id": b_id,
                        "vehicle_id": f"VH_NASA_{b_id}",
                        "timestamp": reading_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "cycle_number": seq_idx,
                        "cycle_type": "discharge",
                        "measurements": {
                            "voltage_v": voltage,
                            "current_a": current,
                            "temperature_c": temp,
                            "capacity_mah": capacity_mah,
                        },
                        "metadata": {
                            "source_file": filename,
                            "elapsed_seconds": elapsed_seconds
                        }
                    }

                    # HTTP POST to API
                    req = urllib.request.Request(
                        f"{api_url}/api/v1/ingest",
                        data=json.dumps(payload).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "X-Internal-API-Key": internal_key
                        },
                        method="POST"
                    )

                    with urllib.request.urlopen(req) as resp:
                        resp.read()

                    total_ingested += 1
                except Exception as e:
                    total_errors += 1
                    # print(f"Error ingesting row in cycle {seq_idx}: {e}")

            print(f"  Ingested cycle {seq_idx}/{len(rows)} ({len(downsampled)} readings) from {filename}")

    print(f"\nIngestion finished. Total readings ingested: {total_ingested}, Ingestion errors: {total_errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NASA Battery Telemetry Ingestion Script")
    parser.add_argument(
        "--dataset-path", 
        default="../cleaned_dataset", 
        help="Path to cleaned_dataset folder containing metadata.csv and data/"
    )
    parser.add_argument(
        "--api-url", 
        default="http://localhost:8000", 
        help="FastAPI application base URL"
    )
    parser.add_argument(
        "--internal-key", 
        default="super_secret_internal_api_key_123", 
        help="Internal API key for ingestion"
    )
    parser.add_argument(
        "--batteries", 
        default="B0047,B0048", 
        help="Comma-separated list of battery IDs to ingest"
    )
    parser.add_argument(
        "--limit-cycles", 
        type=int, 
        default=30, 
        help="Maximum cycles to ingest per battery (defaults to 30 to keep it fast)"
    )
    parser.add_argument(
        "--downsample-factor", 
        type=int, 
        default=10, 
        help="Number of telemetry points to ingest per cycle"
    )

    args = parser.parse_args()
    
    target_bats = [b.strip() for b in args.batteries.split(",") if b.strip()]
    
    load_real_data(
        dataset_path=args.dataset_path,
        api_url=args.api_url,
        internal_key=args.internal_key,
        target_batteries=target_bats,
        limit_cycles=args.limit_cycles,
        downsample_factor=args.downsample_factor,
    )
