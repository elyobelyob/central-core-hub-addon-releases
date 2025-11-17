echo "Starting Central Core Hub add-on (placeholder)"
#!/usr/bin/env bash
set -euo pipefail

echo "Starting Central Core Hub add-on with MQTT telemetry support"


# Read options from Home Assistant environment variables
MQTT_HOST="${MQTT_HOST:-}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USERNAME="${MQTT_USERNAME:-}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"
MQTT_TLS="${MQTT_TLS:-false}"
MQTT_CA_CERT="${MQTT_CA_CERT:-}"
MQTT_CLIENT_CERT="${MQTT_CLIENT_CERT:-}"
MQTT_CLIENT_KEY="${MQTT_CLIENT_KEY:-}"
if [ -n "${CLIENT_ID:-}" ]; then
  CLIENT_ID="$CLIENT_ID"
else
  # Use the system hostname, lowercased and spaces replaced with dashes
  CLIENT_ID="$(hostname | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"
fi


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
TELEMETRY_PAYLOAD="{\"client_id\":\"$CLIENT_ID\",\"status\":\"online\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"hostname\":\"$HOSTNAME\",\"ip\":\"$IP_ADDRESS\",\"uptime\":\"$UPTIME\",\"load_avg\":\"$LOAD_AVG\",\"mem_total_kb\":\"$MEM_TOTAL\",\"mem_free_kb\":\"$MEM_FREE\",\"disk_total_kb\":\"$DISK_TOTAL\",\"disk_free_kb\":\"$DISK_FREE\"}"

publish_telemetry() {
  local mqtt_opts="-h $MQTT_HOST -p $MQTT_PORT -t $TELEMETRY_TOPIC -m \"$TELEMETRY_PAYLOAD\" -i $CLIENT_ID"
  if [ -n "$MQTT_USERNAME" ]; then
    mqtt_opts="$mqtt_opts -u $MQTT_USERNAME"
  fi
  if [ -n "$MQTT_PASSWORD" ]; then
    mqtt_opts="$mqtt_opts -P $MQTT_PASSWORD"
  fi
  if [ "$MQTT_TLS" = "true" ]; then
    mqtt_opts="$mqtt_opts --tls"
    [ -n "$MQTT_CA_CERT" ] && mqtt_opts="$mqtt_opts --cafile $MQTT_CA_CERT"
    [ -n "$MQTT_CLIENT_CERT" ] && mqtt_opts="$mqtt_opts --cert $MQTT_CLIENT_CERT"
    [ -n "$MQTT_CLIENT_KEY" ] && mqtt_opts="$mqtt_opts --key $MQTT_CLIENT_KEY"
  fi
  eval mosquitto_pub $mqtt_opts
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
  mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$topic" -m "$payload" -i "$CLIENT_ID" \
    ${MQTT_USERNAME:+-u "$MQTT_USERNAME"} \
    ${MQTT_PASSWORD:+-P "$MQTT_PASSWORD"}
}


# Helper: subscribe to commands topic
subscribe_commands() {
  local topic="hubs/$CLIENT_ID/commands"
  mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$topic" -i "$CLIENT_ID" \
    ${MQTT_USERNAME:+-u "$MQTT_USERNAME"} \
    ${MQTT_PASSWORD:+-P "$MQTT_PASSWORD"} | while read -r message; do
    echo "Received command: $message"
    # Add command handling logic here if needed
  done &
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
        $first || sensors_array+=","; first=false
        sensors_array+="{\"name\":\"$friendly_name\",\"type\":\"$sensor_type\",\"value\":$state}"
      done < <(echo "$sensors_json" | jq -c '.')
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
