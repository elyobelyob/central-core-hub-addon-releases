"""MQTT topic templates shared by central-core-hub.

This module prefers importing topic constants from the external
`central_core_mqtt_shared` package (installed via `requirements.txt`) if
available. If not present, sensible defaults are provided so the add-on
continues to operate in development/test environments.
"""

from typing import Any


def _try_get_module(name: str) -> Any:
    try:
        mod = __import__(name)
        return mod
    except Exception:
        return None


# Attempt to import the shared mqtt constants package (if installed).
_shared = _try_get_module("central_core_mqtt_shared") or _try_get_module("central-core-mqtt-shared")


# Templates use `{client_id}` placeholder to be formatted by callers.
TELEMETRY_TOPIC_TMPL = (
    getattr(_shared, "TELEMETRY_TOPIC", None)
    or getattr(_shared, "TELEMETRY_TOPIC_TMPL", None)
    or "telemetry/{client_id}"
)

PREFERRED_SENSORS_TOPIC_TMPL = (
    getattr(_shared, "PREFERRED_SENSORS_TOPIC", None)
    or getattr(_shared, "PREFERRED_SENSORS_TOPIC_TMPL", None)
    or "hubs/{client_id}/telemetry/sensors"
)

CMD_BASE_TMPL = (
    getattr(_shared, "CMD_BASE", None) or getattr(_shared, "CMD_BASE_TMPL", None) or "hubs/{client_id}/v1/cmd"
)

CMD_SUB_TMPL = (
    getattr(_shared, "CMD_SUB", None) or getattr(_shared, "CMD_SUB_TMPL", None) or "hubs/{client_id}/v1/cmd/+"
)


__all__ = [
    "TELEMETRY_TOPIC_TMPL",
    "PREFERRED_SENSORS_TOPIC_TMPL",
    "CMD_BASE_TMPL",
    "CMD_SUB_TMPL",
]
