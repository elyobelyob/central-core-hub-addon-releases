
# Central Core Hub Add-on Releases

## Home Assistant Add-on Base Images
This add-on now uses the official Home Assistant base images for all supported architectures, as required for Supervisor compliance. See `central-core-hub/build.yaml` for details.


## MQTT Telemetry
This add-on sends telemetry data to a configurable MQTT broker. You can set the following options in the add-on configuration:

- **mqtt_host**: MQTT broker hostname or IP
- **mqtt_port**: MQTT broker port (default: 1883)
- **mqtt_username**: MQTT username (optional)
- **mqtt_password**: MQTT password (optional)
- **mqtt_tls**: Enable TLS (true/false)
- **mqtt_ca_cert**: CA certificate path (if TLS enabled)
- **mqtt_client_cert**: Client certificate path (if TLS enabled)
- **mqtt_client_key**: Client key path (if TLS enabled)
- **client_id**: MQTT client ID (defaults to the HAOS hostname, lowercased and spaces replaced with dashes)
- **greeting**: Informational message (default: "Central Core Hub telemetry active.")

### Telemetry Topic and Payload
- **Topic:** `telemetry/<client_id>`
- **Payload Example:**
	```json
	{
		"client_id": "hub-001",
		"status": "online",
		"timestamp": "2025-11-16T12:00:00Z"
	}
	```

### Sensors telemetry (preferred)

- **Preferred topic for sensor telemetry:** `hubs/<client_id>/telemetry/sensors`
- **When published:** on startup, hourly, and immediately after a successful `sensors/set` command.
- **Payload format (after a `sensors/set` or `sensors/poll`):**

	```json
	{
	  "data": {
	    "sensor.temp": 22.0,
	    "sensor.hum": 43
	  },
	  "attributes": {
	    "sensor.temp": {"unit_of_measurement": "°C"},
	    "sensor.hum": {"unit_of_measurement": "%"}
	  },
	  "timestamp": "2025-11-18T12:00:00Z"
	}
	```

Notes:
- `data` contains a map of `entity_id -> value` using coercion to boolean/number when possible.
- `attributes` contains the Home Assistant attributes read back from the entity state (if available).
- Telemetry to this preferred topic is published with QoS 0 (best-effort).

### Commands (subscribe)

The add-on subscribes to Vault-style command topics and supports the following commands for `hubs/<client_id>/v1/cmd/...`:

- `hubs/<client_id>/v1/cmd/sensors/poll` (QoS 1)
	- Request: optional JSON payload with `command_id` and an optional `payload.sensors` list to request a subset.
	- Behavior: publishes an immediate ACK to the versioned ACK topic `hubs/<client_id>/v1/ack/<action.replace('/', '.')>/<command_id>` (if `command_id` present), then publishes sensor telemetry to `hubs/<client_id>/telemetry/sensors`, and finally publishes a completion response with a result summary to the same versioned ACK topic.

- `hubs/<client_id>/v1/cmd/sensors/set` (QoS 1)
	- Request payload examples:

		1) List form

		```json
		{
			"command_id": "abc123",
			"action": "sensors/set",
			"payload": {
				"sensors": [
					{"entity_id": "sensor.temp", "state": "22.0"},
					{"entity_id": "sensor.hum", "state": "43"}
				]
			}
		}
		```

		2) Mapping form

		```json
		{
			"command_id": "abc124",
			"action": "sensors/set",
			"payload": {
				"sensors": {"sensor.temp": "22.0", "sensor.hum": "43"}
			}
		}
		```

	- Behavior:
		- Immediately ACKs the command to the versioned ACK topic `hubs/<client_id>/v1/ack/<action.replace('/', '.')>/<command_id>` (QoS 1) if `command_id` present.
		- For each requested sensor, attempts to set the state via the Home Assistant REST API (`POST /api/states/<entity_id>`). Requires `ha_api_url` and `ha_api_token` to be configured in add-on options.
		- After a successful POST, the add-on performs a GET on the same entity (`GET /api/states/<entity_id>`) to read back the authoritative `state` and `attributes`.
		- Publishes a completion response to the versioned ACK topic `hubs/<client_id>/v1/ack/<action.replace('/', '.')>/<command_id>` with a `result` containing `set` and `failed` lists.
		- Publishes telemetry to `hubs/<client_id>/telemetry/sensors` using the authoritative readback values and attributes (if available).

	- Notes:
		- If HA is not configured, the command will report failures for targets and still ACK/complete if `command_id` is present.
