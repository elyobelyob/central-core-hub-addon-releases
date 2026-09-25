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


class FakeClient:
    def __init__(self, client_id="cid"):
        self.client_id = client_id
        self.publishes = []

    def _publish(self, topic, payload, qos=0):
        self.publishes.append((topic, payload, qos))

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"


def test_registry_set_writes_local_when_mqtt_missing(tmp_path, monkeypatch):
    """Without mqtt_client, a token-authorised update goes next to handlers.py;
    without a token nothing is written."""
    monkeypatch.setitem(sys.modules, "mqtt_client", types.SimpleNamespace())
    target = pathlib.Path(__file__).parents[2] / "SENSOR_REGISTRY_from_mqtt.json"
    msg = type("M", (), {"topic": "hubs/cid/v1/cmd/registry/set"})
    entries = [{"entity_id": "sensor.a", "provide": True}]
    try:
        monkeypatch.delenv("REGISTRY_TOKEN", raising=False)
        client = FakeClient()
        handlers.handle_message(client, msg, json.dumps({"command_id": "rnm0", "payload": {"entries": entries}}), None, None, None)
        assert not target.exists()
        assert _secure_final_ack(client.publishes)["result"]["reason"] == "registry_updates_disabled"

        monkeypatch.setenv("REGISTRY_TOKEN", "tok-1")
        payload = {"command_id": "rnm1", "payload": {"token": "tok-1", "entries": entries}}
        handlers.handle_message(FakeClient(), msg, json.dumps(payload), None, None, None)
        assert target.exists()
        data = json.loads(target.read_text())
        assert data == {"entries": entries}
    finally:
        try:
            target.unlink()
        except Exception:
            pass


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
