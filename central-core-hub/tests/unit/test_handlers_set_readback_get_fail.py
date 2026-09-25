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


class DummyClient:
    def __init__(self):
        self.client_id = "cid"
        self.published = []
        self.preferred_sensors_topic = "tele/ps"
        self.vault_topic = "tele/vault"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.ha_readback_after_set = True

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


def test_sensors_set_list_when_ha_fetch_fails_completes_with_empty_report():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    req = _RecordingRequests()

    def failing_fetch(url, token):
        raise RuntimeError("HA unreachable")

    payload = json.dumps({"command_id": "c-getfail", "payload": {"sensors": ["sensor.x"]}})
    handlers.handle_message(client, Msg(topic), payload, failing_fetch, None, None, requests=req)

    assert req.calls == []
    comp = _secure_final_ack(client.published)
    assert comp["status"] == "completed"
    # the selection is kept; no value is invented for it
    assert comp["result"]["selected"] == ["sensor.x"]
    assert comp["result"]["sensors_reported"] == []
    assert comp["result"]["data"] == {}

    # and the readback form itself is refused
    payload = json.dumps({"command_id": "c-getfail2", "payload": {"sensors": [{"entity_id": "sensor.x", "state": "on"}]}})
    handlers.handle_message(client, Msg(topic), payload, failing_fetch, None, None, requests=req)
    assert _secure_final_ack(client.published)["result"]["reason"] == "invalid_payload"


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
