import json
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


def test_sensors_set_readback_get_failure_falls_back(monkeypatch):
    handlers = load_handlers_module()
    client = DummyClient("setcli")
    client.ha_api_url = "http://ha"
    client.ha_api_token = "tok"
    client.ha_readback_after_set = True

    # fake requests: post succeeds, get raises
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"state": "on", "attributes": {}}

    class FakeRequests:
        def post(self, url, headers=None, json=None, timeout=None):
            return FakeResp()

        def get(self, url, headers=None, timeout=None):
            raise RuntimeError("get failed")

    requests = FakeRequests()

    cmd = {
        "command_id": "set1",
        "payload": {"sensors": [{"entity_id": "sensor.x", "state": "on"}]},
    }
    payload_str = json.dumps(cmd)
    msg = Msg(f"hubs/{client.client_id}/v1/cmd/sensors/set")

    handlers.handle_message(client, msg, payload_str, None, None, None, requests=requests)

    # Should publish enhanced completion ACK including sensors_reported
    joined = "\n".join(p[1] for p in client.publishes)
    assert "sensor.x" in joined, f"expected sensor.x in publishes: {client.publishes}"
