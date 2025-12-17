import json as _json
import sys
import types
import typing
import importlib.util as _importlib_util
from pathlib import Path as _Path
import pytest as _pytest
import time as _time
import os as _os


class _TopicsModule(types.ModuleType):
    TELEMETRY_SYSTEM: str
    TELEMETRY_SENSORS: str
    CMD_CONFIG_UPDATE: str
    CMD_GENERIC: str
    ACK_GENERIC: str
    build_topic: typing.Callable[..., str]


# Provide a test shim for the external `central_core_mqtt_shared` package.
# Tests should import the package and use `topics.build_topic(...)` and
# the `schemas` models; do not expose legacy top-level constants here.

# Minimal `topics` helper expected by runtime code
topics_mod = _TopicsModule("central_core_mqtt_shared.topics")


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


# Typed schemas module shim
class _SchemasModule(types.ModuleType):
    SystemTelemetry: typing.Type[_BaseModelShim]
    SensorsTelemetry: typing.Type[_BaseModelShim]


schemas_mod = _SchemasModule("central_core_mqtt_shared.schemas")
schemas_mod.SystemTelemetry = SystemTelemetry
schemas_mod.SensorsTelemetry = SensorsTelemetry


# Create the package module and attach submodules to match the real package
class _CentralCoreMqttShared(types.ModuleType):
    topics: _TopicsModule
    schemas: _SchemasModule


central_mod = _CentralCoreMqttShared("central_core_mqtt_shared")
central_mod.topics = topics_mod
central_mod.schemas = schemas_mod

sys.modules["central_core_mqtt_shared"] = central_mod
sys.modules["central_core_mqtt_shared.topics"] = topics_mod
sys.modules["central_core_mqtt_shared.schemas"] = schemas_mod


# Test-wide HA websocket shim to prevent real network attempts during unit tests.


def _ensure_ha_module():
    try:
        import ha_client as _ha

        return _ha
    except Exception:
        # Load the local `ha_client.py` module so we can patch it for tests
        repo_root = _Path(__file__).resolve().parents[1]
        ha_path = repo_root / "ha_client.py"
        spec = _importlib_util.spec_from_file_location("ha_client", str(ha_path))
        if spec is None or getattr(spec, "loader", None) is None:
            return None
        mod = _importlib_util.module_from_spec(spec)
        loader = spec.loader
        assert loader is not None
        loader.exec_module(mod)
        sys.modules["ha_client"] = mod
        return mod


class _FakeSock:
    def send(self, data):
        return None

    def recv(self):
        # Short sleep to simulate non-blocking behavior in tests
        _time.sleep(0.001)
        return ""

    def close(self):
        return None


class _FakeWSModule:
    def create_connection(self, *args, **kwargs):
        return _FakeSock()


@_pytest.fixture(autouse=True)
def _patch_ha_ws(monkeypatch):
    """Autouse fixture: patch `ha_client.websocket`, silence HA WS logs,
    and temporarily suppress print output to avoid noisy connection errors.
    """
    ha = _ensure_ha_module()
    # Silence instance logging method to avoid noisy output
    if ha is not None:
        try:
            monkeypatch.setattr(ha.HAWebSocketListener, "_log", lambda self, m: None)
        except Exception:
            pass
        # Replace websocket implementation with a fake module that returns a harmless socket
        try:
            monkeypatch.setattr(ha, "websocket", _FakeWSModule())
        except Exception:
            pass

    # Redirect stdout to devnull for the duration of the test to suppress prints
    orig_stdout = sys.stdout
    devnull = open(_os.devnull, "w")
    sys.stdout = devnull
    try:
        yield
    finally:
        sys.stdout = orig_stdout
        try:
            devnull.close()
        except Exception:
            pass
