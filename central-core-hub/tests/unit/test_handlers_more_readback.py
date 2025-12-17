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


def test_poll_success_publishes_telemetry_and_vault():
    client = FakeClient()

    def fetch_sensors(url, token):
        return [
            {
                "entity_id": "sensor.one",
                "state": "on",
                "attributes": {"device_class": "door", "friendly_name": "One"},
            }
        ]

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/poll"})
    payload = {"command_id": "p2", "payload": {"sensors": ["door"]}}

    handlers.handle_message(client, msg, json.dumps(payload), fetch_sensors, None, None)

    # preferred sensors topic and vault reminder should be published
    topics = [t for t, _, _ in client.publishes]
    assert client.preferred_sensors_topic in topics
    assert client.vault_topic in topics


def test_set_list_of_dicts_posts_and_completes():
    client = FakeClient()
    client.ha_readback_after_set = False

    class R:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            class Resp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"ok": True}

            return Resp()

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})
    payload = {"command_id": "s3", "payload": {"sensors": [{"entity_id": "sensor.a", "state": "1"}]}}

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None, requests=R)

    # find completion ack with results showing set
    found = False
    for _, p, _ in client.publishes:
        try:
            obj = json.loads(p)
        except Exception:
            continue
        if obj.get("status") == "completed":
            if obj.get("result", {}).get("set"):
                found = True
                break
    assert found
