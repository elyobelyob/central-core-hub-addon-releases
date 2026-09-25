import importlib.util
import pathlib
import json
from datetime import datetime, timezone


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
    def __init__(self):
        self.client_id = "cid"
        self.published = []
        self.preferred_sensors_topic = "tele/ps"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_list_observed_timestamp_is_normalized():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    req = _RecordingRequests()

    def fetch(url, token):
        return [{"entity_id": "sensor.t", "state": "on", "attributes": {}, "last_changed": "2025-12-17T10:00:00+00:00"}]

    payload = json.dumps({"command_id": "c-time", "payload": {"sensors": ["sensor.t"]}})
    handlers.handle_message(client, Msg(topic), payload, fetch, None, None, requests=req)
    assert req.calls == []
    comp = _secure_final_ack(client.published)
    observed = comp["result"]["observed"]["sensor.t"]
    parsed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed == datetime(2025, 12, 17, 10, 0, tzinfo=timezone.utc)


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
