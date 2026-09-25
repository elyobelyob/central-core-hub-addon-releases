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
        self.vault_topic = "tele/vault"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.ha_readback_after_set = True
        self.selected_sensors = None

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


def test_sensors_set_list_reports_attributes_and_timestamps():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    req = _RecordingRequests()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def fetch(url, token):
        return [
            {
                "entity_id": "sensor.a",
                "state": "42",
                "attributes": {"friendly_name": "A", "device_class": "opening"},
                "last_changed": now,
            }
        ]

    payload = json.dumps({"command_id": "c1", "payload": {"sensors": ["sensor.a"]}})
    handlers.handle_message(client, Msg(topic), payload, fetch, None, None, requests=req)

    assert req.calls == []
    comp = _secure_final_ack(client.published)
    assert comp["status"] == "completed"
    res = comp["result"]
    assert res["sensors_reported"] == ["sensor.a"]
    assert res["device_classes"] == {"sensor.a": "opening"}
    assert res["names"] == {"sensor.a": "A"}
    assert res["observed"]["sensor.a"]

    # the old readback form is refused
    payload = json.dumps({"command_id": "c1b", "payload": {"sensors": [{"entity_id": "sensor.a", "state": "42"}]}})
    handlers.handle_message(client, Msg(topic), payload, fetch, None, None, requests=req)
    assert req.calls == []
    assert _secure_final_ack(client.published)["result"]["reason"] == "invalid_payload"


def test_sensors_set_no_ha_config_write_form_publishes_failed():
    client = DummyClient()
    client.ha_api_url = None
    client.ha_api_token = None
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps({"command_id": "c2", "payload": {"sensors": [{"entity_id": "sensor.b", "state": "on"}]}})
    handlers.handle_message(client, Msg(topic), payload, None, None, None, requests=None)
    comp = _secure_final_ack(client.published)
    assert comp["status"] == "failed"
    assert comp["result"]["reason"] == "invalid_payload"


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
