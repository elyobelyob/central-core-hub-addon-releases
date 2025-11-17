echo "Starting Central Core Hub add-on (placeholder)"
#!/bin/sh
set -euo pipefail

echo "Starting Central Core Hub add-on with MQTT telemetry support"

# Read options from HA options file
OPTIONS_FILE="/data/options.json"
MQTT_HOST=$(jq -r '.mqtt_host // ""' "$OPTIONS_FILE")
MQTT_PORT=$(jq -r '.mqtt_port // 1883' "$OPTIONS_FILE")
MQTT_USERNAME=$(jq -r '.mqtt_username // ""' "$OPTIONS_FILE")
MQTT_PASSWORD=$(jq -r '.mqtt_password // ""' "$OPTIONS_FILE")
MQTT_TLS=$(jq -r '.mqtt_tls // false' "$OPTIONS_FILE")
MQTT_CA_CERT=$(jq -r '.mqtt_ca_cert // ""' "$OPTIONS_FILE")
MQTT_CLIENT_CERT=$(jq -r '.mqtt_client_cert // ""' "$OPTIONS_FILE")
MQTT_CLIENT_KEY=$(jq -r '.mqtt_client_key // ""' "$OPTIONS_FILE")
CLIENT_ID=$(jq -r '.client_id // ""' "$OPTIONS_FILE")
HA_API_URL=$(jq -r '.ha_api_url // ""' "$OPTIONS_FILE")
HA_API_TOKEN=$(jq -r '.ha_api_token // ""' "$OPTIONS_FILE")

if [ -n "${CLIENT_ID:-}" ]; then
	# CLIENT_ID is already set from options
	:
else
	# Use the system hostname, lowercased and spaces replaced with dashes
	CLIENT_ID="$(hostname | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
fi

echo "Debug: MQTT_HOST='$MQTT_HOST', MQTT_PORT='$MQTT_PORT'"

# Topic for vault telemetry
TELEMETRY_TOPIC="telemetry/$CLIENT_ID"

# Gather system metrics
HOSTNAME="$(hostname)"
IP_ADDRESS="$(ip route get 1 2>/dev/null | head -1 | awk '{print $7}' || echo 'unknown')"
UPTIME="$(awk '{print int($1)}' /proc/uptime 2>/dev/null || uptime | awk '{print $3}')"
LOAD_AVG="$(awk '{print $1 "," $2 "," $3}' /proc/loadavg 2>/dev/null || uptime | awk -F'load average:' '{print $2}' | sed 's/ //g')"
MEM_TOTAL="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null)"
MEM_FREE="$(awk '/MemFree/ {print $2}' /proc/meminfo 2>/dev/null)"
DISK_TOTAL="$(df -k / | awk 'NR==2 {print $2}')"
DISK_FREE="$(df -k / | awk 'NR==2 {print $4}')"

# Build telemetry payload
TELEMETRY_PAYLOAD=$(
	cat <<EOF
{
  "client_id": "$CLIENT_ID",
  "status": "online",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "hostname": "$HOSTNAME",
  "ip": "$IP_ADDRESS",
  "uptime": "$UPTIME",
  "load_avg": "$LOAD_AVG",
  "mem_total_kb": $MEM_TOTAL,
  "mem_free_kb": $MEM_FREE,
  "disk_total_kb": $DISK_TOTAL,
  "disk_free_kb": $DISK_FREE
}
EOF
)

publish_telemetry() {
	local extra=""
	if [ -n "$MQTT_USERNAME" ]; then
		extra="$extra -u $MQTT_USERNAME"
	fi
	if [ -n "$MQTT_PASSWORD" ]; then
		extra="$extra -P $MQTT_PASSWORD"
	fi
	if [ "$MQTT_TLS" = "true" ]; then
		extra="$extra --tls"
		if [ -n "$MQTT_CA_CERT" ]; then
			extra="$extra --cafile $MQTT_CA_CERT"
		fi
		if [ -n "$MQTT_CLIENT_CERT" ]; then
			extra="$extra --cert $MQTT_CLIENT_CERT"
		fi
		if [ -n "$MQTT_CLIENT_KEY" ]; then
			extra="$extra --key $MQTT_CLIENT_KEY"
		fi
	fi
	# Build argument string safely (values wrapped in single quotes)
	extra=""
	if [ -n "$MQTT_USERNAME" ]; then
		extra="$extra -u '$MQTT_USERNAME'"
	fi
	if [ -n "$MQTT_PASSWORD" ]; then
		extra="$extra -P '$MQTT_PASSWORD'"
	fi
	if [ "$MQTT_TLS" = "true" ]; then
		extra="$extra --tls"
		if [ -n "$MQTT_CA_CERT" ]; then
			extra="$extra --cafile '$MQTT_CA_CERT'"
		fi
		if [ -n "$MQTT_CLIENT_CERT" ]; then
			extra="$extra --cert '$MQTT_CLIENT_CERT'"
		fi
		if [ -n "$MQTT_CLIENT_KEY" ]; then
			extra="$extra --key '$MQTT_CLIENT_KEY'"
		fi
	fi
	# Use keepalive to ensure broker knows the client intent
	eval "mosquitto_pub -h '$MQTT_HOST' -p '$MQTT_PORT' -k 60 -t '$TELEMETRY_TOPIC' -m '$TELEMETRY_PAYLOAD' -i '${CLIENT_ID}_pub' $extra"
}

