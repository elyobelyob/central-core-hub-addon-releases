import importlib.util
import pathlib
import json
import tempfile


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

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_sensors_set_persist_tempfile_raises(monkeypatch):
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps({"command_id": "c-persistfail", "payload": {"sensors": ["sensor.a"]}})

    # Provide fetch_sensors so monitor telemetry is built
    def fetch_sensors(url, token):
        return [
            {
                "entity_id": "sensor.a",
                "state": "1",
                "attributes": {"device_class": "temperature"},
            }
        ]

    # Cause tempfile.NamedTemporaryFile to raise to hit persistence failure branch
    def _bad_named_tempfile(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", _bad_named_tempfile)

    handlers.handle_message(client, Msg(topic), payload, fetch_sensors, None, None)

    # completion ack should still be published (should not crash)
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
