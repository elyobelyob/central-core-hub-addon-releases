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

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_registry_set_env_token_auth_fail(tmp_path, monkeypatch):
    # Set an env token expected by handlers
    monkeypatch.setenv("REGISTRY_TOKEN", "env-secret")
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/registry/set"
    # payload without token should fail auth
    payload = json.dumps({"command_id": "c-reg", "payload": {"entries": []}})

    handlers.handle_message(client, Msg(topic), payload, None, None, None)

    # find failed completion ack
    comp = None
    for t, payload_str, qos in client.published:
        try:
            p = json.loads(payload_str)
        except Exception:
            continue
        if p.get("status") in ("failed", "completed"):
            comp = p
            break
    assert comp is not None
    res = comp.get("result") or {}
    assert res.get("reason") == "auth_failed"
