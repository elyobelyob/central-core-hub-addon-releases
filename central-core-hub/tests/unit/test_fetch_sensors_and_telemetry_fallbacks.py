import importlib.util
from pathlib import Path
import types
from typing import Any, cast


def _load_module(name):
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_fetch_sensors_handles_requests_get_exception(monkeypatch):
    mc = _load_module("mqtt_client.py")

    class BadResp:
        def get(self, *a, **k):
            raise RuntimeError("net")

    cast(Any, mc).requests = BadResp()
    assert mc.fetch_sensors("http://ha", "tok") is None


def test_fetch_sensors_parses_entities(monkeypatch):
    mc = _load_module("mqtt_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "entity_id": "sensor.x",
                    "state": "12",
                    "attributes": {"friendly_name": "X", "extra": 1},
                },
                {"entity_id": "binary_sensor.y", "state": "on", "attributes": {}},
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    cast(Any, mc).requests = RClient()
    sensors = mc.fetch_sensors("http://ha", "tok")
    assert isinstance(sensors, list)
    # sensor.* and binary_sensor.* without device_class should be included
    assert any(s["entity_id"] == "sensor.x" for s in sensors)
    # binary sensors without device_class attribute are now included
    assert any(s["entity_id"] == "binary_sensor.y" for s in sensors)


def test_telemetry_get_cpu_from_mqtt_client_module(monkeypatch):
    tele = _load_module("telemetry.py")
    # create fake mqtt_client module with get_cpu_percent
    fake = types.ModuleType("mqtt_client")
    setattr(fake, "get_cpu_percent", lambda: 4.4)
    import sys

    sys.modules["mqtt_client"] = fake
    try:
        assert tele._get_cpu_percent() == 4.4
    finally:
        del sys.modules["mqtt_client"]


def test_on_message_falls_back_to_file_load(monkeypatch):
    mc = _load_module("mqtt_client.py")
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({"client_id": "fallback-onmsg"})

    # ensure handlers in sys.modules lacks handle_message to force file-based load
    import sys
    import types

    sys.modules["handlers"] = types.ModuleType("handlers")

    published = []

    def fake_publish(topic, payload, qos=0):
        published.append({"topic": topic, "payload": payload, "qos": qos})

    c._publish = fake_publish

    # call on_message which should import handlers via file and call handle_message
    msg = types.SimpleNamespace(topic=f"hubs/{c.client_id}/v1/cmd/sensors/poll", payload=b"{}")
    c.on_message(None, None, msg)

    # after handling, preferred sensors topic should have been published
    assert any(p["topic"].endswith("/telemetry/sensors") for p in published)
