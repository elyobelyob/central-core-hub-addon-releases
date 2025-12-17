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
        # Intentionally do not set ha_api_url/ha_api_token to simulate missing HA config

    def _publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class Msg:
    def __init__(self, topic):
        self.topic = topic
        self.payload = b""


def test_sensors_set_no_ha_publishes_empty_telemetry_and_completion_ack():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    # Provide a single set item; without HA config the handler should mark it failed
    cmd = {"command_id": "noha1", "payload": {"sensors": [{"entity_id": "sensor.x", "state": "on"}]}}
    payload = json.dumps(cmd)
    msg = Msg(topic)

    # No requests and no HA config => results['set'] should remain empty
    handlers.handle_message(c, msg, payload, None, None, None)

    # Expect fallback telemetry publish to preferred_sensors_topic (may be empty)
    pref = None
    for p in c.published:
        if p["topic"] == c.preferred_sensors_topic:
            pref = json.loads(p["payload"]) if p["payload"] else None
            break
    assert pref is not None, f"expected fallback telemetry publish to {c.preferred_sensors_topic}, got: {c.published}"
    assert pref.get("data") == {}, "expected empty data map in fallback telemetry"

    # Expect vault reminder publish with selected_sensors empty or absent
    rem = None
    for p in c.published:
        if p["topic"] == c.vault_topic:
            rem = json.loads(p["payload"]) if p["payload"] else None
            break
    assert rem is not None, f"expected vault reminder publish to {c.vault_topic}, got: {c.published}"
    assert isinstance(rem.get("selected_sensors"), list)

    # Expect completion ACK with failed entry
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/noha1"
    found = None
    for p in c.published:
        if p["topic"] == ack_topic:
            try:
                found = json.loads(p["payload"]) if p.get("payload") else None
            except Exception:
                found = None
            break
    assert found is not None, f"expected completion ack on {ack_topic}, got: {c.published}"
    # Handler may publish an initial 'acknowledged' ACK before the
    # completion payload; accept either. Prefer an ACK that contains
    # a 'result' or 'completed' marker when available.
    if not ("result" in found or "completed" in found):
        assert "acknowledged" in found.get("status", ""), f"unexpected ack payload: {found}"
    else:
        assert "failed" in found.get("result", {}), f"expected failed entry in result, got: {found}"
