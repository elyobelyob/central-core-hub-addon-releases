#!/usr/bin/env bash
# Simple integration script to run a local mosquitto broker and the Python client
# Usage: ./run_local_test.sh
set -euo pipefail

# Build the client image (use local Python script) or run python directly
# Start a local mosquitto container
MOSQ_PORT=1883

echo "Starting local mosquitto container..."
docker run -d --name test-mosquitto -p ${MOSQ_PORT}:1883 eclipse-mosquitto:2.0
sleep 2

# Run the client locally (requires python3 and deps installed on host)
# We'll run the mqtt_client.py directly and set options via env or a temp options.json
TMP_OPTIONS=$(mktemp)
cat > "$TMP_OPTIONS" <<EOF
{
  "mqtt_host": "localhost",
  "mqtt_port": 1883,
  "client_id": "test-hub-001",
  "vault_topic": "vault/test-hub-001"
}
EOF

echo "Running mqtt_client.py with test options (press Ctrl-C to stop)"
# run in foreground so user can see output
MQTT_OPTIONS_PATH="$TMP_OPTIONS" python3 ./central-core-hub/mqtt_client.py

# cleanup (won't run unless user stops the test script)
# docker rm -f test-mosquitto
