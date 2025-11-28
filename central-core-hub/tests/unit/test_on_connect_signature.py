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


class DummyClientInner:
    def __init__(self):
        self.subscribed = []

    def subscribe(self, topic, qos=0):
        self.subscribed.append({"topic": topic, "qos": qos})


def test_on_connect_accepts_extra_args(monkeypatch):
    """Ensure on_connect handles extra positional and keyword args without raising."""
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    options = {"client_id": "conn-hub", "ha_api_url": "http://ha", "ha_api_token": "t"}
    c = CentralCoreClient(options)

    dummy = DummyClientInner()
    c._client = dummy

    called = {"sensors": 0, "telemetry": 0}

    def fake_publish_sensors():
        called["sensors"] += 1

    def fake_publish_telemetry():
        called["telemetry"] += 1

    monkeypatch.setattr(c, "publish_sensors", fake_publish_sensors)
    monkeypatch.setattr(c, "publish_telemetry", fake_publish_telemetry)

    # Standard call (positional args)
    c._connected = False
    c.on_connect(c._client, None, None, 0)
    assert any(s["topic"] == c.cmd_sub_topic for s in dummy.subscribed)
    assert called["sensors"] >= 1
    assert called["telemetry"] >= 1
    assert c._connected is True

    # Extra positional args
    c._connected = False
    called["sensors"] = 0
    called["telemetry"] = 0
    c.on_connect(c._client, None, 0, None, None)
    assert called["sensors"] >= 1
    assert called["telemetry"] >= 1
    assert c._connected is True

    # Keyword args style
    c._connected = False
    called["sensors"] = 0
    called["telemetry"] = 0
    c.on_connect(c._client, None, rc=0, properties=None)
    assert called["sensors"] >= 1
    assert called["telemetry"] >= 1
    assert c._connected is True
