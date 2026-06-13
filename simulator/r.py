import argparse
import asyncio
import httpx
import csv
import datetime
import os
#asyncio implemented for multiple evs
#argparse (used for scaling to multiple evs upto 100 if needed)
async def simulate_ev(battery_id, filename):    

    async with httpx.AsyncClient() as client:
        
        with open(filename, "r") as file:
            reader = csv.DictReader(file)
            
            current_cycle = 1 
            #check here for dict 
            for row in reader:
                try:
                    fresh_timestamp = datetime.datetime.now().isoformat()
                    float_voltage = float(row['Voltage_measured'])
                    float_current = float(row['Current_measured'])
                    float_temp = float(row['Temperature_measured'])
                    
                    payload = {
                        "battery_id": battery_id,
                        "timestamp": fresh_timestamp,
                        "cycle_number": current_cycle,
                        "measurements": {
                            "voltage_v": float_voltage,
                            "current_a": float_current,
                            "temperature_c": float_temp
                        }
                    }
                    response = await client.post(
                        
                        "http://localhost:8000/api/v1/ingest",
                        headers={"X-Internal-API-Key": os.getenv("API_KEY", "super_secret_internal_api_key_123")},
                        json=payload
                    )
                    print(f"[{battery_id}] Sent cycle {current_cycle} | Status: {response.status_code}")
                    
                except KeyError as e:
                    # Catch #1: Bad CSV Headers
                    print(f"[{battery_id}] 🛑 CRASH! Missing header {e} in {filename}")
                    print(f"[{battery_id}] Headers actually found: {reader.fieldnames}")
                    break  
                    
                except httpx.ConnectError:
                    # Catch #2: Backend Server is Offline
                    print(f"[{battery_id}] Server offline. Retrying...")

                await asyncio.sleep(1)
                current_cycle += 1
  
        

                
              

#  The Main Loop
async def main(ev_count):
    print(f"Starting Fleet Simulator with {ev_count} cars...")
    
    tasks = []
    for i in range(1,ev_count+1):
        battery_id = f"{i:05d}"
        filename = f"data/{i:05d}.csv"
        tasks.append(simulate_ev(battery_id, filename))
    
    
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EV Fleet Simulator")
    parser.add_argument("--ev-count", type=int, default=1, help="Number of EVs to simulate")
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.ev_count))
    except KeyboardInterrupt:
        print("\n[Simulator] Shutting down fleet streams gracefully. Goodbye!")
