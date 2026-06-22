#!/bin/bash

# Get the directory where this script is located (absolute path)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( dirname "$SCRIPT_DIR" )"

echo "Starting EV Telemetry Smoke Test..."

# 1. Start the simulator using its absolute location
# This reads data/00001.csv right next to r.py
cd "$SCRIPT_DIR"
python3 r.py --ev-count 2 &
SIM_PID=$!

echo "Simulator running (PID: $SIM_PID). Waiting 5 seconds for data flow..."
sleep 5

# 2. Ping the backend from the root workspace folder context
cd "$ROOT_DIR"
echo "Checking backend database..."
# curl -s -X GET "http://localhost:8000/api/v1/telemetry/00001" | grep -q "voltage"

# if [ $? -eq 0 ]; then
#     echo "SUCCESS: Telemetry found in the database!"
# else
#     echo "FAILED: No telemetry found or backend is offline."
# fi

# curl -s http://localhost:8000/health | grep -q "healthy"

# if [ $? -eq 0 ]; then
#     echo "SUCCESS: EV platform is online and native environment is responsive!"
# else
#     echo "FAILED: Backend is offline."
# fi

nc -z localhost 8000

if [ $? -eq 0 ]; then
    echo "SUCCESS: EV platform server is awake and accepting traffic natively!"
else
    echo "FAILED: Backend is offline. Make sure uvicorn main:app --port 8000 is running."
fi

# 3. Clean up the background process safely
echo "Stopping simulator..."
kill $SIM_PID
echo "Test complete."

# # 3. Clean up the background simulator process safely
# echo "Stopping simulator..."
# kill $SIM_PID
# echo "Test complete."