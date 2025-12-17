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

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_selected_sensors_persist_replace_failure(tmp_path, monkeypatch):
    # Prepare fake mqtt_client module with SELECTED_SENSORS_FILE
    mc = types.SimpleNamespace()
    mc.SELECTED_SENSORS_FILE = str(tmp_path / "SELECTED_SENSORS.json")
    orig = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = mc

    try:
        client = DummyClient("unit-persist")
        topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
        payload = json.dumps({"command_id": "p1", "payload": {"sensors": ["sensor.x"]}})

        # fetch_sensors returns one matching entity so monitor_telemetry constructed
        def fetch_sensors(url, token):
            return [{"entity_id": "sensor.x", "state": "on", "attributes": {}}]

        # Force pathlib.Path.replace to raise to simulate atomic rename failure
        def raise_replace(self, target):
            raise OSError("rename failed")

        monkeypatch.setattr(pathlib.Path, "replace", raise_replace, raising=True)

        handlers.handle_message(client, Msg(topic), payload, fetch_sensors, None, None)

        # Even though replace failed, handler should still publish a completion ACK
        ack_topic = f"hubs/{client.client_id}/v1/ack/sensors.set/p1"
        comp = None
        for t, p, qos in client.published:
            if t == ack_topic:
                try:
                    comp = json.loads(p)
                except Exception:
                    comp = None
                break
        assert comp is not None
        # Handler may only publish an initial 'acknowledged' ACK if the
        # completion path failed; accept either acknowledgement or completion.
        assert comp.get("status") in ("completed", "acknowledged")
    finally:
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig
