
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

See `central-core-hub/run.sh` for implementation details.
