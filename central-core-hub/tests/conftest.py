import sys
import types

# Provide a test shim for the external `central_core_mqtt_shared` package
# so tests do not need network access or real package installs.
_shared = types.ModuleType("central_core_mqtt_shared")

_shared.TELEMETRY_TOPIC_TMPL = "telemetry/{client_id}"
_shared.CMD_BASE_TMPL = "hubs/{client_id}/cmd"
_shared.PREFERRED_SENSORS_TOPIC_TMPL = "hubs/{client_id}/telemetry/sensors"
_shared.CMD_SUB_TMPL = "hubs/{client_id}/cmd/+"

# Also set older/alternate names some modules may try to read
_shared.TELEMETRY_TOPIC = _shared.TELEMETRY_TOPIC_TMPL
_shared.PREFERRED_SENSORS_TOPIC = _shared.PREFERRED_SENSORS_TOPIC_TMPL
_shared.CMD_BASE = _shared.CMD_BASE_TMPL
_shared.CMD_SUB = _shared.CMD_SUB_TMPL

sys.modules["central_core_mqtt_shared"] = _shared