- Telemetry published after `sensors/set` contains both `data` and `attributes` so consumers see authoritative values and metadata (units, device_class, etc.).
### Config update command (Vault-driven)

- `hubs/<client_id>/v1/cmd/config/update` (QoS 1)
  - Trigger: Vault sends a JSON payload with an optional `command_id`/`action`.
  - Behavior:
    1. Immediately ACKs the command to `hubs/<client_id>/v1/ack/config.update/<command_id>` (if provided).
    2. Calls HA’s websocket services (`supervisor.check_addon_updates` or `hassio.check_addon_updates` followed by `supervisor.addon_update`/`hassio.addon_update`) using the add-on slug from `central-core-hub/config.json`.
    3. Publishes a completion response containing the service call results to the versioned ACK topic `hubs/<client_id>/v1/ack/<action.replace('/', '.')>/<command_id>` (the same topic receives both ACK and completion payloads).
  - Payload `result` includes both the “check” and “update” responses along with a `success` flag so Vault knows whether a newer version was installed.

### Home Assistant integration options

- **ha_api_url**: Base URL of the Home Assistant instance (e.g. `http://homeassistant.local:8123`).
- **ha_api_token**: Long-Lived Access Token to call the REST API (`POST`/`GET` on `/api/states`).
- **safe_device_classes**: (Optional) List of device class types that are considered safe for telemetry. Sensors with a `device_class` attribute that is not in this list will be filtered out. Sensors without a `device_class` attribute are allowed through for backward compatibility. Default: `["temperature", "motion", "door", "battery", "occupancy", "presence", "opening", "aqi", "energy"]`.

  Example configuration:
  ```json
  {
    "safe_device_classes": ["temperature", "humidity", "pressure", "battery"]
  }
  ```

Security:
- The add-on uses the provided token to call HA REST endpoints; protect it like any secret.
- The `safe_device_classes` configuration provides a security layer by filtering which sensor types are included in telemetry based on their `device_class` attribute, preventing potentially sensitive sensor data from being transmitted.


### Vault integration and schema versions

- New option `vault_topic` (optional): when set, the add-on publishes a Vault-friendly compact payload to this topic in addition to the default telemetry topic.
- Telemetry payload `schema_version`: 1 (full telemetry). A transformed Vault payload is published with `schema_version`: 2.

Integration test:

 - Run the local mosquitto broker and the client for quick manual verification:

 ```bash
 ./central-core-hub/tests/integration/run_local_test.sh
 ```

See `central-core-hub/mqtt_client.py` for `build_vault_payload()` implementation.

See `central-core-hub/run.sh` for implementation details.

Formatting & Linting
--------------------

This repository uses `ruff` as the single tool for linting and formatting.

- Format code in-place:

```bash
ruff format .
```

- Run lint checks:

```bash
ruff check .
```

If you use `pre-commit`, the repository is configured to run `ruff --fix` automatically on commits. To install the hook locally:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Notes:
- We intentionally removed Black and Flake8 in favor of Ruff. If you previously relied on Black, Ruff's formatting is compatible, but Black-specific tooling is not required.
- The project's `ruff.toml` contains settings to make Ruff behave in a Black-compatible way (ignore `E203`, `line-length = 120`).

Release Notes
-------------

Recent notable commits (extracted from git history):

From `v1.1.25..v1.1.26`:

- chore(release): bump version to 1.1.26 (7076e68)
- test(ha_client): add timeout, malformed-json, and pending-request timeout tests (56785e5)

From `v1.1.26..HEAD`:

- chore(release): include all changes; bump version to 1.1.27 (1f730f9)
- docs(changelog): add release notes for v1.1.27 (d591831)
- docs(changelog): backfill commits for v1.1.26..v1.1.27 (16b4f2e)

For more details see `CHANGELOG.md` or the git history.
