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
        # Intentionally missing HA settings to trigger no_ha_config
        self.ha_api_url = ""
        self.ha_api_token = None

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_sensors_set_no_ha_config_reports_failure():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps({"command_id": "c-noha", "payload": {"sensors": [{"entity_id": "sensor.x", "state": "on"}]}})

    # Provide a dummy requests object so the code path checks HA config
    handlers.handle_message(client, Msg(topic), payload, None, None, None, requests=object())

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
    res = comp.get("result") or {}
    failed = res.get("failed") or []
    assert any(f.get("entity_id") == "sensor.x" and f.get("reason") == "no_ha_config" for f in failed)
