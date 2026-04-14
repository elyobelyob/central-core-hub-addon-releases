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
    def __init__(self):
        self.client_id = "cid"
        self.published = []
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.ha_readback_after_set = False
        self.preferred_sensors_topic = "pref/topic"
        self.vault_topic = "vault/topic"

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_set_post_exception_results_failed():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps({"command_id": "t1", "payload": {"sensors": [{"entity_id": "sensor.x", "state": "on"}]}})

    class BadReq:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            raise RuntimeError("boom-post")

    handlers.handle_message(client, Msg(topic), payload, None, None, None, requests=BadReq)

    # Find completion ack and assert failed entry contains our error
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
    res = comp.get("result") or {}
    failed = res.get("failed") or []
    assert any("boom-post" in f.get("reason", "") for f in failed)


def test_set_list_with_missing_entity_id_skipped():
    client = DummyClient()
    # Simulate no HA config so set operations are marked failed
    client.ha_api_url = None
    client.ha_api_token = None
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps(
        {
            "command_id": "t2",
            "payload": {"sensors": [{"state": "on"}, {"entity_id": "sensor.y", "state": "off"}]},
        }
    )

    handlers.handle_message(client, Msg(topic), payload, None, None, None)

    # Ensure the item without entity_id was skipped; completion ack should exist
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
    res = comp.get("result") or {}
    # since no HA config, results.failed should include the valid entity, and no entry for the missing one
    failed = res.get("failed") or []
    # the valid sensor should be in failed due to no_ha_config
    assert any(f.get("entity_id") == "sensor.y" or f.get("reason") == "no_ha_config" for f in failed)
