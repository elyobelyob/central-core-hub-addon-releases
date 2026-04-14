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


def test_sensors_set_readback_get_raises_fallbacks_to_sent_state():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps(
        {"command_id": "c-getfail", "payload": {"sensors": [{"entity_id": "sensor.x", "state": "on"}]}}
    )

    # fake requests: post succeeds, get raises exception to trigger fallback
    class FakeReq:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            return _FakeResp({})

        @staticmethod
        def get(url, headers=None, timeout=None):
            raise RuntimeError("readback failed")

    handlers.handle_message(client, Msg(topic), payload, None, None, None, requests=FakeReq)

    # Expect completion ack published with detailed result including data
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
    # If readback failed, handlers should still include the sent state in the data
    result = comp.get("result") or {}
    data = result.get("data") or {}
    # when readback failed, code assigns the requested state as readback value
    assert data.get("sensor.x") == "on"
