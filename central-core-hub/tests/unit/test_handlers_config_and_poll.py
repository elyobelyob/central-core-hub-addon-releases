import json
import importlib.util
import pathlib


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
    def __init__(self, client_id="cid"):
        self.client_id = client_id
        self.published = []

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_config_update_success_publishes_completed():
    client = DummyClient("unit-cfg")

    def trigger_addon_update(version=None):
        return {"success": True, "version": version}

    client.trigger_addon_update = trigger_addon_update

    topic = f"hubs/{client.client_id}/v1/cmd/config/update"
    payload = json.dumps({"command_id": "cfg1", "payload": {"version": "1.2.3"}})

    handlers.handle_message(client, Msg(topic), payload, None, None, None)

    # Ensure a completion ack published with success True
    comp = None
    for t, p, qos in client.published:
        try:
            o = json.loads(p)
        except Exception:
            continue
        if o.get("status") == "completed":
            comp = o
            break
    assert comp is not None
    assert comp.get("result", {}).get("success") is True


def test_sensors_poll_early_return_no_sensors_requested():
    client = DummyClient("unit-poll")

    # fetch_sensors should not be called; make it fail if invoked
    def fetch_sensors_should_not_be_called(url, token):
        raise AssertionError("fetch_sensors called unexpectedly")

    topic = f"hubs/{client.client_id}/v1/cmd/sensors/poll"
    # payload with empty sensors list -> treated as falsy and should return early
    payload = json.dumps({"payload": {"sensors": []}})

    handlers.handle_message(client, Msg(topic), payload, fetch_sensors_should_not_be_called, None, None)

    # No publishes should have occurred
    assert client.published == []
