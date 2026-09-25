import importlib.util
import pathlib
import json


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
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.ha_readback_after_set = True
        self.preferred_sensors_topic = "pref/topic"
        self.vault_topic = "vault/topic"
        self.selected_sensors = None
        self.publishes = []

    def _publish(self, topic, payload, qos=0):
        self.publishes.append((topic, payload, qos))

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"


def test_set_write_form_refused_and_nothing_published():
    client = FakeClient()
    R = _RecordingRequests()
    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})
    payload = {"command_id": "f1", "payload": {"sensors": [{"entity_id": "sensor.z", "state": "x"}]}}
    handlers.handle_message(client, msg, json.dumps(payload), None, None, None, requests=R)

    assert R.calls == []
    topics = [t for t, _, _ in client.publishes]
    # only the command's ACKs: no fallback telemetry, no vault reminder
    assert client.preferred_sensors_topic not in topics
    assert client.vault_topic not in topics
    comp = _secure_final_ack(client.publishes)
    assert comp["status"] == "failed" and comp["result"]["reason"] == "invalid_payload"


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
