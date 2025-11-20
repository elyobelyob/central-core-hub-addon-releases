import json
from pathlib import Path
import importlib.util


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
        self.subscribed = []

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})

        class R:
            rc = 0

        return R()

    def subscribe(self, topic, qos=0):
        self.subscribed.append({"topic": topic, "qos": qos})
        return (0, 1)


def test_publish_telemetry_and_vault(monkeypatch):
    mod = _load_client_module()
    # stub payload builders
    monkeypatch.setattr(
        mod, "build_telemetry", lambda client_id, **kwargs: json.dumps({"client_id": client_id})
    )
    monkeypatch.setattr(
        mod, "build_vault_payload", lambda raw: json.dumps({"schema_version": 2})
    )

    options = {
        "client_id": "unit-123",
        "mqtt_host": "x",
        "vault_topic": "vault/unit-123/telemetry",
    }
    c = mod.CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    c.publish_telemetry()
    topics = [p["topic"] for p in dummy.published]
    assert c.telemetry_topic in topics
    assert options["vault_topic"] in topics


def test_get_cpu_percent_with_mocked_proc(monkeypatch):
    mod = _load_client_module()
    # simulate two _read_proc_stat calls returning increasing totals
    seq = [(100, 200), (120, 240)]

    def fake_read():
        return seq.pop(0)

    monkeypatch.setattr(mod, "_read_proc_stat", fake_read)
    val = mod.get_cpu_percent()
    assert isinstance(val, float) or isinstance(val, int)


def test_on_connect_subscribes_to_cmd_pattern():
    mod = _load_client_module()
    options = {"client_id": "unit-xyz"}
    c = mod.CentralCoreClient(options)
    dummy = DummyClient()
    # call on_connect
    c.on_connect(dummy, None, None, 0)
    # ensure we subscribed to cmd_sub_topic only
    subs = [s["topic"] for s in dummy.subscribed]
    assert c.cmd_sub_topic in subs


def test_publish_sensors_no_ha_config_does_nothing():
    mod = _load_client_module()
    options = {"client_id": "unit-noha"}
    c = mod.CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    # no ha_api_url or token, so publish_sensors should return early and not publish
    c.publish_sensors()
    assert dummy.published == []


def test_build_vault_payload_invalid_returns_none():
    mod = _load_client_module()
    assert mod.build_vault_payload("not-a-json") is None


def test_get_cpu_percent_handles_none(monkeypatch):
    mod = _load_client_module()
    # simulate _read_proc_stat returning None
    monkeypatch.setattr(mod, "_read_proc_stat", lambda: (None, None))
    assert mod.get_cpu_percent() is None


def test_fetch_sensors_parses_http_response(monkeypatch):
    mod = _load_client_module()

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    class FakeRequests:
        def get(self, url, headers=None, timeout=10):
            data = [
                {
                    "entity_id": "sensor.a",
                    "state": "1",
                    "attributes": {"friendly_name": "A"},
                },
                {"entity_id": "light.b", "state": "on"},
            ]
            return FakeResp(data)

    monkeypatch.setattr(mod, "requests", FakeRequests())
    out = mod.fetch_sensors("http://ha", "token")
    assert isinstance(out, list)
    assert any(s["entity_id"] == "sensor.a" for s in out)


def test_on_message_non_sensor_topic_no_crash():
    mod = _load_client_module()
    options = {"client_id": "unit-xyz"}
    c = mod.CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy

    # non-sensor topic should be handled gracefully
    class Msg:
        def __init__(self):
            self.topic = "other/topic"
            self.payload = b"hello"

    c.on_message(None, None, Msg())
    # no publishes expected
    assert dummy.published == []
