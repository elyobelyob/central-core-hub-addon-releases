import json
import importlib.util
from pathlib import Path


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class DummyMsg:
    def __init__(self, topic, payload_bytes=b""):
        self.topic = topic
        self.payload = payload_bytes


def test_poll_malformed_payload_no_ack(monkeypatch):
    mc = _load_client_module()
    CentralCoreClient = mc.CentralCoreClient

    # fetch_sensors returns something so handler publishes telemetry
    monkeypatch.setattr(mc, "fetch_sensors", lambda url, token: [{"entity_id": "sensor.x", "state": "1", "attributes": {}}])

    options = {"client_id": "unit-hub", "ha_api_url": "http://ha", "ha_api_token": "tok"}
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    c.vault_topic = ""

    # payload_str is invalid JSON -> handler should treat as {} and not ack
    msg = DummyMsg(f"hubs/{c.client_id}/cmd/sensors/poll", b"not-a-json")

    # on_message will decode payload into '<binary>' unless provided; call handlers via on_message
    c.on_message(None, None, msg)

    # ensure no ack topic published (no command_id in payload)
    topics = [p["topic"] for p in dummy.published]
    assert not any("/cmd/" in t and t.endswith("/response") for t in topics)
    # but preferred sensors topic should be published
    assert c.preferred_sensors_topic in topics


def test_set_with_sensors_as_dict_and_readback_failure(monkeypatch):
    mc = _load_client_module()
    CentralCoreClient = mc.CentralCoreClient

    posts = []

    class FakeResp:
        def __init__(self, data=None):
            self._data = data or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    def fake_post(url, headers=None, json=None, timeout=10):
        posts.append({"url": url, "json": json})
        return FakeResp()

    def fake_get(url, headers=None, timeout=10):
        raise RuntimeError("readback failed")

    monkeypatch.setattr(mc, "requests", type("R", (), {"post": staticmethod(fake_post), "get": staticmethod(fake_get)}))

    options = {"client_id": "unit-hub", "ha_api_url": "http://ha", "ha_api_token": "tok", "ha_readback_after_set": True}
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    c.vault_topic = "vault/unit"

    # sensors payload as dict form
    payload = {"sensors": {"sensor.a": "10", "sensor.b": "20"}}
    cmd = {"command_id": "cid", "action": "sensors/set", "payload": payload}
    msg = DummyMsg(f"hubs/{c.client_id}/cmd/sensors/set", json.dumps(cmd).encode("utf-8"))

    c.on_message(None, None, msg)

    # POSTs should have occurred for each sensor
    assert len(posts) == 2
    # telemetry published to preferred topic
    topics = [p["topic"] for p in dummy.published]
    assert c.preferred_sensors_topic in topics
    # reminder published to vault topic
    assert any(p["topic"] == c.vault_topic for p in dummy.published)