# Helper: fetch sensor states from Home Assistant API
fetch_sensors() {
	if [ -z "$HA_API_URL" ] || [ -z "$HA_API_TOKEN" ]; then
		echo "HA API URL or token not set, skipping sensor fetch"
		return 1
	fi
	curl -s -X GET \
		-H "Authorization: Bearer $HA_API_TOKEN" \
		-H "Content-Type: application/json" \
		"$HA_API_URL/api/states" | jq '.[] | select(.entity_id | test("^sensor\\."))' || true
}

# Helper: publish all sensors as an array
publish_all_sensors() {
	local sensors_json="$1"
	local topic="hubs/$CLIENT_ID/telemetry/sensors"
	local payload="{\"data\": $sensors_json}"
	# Build extra args safely and publish
	extra=""
	if [ -n "$MQTT_USERNAME" ]; then
		extra="$extra -u '$MQTT_USERNAME'"
	fi
	if [ -n "$MQTT_PASSWORD" ]; then
		extra="$extra -P '$MQTT_PASSWORD'"
	fi
	eval "mosquitto_pub -h '$MQTT_HOST' -p '$MQTT_PORT' -t '$topic' -m '$payload' -i '${CLIENT_ID}_pub' $extra"
}

# Helper: subscribe to commands topic
subscribe_commands() {
	local topic="hubs/$CLIENT_ID/commands"
	sub_log="/data/mosquitto_sub.log"
	rm -f "$sub_log" || true
	touch "$sub_log" || true

	# Background loop that restarts mosquitto_sub and logs exit codes
	(
		while true; do
			sub_extra=""
			if [ -n "$MQTT_USERNAME" ]; then
				sub_extra="$sub_extra -u '$MQTT_USERNAME'"
			fi
			if [ -n "$MQTT_PASSWORD" ]; then
				sub_extra="$sub_extra -P '$MQTT_PASSWORD'"
			fi
			echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Starting mosquitto_sub for topic '$topic'" >> "$sub_log"
			# Run subscriber; write stdout+stderr to log
			eval "mosquitto_sub -h '$MQTT_HOST' -p '$MQTT_PORT' -k 60 -t '$topic' -i '$CLIENT_ID' $sub_extra" >> "$sub_log" 2>&1
			rc=$?
			echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) mosquitto_sub exited with code $rc, restarting in 5s" >> "$sub_log"
			sleep 5
		done
	) &

	# Tail the log to stdout so HA add-on logs show subscriber messages and diagnostics
	tail -F "$sub_log" &
}

# Main loop: poll sensors and send telemetry as array on any state change
if [ -n "$MQTT_HOST" ]; then
	subscribe_commands
fi
while true; do
	if [ -n "$MQTT_HOST" ]; then
		# Send system telemetry
		publish_telemetry || echo "Failed to publish telemetry to MQTT broker"

		# Fetch and process sensors
		sensors_json=$(fetch_sensors)
		if [ -n "$sensors_json" ]; then
			changed=false
			sensors_array="["
			first=true
			echo "$sensors_json" | jq -c '.' > /tmp/sensors.json
			while IFS= read -r sensor; do
				entity_id=$(echo "$sensor" | jq -r '.entity_id')
				state=$(echo "$sensor" | jq -r '.state')
				friendly_name=$(echo "$sensor" | jq -r '.attributes.friendly_name // .entity_id')
				sensor_type=$(echo "$sensor" | jq -r '.attributes.device_class // "unknown"')
				# Only send if any state changed
				key=$(echo "$entity_id" | sed 's/\./_/g')
				old=$(eval "echo \$SENSOR_$key")
				if [ "$old" != "$state" ]; then
					changed=true
				fi
				eval "SENSOR_$key=\"$state\""
				# Build array entry
				$first || sensors_array+=","
				first=false
				sensors_array+="{\"name\":\"$friendly_name\",\"type\":\"$sensor_type\",\"value\":$state}"
			done < /tmp/sensors.json
			sensors_array+="]"
			if $changed; then
				publish_all_sensors "$sensors_array"
			fi
		fi
	else
		echo "MQTT_HOST not set, skipping telemetry publish"
	fi
	sleep 30
done
