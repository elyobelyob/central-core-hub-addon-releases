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


def test_sensors_set_readback_success():
    client = FakeClient()

    # requests module that simulates POST success and GET readback
    class R:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            return FakeResponse({"ok": True})

        @staticmethod
        def get(url, headers=None, timeout=None):
            # return a readback payload
            return FakeResponse({
                "entity_id": "sensor.foo",
                "state": "on",
                "attributes": {"friendly_name": "Foo"},
                "last_changed": "2025-01-01T00:00:00+00:00",
            })

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})
    payload = {
        "command_id": "cmd1",
        "payload": {"sensors": [{"entity_id": "sensor.foo", "state": "on"}]},
    }

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None, requests=R)

    # ensure we published a completion ack that includes readback data
    found = False
    for _, p, _ in client.publishes:
        try:
            obj = json.loads(p)
        except Exception:
            continue
        if obj.get("status") == "completed" and isinstance(obj.get("result"), dict):
            res = obj.get("result")
            if "data" in res and res.get("data", {}).get("sensor.foo") == "on":
                found = True
                break
    assert found


def test_sensors_set_no_ha_config():
    client = FakeClient()
    client.ha_api_url = ""
    client.ha_api_token = ""

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})
    payload = {
        "command_id": "cmd2",
        "payload": {"sensors": [{"entity_id": "sensor.bar", "state": "off"}]},
    }

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None, requests=None)

    # completion ack should include failed reason no_ha_config
    found = False
    for _, p, _ in client.publishes:
        try:
            obj = json.loads(p)
        except Exception:
            continue
        if obj.get("status") == "completed":
            res = obj.get("result")
            if res and res.get("failed") and res.get("failed")[0].get("reason") == "no_ha_config":
                found = True
                break
    assert found
