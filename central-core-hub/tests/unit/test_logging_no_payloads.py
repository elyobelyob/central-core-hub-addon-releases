"""F9 / perf #7: logs carry topic, length and result code, never payloads or states.

Payloads appear only when debug logging is on, redacted and truncated.
"""

import importlib
import json
import types

import pytest

SECRET = "tok_SECRET_VALUE"


@pytest.fixture
def mc(monkeypatch, tmp_path):
    mod = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mod, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    lines = []
    monkeypatch.setattr(mod, "_log", lambda msg, file=None: lines.append(str(msg)))
    monkeypatch.setattr(mod, "_DEBUG_LOGGING", False)
    mod._captured = lines
    return mod


def _client(mc, **opts):
    c = mc.CentralCoreClient(dict({"client_id": "hub1", "mqtt_host": "localhost"}, **opts))

    class _Paho:
        def __init__(self):
            self.sent = []

        def publish(self, topic, payload, qos=0, retain=False):
            self.sent.append((topic, payload))
            return types.SimpleNamespace(rc=0)

    c._client = _Paho()
    return c


def test_publish_logs_topic_length_and_rc_but_not_payload(mc):
    c = _client(mc)
    body = json.dumps({"data": {"sensor.a": SECRET}})
    c._publish("hubs/hub1/v1/telemetry/sensors", body)
    joined = "\n".join(mc._captured)
    assert SECRET not in joined
    assert "hubs/hub1/v1/telemetry/sensors" in joined
    assert f"len={len(body)}" in joined
    assert "rc=0" in joined


def test_debug_logging_shows_truncated_redacted_payload(mc, monkeypatch):
    monkeypatch.setattr(mc, "_DEBUG_LOGGING", True)
    c = _client(mc)
    pem = "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    body = json.dumps({"k": pem, "pad": "x" * 5000})
    c._publish("hubs/hub1/v1/telemetry/sensors", body)
    joined = "\n".join(mc._captured)
    assert "BEGIN PRIVATE KEY" not in joined
    assert "x" * 1000 not in joined
    assert "payload=" in joined


def test_debug_option_turns_on_payload_logging(mc):
    _client(mc, debug_logging=True)
    assert mc._DEBUG_LOGGING is True


def test_inbound_command_log_has_no_payload(mc):
    c = _client(mc)
    c.wait_for_commands = getattr(c, "wait_for_commands", lambda timeout=None: None)
    msg = types.SimpleNamespace(
        topic="hubs/hub1/v1/cmd/registry/set",
        payload=json.dumps({"command_id": "c1", "payload": {"token": SECRET}}).encode(),
        retain=False,
    )
    c.on_message(None, None, msg)
    c.wait_for_commands(timeout=5)
    joined = "\n".join(mc._captured)
    assert SECRET not in joined
    assert "hubs/hub1/v1/cmd/registry/set" in joined


def test_state_changes_are_not_logged_at_info(mc):
    c = _client(mc)
    c.selected_sensors = ["sensor.door_state"]
    c._on_ha_state_event("sensor.door_state", {"state": "unlocked_now", "attributes": {}})
    assert not any("unlocked_now" in line for line in mc._captured)


def test_entity_ids_are_counted_not_listed(mc, monkeypatch):
    c = _client(mc)
    c.selected_sensors = ["sensor.bedroom_motion", "sensor.kitchen"]
    c._last_monitor_log = 0
    monkeypatch.setattr(c, "publish_telemetry", lambda: None)
    monkeypatch.setattr(c, "publish_selected_sensor_changes", lambda: None)
    monkeypatch.setattr(c, "publish_sensors", lambda: None)
    c._connected = True
    c.run_iteration()
    joined = "\n".join(mc._captured)
    assert "bedroom_motion" not in joined
    assert "Periodic: HA WS monitoring sensors: 2" in joined
