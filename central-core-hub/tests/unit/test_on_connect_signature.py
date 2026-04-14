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

    sensors_called = [0]

    def fake_publish_sensors_with_default_filter():
        sensors_called[0] += 1

    monkeypatch.setattr(c, "publish_sensors_with_default_filter", fake_publish_sensors_with_default_filter)

    # Standard call (positional args)
    c._connected = False
    c.on_connect(c._client, None, None, 0)
    assert any(s["topic"] == c.cmd_sub_topic for s in dummy.subscribed)
    assert sensors_called[0] >= 1
    assert c._connected is True

    # Extra positional args
    c._connected = False
    sensors_called[0] = 0
    c.on_connect(c._client, None, 0, None, None)
    assert sensors_called[0] >= 1
    assert c._connected is True

    # Keyword args style
    c._connected = False
    sensors_called[0] = 0
    c.on_connect(c._client, None, rc=0, properties=None)
    assert sensors_called[0] >= 1
    assert c._connected is True
