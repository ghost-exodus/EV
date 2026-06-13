#!/bin/bash

echo "Starting EV Telemetry Smoke Test..."

# 1. Start the simulator with 2 cars
python r.py --ev-count 2 &
SIM_PID=$!

echo "Simulator running (PID: $SIM_PID). Waiting 5 seconds for data flow..."
sleep 5

# 2. Ping the backend
echo "Checking backend database..."
curl -s -X GET "http://localhost:8000/api/v1/telemetry/00001" | grep -q "voltage_v"

if [ $? -eq 0 ]; then
    echo "SUCCESS: Telemetry found in the database!"
else
    echo "FAILED: No telemetry found or backend is offline."
fi

# 3. Clean up the background process
echo "Stopping simulator..."
kill $SIM_PID
echo "Test complete."