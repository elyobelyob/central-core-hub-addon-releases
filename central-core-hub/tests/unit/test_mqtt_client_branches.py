import json
import importlib.util
from pathlib import Path


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


class DummyPub:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})

        class R:
            rc = 0

        return R()


def test_build_telemetry_wrapper_respects_monkeypatched_get_cpu():
    mod = _load_module()
    # monkeypatch mqtt_client.get_cpu_percent
    setattr(mod, "get_cpu_percent", lambda: 9.9)
    payload = mod.build_telemetry("cid-test")
    j = json.loads(payload)
    assert j.get("cpu_percent") == 9.9


def test__publish_handles_exception():
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "pub1"})

    class BadClient:
        def publish(self, topic, payload, qos=0):
            raise RuntimeError("boom")

    c._client = BadClient()
    res = c._publish("t", "p", qos=1)
    assert res is None


def test_publish_telemetry_with_vault_transform():
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    options = {"client_id": "vt1", "vault_topic": "vault/vt1"}
    c = CentralCoreClient(options)
    dummy = DummyPub()
    c._client = dummy
    # stub telemetry builders
    setattr(mod, "build_telemetry", lambda cid, **kwargs: "raw-payload")
    setattr(mod, "build_vault_payload", lambda raw: "vault-payload")
    c.publish_telemetry()
    topics = [p["topic"] for p in dummy.published]
    assert c.telemetry_topic in topics
    assert c.vault_topic in topics
    # ensure vault payload used
    vault_msgs = [p for p in dummy.published if p["topic"] == c.vault_topic]
    assert vault_msgs and vault_msgs[0]["payload"] == "vault-payload"


def test_publish_telemetry_with_vault_fallback():
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    options = {"client_id": "vt2", "vault_topic": "vault/vt2"}
    c = CentralCoreClient(options)
    dummy = DummyPub()
    c._client = dummy
    setattr(mod, "build_telemetry", lambda cid, **kwargs: "raw-payload-2")
    setattr(mod, "build_vault_payload", lambda raw: None)
    c.publish_telemetry()
    vault_msgs = [p for p in dummy.published if p["topic"] == c.vault_topic]
    assert vault_msgs and vault_msgs[0]["payload"] == "raw-payload-2"


def test_publish_sensors_no_ha_does_nothing():
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "s1"})
    dummy = DummyPub()
    c._client = dummy
    # ha_api_url not set, so publish_sensors should return without publishing
    c.publish_sensors()
    assert not dummy.published


def test_on_connect_subscribe_exception_calls_publish_sensors(monkeypatch):
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "conn1", "ha_api_url": "http://ha", "ha_api_token": "t"})

    class BadSubscriber:
        def subscribe(self, topic, qos=0):
            raise RuntimeError("subfail")

    bs = BadSubscriber()
    called = {}

    def fake_publish_sensors():
        called["sensors"] = True

    monkeypatch.setattr(c, "publish_sensors", fake_publish_sensors)
    # call on_connect with client object that raises on subscribe
    c.on_connect(bs, None, None, 0)
    assert c._connected is True
    assert called.get("sensors") is True
