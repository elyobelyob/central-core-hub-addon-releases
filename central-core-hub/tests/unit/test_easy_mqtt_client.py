import importlib.util
from pathlib import Path
import types


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_publish_returns_tuple_is_handled():
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "tup1"})

    class TClient:
        def publish(self, topic, payload, qos=0):
            return (0, 1)

    c._client = TClient()
    res = c._publish("t", "p", qos=1)
    assert res == (0, 1)


def test_on_message_passes_binary_payload_to_handler(monkeypatch):
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "bin1"})

    class BadPayload:
        def decode(self, *a, **k):
            raise RuntimeError("no decode")

    msg = types.SimpleNamespace(topic="hubs/bin/v1/cmd/test", payload=BadPayload())

    called = {}

    def fake_handle_message(client, msg_in, payload_str, *a, **k):
        # payload should be the '<binary>' sentinel
        called["payload"] = payload_str

    fake_mod = types.ModuleType("handlers")
    setattr(fake_mod, "handle_message", fake_handle_message)
    # ensure handlers module is found by on_message import
    import sys

    sys.modules["handlers"] = fake_mod

    c.on_message(None, None, msg)
    assert called.get("payload") == "<binary>"
