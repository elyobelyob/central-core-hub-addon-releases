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


class FakeResponse:
    def __init__(self, data=None):
        self._data = data or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_sensors_set_list_reports_current_state_without_readback_calls():
    client = FakeClient()
    R = _RecordingRequests()

    def fetch(url, token):
        return [
            {
                "entity_id": "sensor.foo",
                "state": "on",
                "attributes": {"friendly_name": "Foo"},
                "last_changed": "2025-01-01T00:00:00+00:00",
            }
        ]

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})
    payload = {"command_id": "cmd1", "payload": {"sensors": ["sensor.foo"]}}
    handlers.handle_message(client, msg, json.dumps(payload), fetch, None, None, requests=R)

    assert R.calls == []
    comp = _secure_final_ack(client.publishes)
    assert comp["status"] == "completed"
    assert comp["result"]["data"] == {"sensor.foo": "on"}
    assert comp["result"]["names"] == {"sensor.foo": "Foo"}
    assert "sensor.foo" in comp["result"]["observed"]


def test_sensors_set_readback_form_is_refused():
    client = FakeClient()
    R = _RecordingRequests()
    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})
    payload = {"command_id": "cmd1b", "payload": {"sensors": [{"entity_id": "sensor.foo", "state": "on"}]}}
    handlers.handle_message(client, msg, json.dumps(payload), None, None, None, requests=R)
    assert R.calls == []
    assert _secure_final_ack(client.publishes)["result"]["reason"] == "invalid_payload"


def test_sensors_set_write_form_refused_without_ha_config():
    client = FakeClient()
    client.ha_api_url = ""
    client.ha_api_token = ""

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})
    payload = {"command_id": "cmd2", "payload": {"sensors": [{"entity_id": "sensor.bar", "state": "off"}]}}
    handlers.handle_message(client, msg, json.dumps(payload), None, None, None, requests=None)

    comp = _secure_final_ack(client.publishes)
    # refused for its shape, before HA configuration is even considered
    assert comp["status"] == "failed"
    assert comp["result"] == {"reason": "invalid_payload"}


def test_sensors_set_list_without_ha_config_completes_with_empty_report():
    client = FakeClient()
    client.ha_api_url = ""
    client.ha_api_token = ""

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})
    payload = {"command_id": "cmd3", "payload": {"sensors": ["sensor.bar"]}}
    handlers.handle_message(client, msg, json.dumps(payload), lambda a, b: None, None, None, requests=None)

    comp = _secure_final_ack(client.publishes)
    assert comp["status"] == "completed"
    assert comp["result"]["selected"] == ["sensor.bar"]
    assert comp["result"]["sensors_reported"] == []


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
