#!/bin/sh
set -euo pipefail

echo "Starting Central Core Hub (Python MQTT client)"

# Ensure options file exists so Python client can read it
OPTIONS_FILE="/data/options.json"
if [ ! -f "$OPTIONS_FILE" ]; then
	echo "{}" > "$OPTIONS_FILE"
fi

# Store the current addon/package version in a separate metadata file
# to avoid polluting the user's options.json configuration.
python3 - <<'PY'
import json
from pathlib import Path

metadata_path = Path("/data/.addon_metadata.json")
candidates = [Path("/config.json"), Path(__file__).resolve().parent / "config.json"]
version = None
for p in candidates:
	try:
		with p.open() as f:
			data = json.load(f)
		if isinstance(data, dict) and "version" in data:
			version = str(data["version"])
			break
	except Exception:
		continue

if version:
	try:
		metadata = {"addon_version": version}
		with metadata_path.open("w") as f:
			json.dump(metadata, f, indent=2)
		print(f"Stored addon_version={version} in {metadata_path}")
	except Exception as e:
		print(f"Failed to write metadata to {metadata_path}: {e}")
else:
	print("No package version found to store in metadata")
PY

exec python3 /mqtt_client.py
