#!/bin/sh
set -euo pipefail

echo "Starting Central Core Hub (Python MQTT client)"

# Ensure options file exists so Python client can read it
OPTIONS_FILE="/data/options.json"
if [ ! -f "$OPTIONS_FILE" ]; then
	echo "{}" > "$OPTIONS_FILE"
fi

# Write the current addon/package version into the options file so
# the UI and runtime stay synchronized. We prefer `/config.json`
# (the add-on manifest) if present; otherwise fall back to the
# repository `central-core-hub/config.json`.
python3 - <<'PY'
import json
from pathlib import Path

options_path = Path("/data/options.json")
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
		opts = {}
		if options_path.exists():
			with options_path.open() as f:
				try:
					opts = json.load(f)
				except Exception:
					opts = {}
		opts = opts if isinstance(opts, dict) else {}
		# Always update addon_version to reflect packaged version
		opts["addon_version"] = version
		with options_path.open("w") as f:
			json.dump(opts, f)
		print(f"Wrote addon_version={version} to {options_path}")
	except Exception as e:
		print(f"Failed to write addon_version to {options_path}: {e}")
else:
	print("No package version found to write into options.json")
PY

exec python3 /mqtt_client.py
