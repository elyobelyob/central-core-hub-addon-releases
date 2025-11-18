
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

The add-on subscribes to Vault-style command topics and supports the following commands for `hubs/<client_id>/cmd/...`:

- `hubs/<client_id>/cmd/sensors/poll` (QoS 1)
	- Request: optional JSON payload with `command_id` and an optional `payload.sensors` list to request a subset.
	- Behavior: publishes an immediate ACK to `hubs/<client_id>/cmd/<command_id>/response` (if `command_id` present), then publishes sensor telemetry to `hubs/<client_id>/telemetry/sensors`, and finally publishes a completion response with a result summary to the response topic.

- `hubs/<client_id>/cmd/sensors/set` (QoS 1)
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
		- Immediately ACKs the command to `hubs/<client_id>/cmd/<command_id>/response` (QoS 1) if `command_id` present.
		- For each requested sensor, attempts to set the state via the Home Assistant REST API (`POST /api/states/<entity_id>`). Requires `ha_api_url` and `ha_api_token` to be configured in add-on options.
		- After a successful POST, the add-on performs a GET on the same entity (`GET /api/states/<entity_id>`) to read back the authoritative `state` and `attributes`.
		- Publishes a completion response to `hubs/<client_id>/cmd/<command_id>/response` with a `result` containing `set` and `failed` lists.
		- Publishes telemetry to `hubs/<client_id>/telemetry/sensors` using the authoritative readback values and attributes (if available).

	- Notes:
		- If HA is not configured, the command will report failures for targets and still ACK/complete if `command_id` is present.
		- Telemetry published after `sensors/set` contains both `data` and `attributes` so consumers see authoritative values and metadata (units, device_class, etc.).

### Home Assistant integration options

- **ha_api_url**: Base URL of the Home Assistant instance (e.g. `http://homeassistant.local:8123`).
- **ha_api_token**: Long-Lived Access Token to call the REST API (`POST`/`GET` on `/api/states`).

Security:
- The add-on uses the provided token to call HA REST endpoints; protect it like any secret.


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
