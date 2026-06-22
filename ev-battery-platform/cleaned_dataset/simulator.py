import argparse, asyncio, httpx, csv, datetime, os

async def simulate_ev(battery_id, filename):
    async with httpx.AsyncClient() as client:
        with open(filename, "r") as file:
            reader = csv.DictReader(file)
            current_cycle = 1
            for row in reader:
                payload = {
                    "schema_version": "1.0",
                    "source": "ev_simulator_aws",
                    "battery_id": battery_id,
                    "timestamp": datetime.datetime.now().isoformat() + "Z",
                    "cycle_number": current_cycle,
                    "cycle_type": "discharge",
                    "measurements": {
                        "voltage_v": float(row['Voltage_measured']),
                        "current_a": float(row['Current_measured']),
                        "temperature_c": float(row['Temperature_measured'])
                        # NOTE: No capacity_mah here
                    }
                }
                response = await client.post(
                    "http://localhost:8000/api/v1/ingest",
                    headers={"X-Internal-API-Key": os.getenv("API_KEY", "super_secret_internal_api_key_123")},
                    json=payload
                )
                print(f"[{battery_id}] Sent cycle {current_cycle} | Status: {response.status_code}")
                # Temp modification: reduce wait time for faster smoke test
                await asyncio.sleep(0.05)
                current_cycle += 1

async def main(ev_count):
    tasks = []
    for i in range(1, ev_count+1):
        battery_id = f"{i:05d}"
        filename = f"data/{i:05d}.csv"
        tasks.append(simulate_ev(battery_id, filename))
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ev-count", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(main(args.ev_count))
