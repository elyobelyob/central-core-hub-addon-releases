import json
import types
import sys
from pathlib import Path
import importlib.util


def load_handlers_module():
    p = Path(__file__).resolve().parents[2] / "central-core-hub" / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DummyClient:
    def __init__(self, client_id="C1"):
        self.client_id = client_id
        self.publishes = []
        self.ha_api_url = "http://ha"
        self.ha_api_token = "token"
        self.ha_readback_after_set = True
        self.preferred_sensors_topic = "pref/topic"
        self.vault_topic = "vault/topic"
        self.selected_sensors = None
        self.registry_token = None

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.publishes.append((topic, payload, qos))

    def reload_sensor_registry(self):
        # noop hook
        pass


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_registry_auth_failed_publishes_ack(tmp_path, monkeypatch):
    handlers = load_handlers_module()
    client = DummyClient("testcli")
    client.registry_token = "expected"

    cmd = {"command_id": "cmd1", "payload": {"entries": [], "token": "wrong"}}
    payload_str = json.dumps(cmd)
    msg = Msg(f"hubs/{client.client_id}/v1/cmd/registry/set")

    handlers.handle_message(client, msg, payload_str, None, None, None)

    # Expect at least one published completion/failed ack mentioning auth_failed
    found = any("auth_failed" in (p[1] or "") for p in client.publishes)
    assert found, f"expected auth_failed in publishes: {client.publishes}"


def test_registry_missing_payload_publishes_failed(tmp_path):
    handlers = load_handlers_module()
    client = DummyClient("testcli2")

    # Send a command with no payload
    cmd = {"command_id": "cmd2"}
    payload_str = json.dumps(cmd)
    msg = Msg(f"hubs/{client.client_id}/v1/cmd/registry/set")

    handlers.handle_message(client, msg, payload_str, None, None, None)

    # One of the publishes should include missing_payload
    found = any("missing_payload" in (p[1] or "") for p in client.publishes)
    assert found, f"expected missing_payload in publishes: {client.publishes}"


def test_sensors_set_readback_form_is_refused_and_list_reports(monkeypatch, tmp_path):
    handlers = load_handlers_module()
    # keep the persisted selection out of the add-on directory
    monkeypatch.setitem(sys.modules, "mqtt_client", types.SimpleNamespace(SELECTED_SENSORS_FILE=tmp_path / "sel.json"))
    client = DummyClient("setcli")
    client.ha_api_url = "http://ha"
    client.ha_api_token = "tok"
    client.ha_readback_after_set = True
    requests = _RecordingRequests()
    msg = Msg(f"hubs/{client.client_id}/v1/cmd/sensors/set")

    cmd = {"command_id": "set1", "payload": {"sensors": [{"entity_id": "sensor.x", "state": "on"}]}}
    handlers.handle_message(client, msg, json.dumps(cmd), None, None, None, requests=requests)
    assert requests.calls == []
    assert _secure_final_ack(client.publishes)["result"]["reason"] == "invalid_payload"

    cmd = {"command_id": "set2", "payload": {"sensors": ["sensor.x"]}}
    fetch = lambda url, token: [{"entity_id": "sensor.x", "state": "on", "attributes": {}}]  # noqa: E731
    handlers.handle_message(client, msg, json.dumps(cmd), fetch, None, None, requests=requests)
    comp = _secure_final_ack(client.publishes)
    assert comp["result"]["sensors_reported"] == ["sensor.x"]


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
