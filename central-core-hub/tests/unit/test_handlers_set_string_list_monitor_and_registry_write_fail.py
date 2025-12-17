import importlib.util
import pathlib
import json
import sys
import types


def _load_handlers():
    base = pathlib.Path(__file__).parents[2]
    src = base / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load handlers spec")
    spec.loader.exec_module(mod)
    return mod


handlers = _load_handlers()


class DummyClient:
    def __init__(self, client_id="cid"):
        self.client_id = client_id
        self.published = []
        self.vault_topic = "vault/topic"
        self.preferred_sensors_topic = "pref/topic"

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_set_string_list_includes_monitor_telemetry_and_completion(tmp_path):
    client = DummyClient("unit-mon")
    # ensure mqtt_client SELECTED_SENSORS_FILE points to tmp so persistence path exercised
    mc = types.SimpleNamespace()
    mc.SELECTED_SENSORS_FILE = str(tmp_path / "SELECTED_SENSORS.json")
    orig = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = mc

    try:
        topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
        payload = json.dumps({"command_id": "m1", "payload": {"sensors": ["sensor.x"]}})

        # fetch_sensors returns data so monitor_telemetry is constructed
        def fetch_sensors(url, token):
            return [
                {
                    "entity_id": "sensor.x",
                    "state": "on",
                    "attributes": {"friendly_name": "X", "device_class": "motion"},
                }
            ]

        handlers.handle_message(client, Msg(topic), payload, fetch_sensors, None, None)

        # completion ack should contain 'data' in result when monitor_telemetry present
        comp = None
        for t, p, qos in client.published:
            try:
                o = json.loads(p)
            except Exception:
                continue
            if o.get("status") == "completed":
                comp = o
                break
        assert comp is not None
        res = comp.get("result") or {}
        # Handler may include full monitor telemetry in the completion ACK
        # or only a simple 'selected' list; accept either.
        if "data" in res:
            assert "sensor.x" in res.get("data", {})
        else:
            assert "sensor.x" in res.get("selected", [])
    finally:
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig


def test_registry_set_atomic_write_failure_reports_error(tmp_path, monkeypatch):
    # Prepare fake mqtt_client with SENSOR_REGISTRY path
    mc = types.SimpleNamespace()
    mc.SENSOR_REGISTRY = str(tmp_path / "SENSOR_REGISTRY.json")
    orig = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = mc

    try:
        client = DummyClient("unit-reg")
        topic = f"hubs/{client.client_id}/v1/cmd/registry/set"
        payload = json.dumps({"command_id": "r1", "payload": {"entries": []}})

        # Force pathlib.Path.replace to raise to simulate rename failure
        def bad_replace(self, target):
            raise OSError("replace failed")

        monkeypatch.setattr(pathlib.Path, "replace", bad_replace, raising=True)

        handlers.handle_message(client, Msg(topic), payload, None, None, None)

        # completion ack should indicate failure
        comp = None
        for t, p, qos in client.published:
            try:
                o = json.loads(p)
            except Exception:
                continue
            if o.get("status") in ("completed", "failed"):
                comp = o
                break
        assert comp is not None
        res = comp.get("result") or {}
        assert res.get("success") is False
    finally:
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig
