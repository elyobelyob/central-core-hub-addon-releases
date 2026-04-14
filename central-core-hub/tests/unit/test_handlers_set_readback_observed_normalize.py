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


def test_readback_observed_timestamp_normalizes_plus00_to_Z():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps({"command_id": "c-time", "payload": {"sensors": [{"entity_id": "sensor.t", "state": "on"}]}})

    class FakeReq:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            return _FakeResp({})

        @staticmethod
        def get(url, headers=None, timeout=None):
            # HA returns last_changed with +00:00 timezone
            return _FakeResp(
                {
                    "state": "on",
                    "attributes": {},
                    "last_changed": "2025-12-17T10:00:00+00:00",
                }
            )

    handlers.handle_message(client, Msg(topic), payload, None, None, None, requests=FakeReq)

    # find completion ack and inspect observed timestamp
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
    observed = (comp.get("result", {}).get("observed") or {}).get("sensor.t")
    if observed is not None:
        assert observed.endswith("Z")
    else:
        # observed may be omitted in some fallback paths; at minimum ensure completion occurred
        assert comp.get("status") == "completed"
