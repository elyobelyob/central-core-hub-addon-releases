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


def test_sensors_set_readback_success():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps({"command_id": "c1", "payload": {"sensors": [{"entity_id": "sensor.a", "state": "42"}]}})

    # fake requests: post succeeds, get returns readback with attributes and timestamps
    class FakeReq:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            return _FakeResp({})

        @staticmethod
        def get(url, headers=None, timeout=None):
            return _FakeResp(
                {
                    "entity_id": "sensor.a",
                    "state": "42",
                    "attributes": {"friendly_name": "A", "device_class": "opening"},
                    "last_changed": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )

    handlers.handle_message(client, Msg(topic), payload, None, None, None, requests=FakeReq)

    # Expect a completion ack published
    assert any("/v1/ack/" in t for t, _, _ in client.published)
    # completion payload should include 'result' with set list
    comp = None
    for t, payload_str, qos in client.published:
        try:
            p = json.loads(payload_str)
        except Exception:
            continue
        if p.get("status") == "completed":
            comp = p
            break
    assert comp is not None
    assert comp.get("status") == "completed"
    assert "result" in comp


def test_sensors_set_no_ha_config_publishes_failed():
    client = DummyClient()
    client.ha_api_url = None
    client.ha_api_token = None
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps({"command_id": "c2", "payload": {"sensors": [{"entity_id": "sensor.b", "state": "on"}]}})

    handlers.handle_message(client, Msg(topic), payload, None, None, None, requests=None)

    # Should publish completion ack with failed entry
    comp = None
    for t, payload_str, qos in client.published:
        try:
            p = json.loads(payload_str)
        except Exception:
            continue
        if p.get("status") == "completed":
            comp = p
            break
    assert comp is not None
    # result.failed should contain reason no_ha_config
    res = comp.get("result")
    assert res is not None
    assert any((f.get("reason") == "no_ha_config") for f in res.get("failed", []))
