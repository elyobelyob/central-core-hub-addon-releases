import sys
import types
import json as _json

# Provide a test shim for the external `central_core_mqtt_shared` package.
# Tests should import the package and use `topics.build_topic(...)` and
# the `schemas` models; do not expose legacy top-level constants here.

# Minimal `topics` helper expected by runtime code
topics_mod = types.ModuleType("central_core_mqtt_shared.topics")


def _build_topic(template, **kwargs):
    try:
        return template.format(**kwargs)
    except Exception:
        return str(template)


topics_mod.build_topic = _build_topic
topics_mod.TELEMETRY_SYSTEM = "hubs/{hub_id}/v{version}/telemetry/system"
topics_mod.TELEMETRY_SENSORS = "hubs/{hub_id}/v{version}/telemetry/sensors"
topics_mod.CMD_CONFIG_UPDATE = "hubs/{hub_id}/v{version}/cmd/config/update"
topics_mod.CMD_GENERIC = "hubs/{hub_id}/v{version}/cmd/{domain}/{action}"
topics_mod.ACK_GENERIC = "hubs/{hub_id}/v{version}/ack/{command_name}/{command_id}"


# Minimal `schemas` shim: provides model classes with .json()
class _BaseModelShim:
    def __init__(self, **data):
        self._data = data

    def json(self):
        return _json.dumps(self._data)


class SystemTelemetry(_BaseModelShim):
    pass


class SensorsTelemetry(_BaseModelShim):
    pass


schemas_mod = types.ModuleType("central_core_mqtt_shared.schemas")
schemas_mod.SystemTelemetry = SystemTelemetry
schemas_mod.SensorsTelemetry = SensorsTelemetry


# Create the package module and attach submodules to match the real package
central_mod = types.ModuleType("central_core_mqtt_shared")
central_mod.topics = topics_mod
central_mod.schemas = schemas_mod

sys.modules["central_core_mqtt_shared"] = central_mod
sys.modules["central_core_mqtt_shared.topics"] = topics_mod
sys.modules["central_core_mqtt_shared.schemas"] = schemas_mod
