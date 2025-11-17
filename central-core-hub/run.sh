#!/bin/sh
set -euo pipefail

echo "Starting Central Core Hub (Python MQTT client)"

# Ensure options file exists so Python client can read it
OPTIONS_FILE="/data/options.json"
if [ ! -f "$OPTIONS_FILE" ]; then
	echo "{}" > "$OPTIONS_FILE"
fi

exec python3 /mqtt_client.py
