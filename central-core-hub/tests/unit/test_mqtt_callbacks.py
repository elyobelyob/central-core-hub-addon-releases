import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyClientInner:
    def __init__(self):
        self.subscribed = []

    def subscribe(self, topic, qos=0):
        self.subscribed.append({"topic": topic, "qos": qos})


class DummyPub:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})

        class R:
            rc = 0

        return R()


def test_on_connect_subscribes_and_publishes(monkeypatch):
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    options = {"client_id": "cb-hub", "ha_api_url": "http://ha", "ha_api_token": "t"}
    c = CentralCoreClient(options)
    dummy_inner = DummyClientInner()
    # attach a client that has subscribe and publish
    c._client = dummy_inner
    # monkeypatch publish_sensors to record it was called by adding to published list
    called = {}

    def fake_publish_sensors():
        called["sensors"] = True

    monkeypatch.setattr(c, "publish_sensors", fake_publish_sensors)
    # simulate on_connect call
    c.on_connect(c._client, None, None, 0)
    # should have subscribed to cmd_sub_topic
    assert any(s["topic"] == c.cmd_sub_topic for s in dummy_inner.subscribed)
    assert called.get("sensors") is True


def test_on_disconnect_sets_flag():
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "d-hub"})
    c._connected = True
    c.on_disconnect(None, None, 1)
    assert c._connected is False


def test_on_message_handles_binary_payload_gracefully(monkeypatch):
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "m-hub"})

    # create a message whose payload is not utf-8 decodable (simulate by bytes)
    class M:
        def __init__(self):
            self.topic = f"hubs/{c.client_id}/v1/cmd/sensors/poll"
            self.payload = b"\xff\xfe\xfd"  # invalid utf-8

    # Ensure handlers exists and is callable; use the real handlers
    m = M()
    # Replace handlers with a dummy that records it was called
    spec = importlib.util.spec_from_file_location(
        "handlers", Path(mod.__file__).parent / "handlers.py"
    )
    handlers_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(handlers_mod)
    # call on_message; it should not raise
    c._client = DummyPub()
    c.on_message(None, None, m)
