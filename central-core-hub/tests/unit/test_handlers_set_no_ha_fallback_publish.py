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


def test_sensors_set_no_ha_write_form_publishes_only_acks():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    cmd = {"command_id": "noha1", "payload": {"sensors": [{"entity_id": "sensor.x", "state": "on"}]}}
    handlers.handle_message(c, Msg(topic), json.dumps(cmd), None, None, None)

    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/noha1"
    assert {p["topic"] for p in c.published} == {ack_topic}
    acks = [json.loads(p["payload"]) for p in c.published]
    assert [a["status"] for a in acks] == ["acknowledged", "failed"]
    assert acks[-1]["result"] == {"reason": "invalid_payload"}


def test_sensors_set_no_ha_list_form_still_reminds_vault_and_completes():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    cmd = {"command_id": "noha2", "payload": {"sensors": ["sensor.x"]}}
    handlers.handle_message(c, Msg(topic), json.dumps(cmd), None, None, None)

    rem = [json.loads(p["payload"]) for p in c.published if p["topic"] == c.vault_topic]
    assert rem and rem[-1]["selected_sensors"] == ["sensor.x"]
    comp = _secure_final_ack(c.published)
    assert comp["status"] == "completed"
    assert comp["result"]["selected"] == ["sensor.x"]
    assert comp["result"]["data"] == {}


# --- helpers for the secure sensors/set and registry/set behaviour ---------


def _secure_final_ack(records):
    """Last non-"acknowledged" ACK body among recorded publishes (any record shape)."""
    last = None
    for r in records:
        topic, payload = (r["topic"], r["payload"]) if isinstance(r, dict) else (r[0], r[1])
        if "/ack/" not in topic:
            continue
        body = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        if isinstance(body, dict) and body.get("status") != "acknowledged":
            last = body
    return last


class _RecordingRequests:
    """A `requests` stand-in that records calls and refuses every one."""

    def __init__(self):
        self.calls = []

    def post(self, url, *a, **k):
        self.calls.append(("POST", url))
        raise AssertionError(f"hub must not POST to Home Assistant: {url}")

    def get(self, url, *a, **k):
        self.calls.append(("GET", url))
        raise AssertionError(f"sensors/set must not call Home Assistant per entity: {url}")
