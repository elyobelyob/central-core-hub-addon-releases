import json
import importlib.util
from pathlib import Path


def _load_modules():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mqtt_mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mqtt_mod)

    src2 = repo_root / "central-core-hub" / "handlers.py"
    spec2 = importlib.util.spec_from_file_location("handlers", str(src2))
    if spec2 is None or getattr(spec2, "loader", None) is None:
        raise ImportError("could not load spec")
    handlers_mod = importlib.util.module_from_spec(spec2)
    hloader = spec2.loader
    assert hloader is not None
    hloader.exec_module(handlers_mod)
    return mqtt_mod, handlers_mod


class DummyClient:
    def __init__(self):
        self.published = []
        self.client_id = "unit-hub"
        self.preferred_sensors_topic = f"hubs/{self.client_id}/v1/telemetry/sensors"
        self.vault_topic = f"hubs/{self.client_id}/v1/vault/reminder"

    def _publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class Msg:
    def __init__(self, topic):
        self.topic = topic
        self.payload = b""


def test_sensors_set_empty_selection_publishes_fallback_telemetry_and_vault_reminder():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    cmd = {"command_id": "s_empty", "payload": {"sensors": []}}
    payload = json.dumps(cmd)
    msg = Msg(topic)

    # Provide a fetch_sensors callable so the monitor telemetry path runs
    handlers.handle_message(c, msg, payload, lambda a, b: [], None, None)

    # Find vault reminder publish
    rem = None
    for p in c.published:
        if p["topic"] == c.vault_topic:
            rem = json.loads(p["payload"]) if p["payload"] else None
            break
    assert rem is not None, f"expected vault reminder publish to {c.vault_topic}, got: {c.published}"
    assert rem.get("selected_sensors") == [], "expected selected_sensors empty list in reminder"

    # Expect completion ACK for the command and that it contains the monitor telemetry
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/s_empty"
    found = None
    for p in c.published:
        if p["topic"] == ack_topic:
            payload = p.get("payload")
            if payload and ("completed" in payload or "result" in payload):
                found = json.loads(payload)
                break
    assert found is not None, f"expected completion ack on {ack_topic} (completed), got: {c.published}"
    # When monitor telemetry existed the ACK may include telemetry fields
    assert "result" in found
    assert ("data" in found["result"]) or (found["result"].get("selected") == [])
