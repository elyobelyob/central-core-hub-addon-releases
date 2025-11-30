import json
import importlib.util
from pathlib import Path


def _load_modules():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mc = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mc)

    # handlers.py
    hsrc = repo_root / "central-core-hub" / "handlers.py"
    hspec = importlib.util.spec_from_file_location("handlers", str(hsrc))
    if hspec is None or getattr(hspec, "loader", None) is None:
        raise ImportError("could not load spec")
    hmod = importlib.util.module_from_spec(hspec)
    hloader = hspec.loader
    assert hloader is not None
    hloader.exec_module(hmod)

    return mc, hmod


class DummyClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class DummyMsg:
    def __init__(self, topic, payload_bytes):
        self.topic = topic
        self.payload = payload_bytes





def test_client_loads_persisted_selection_on_init(tmp_path):
    mc, handlers = _load_modules()
    import sys
    prev = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = mc
    CentralCoreClient = mc.CentralCoreClient

    target = tmp_path / "SELECTED_SENSORS.json"
    target.write_text(json.dumps(["sensor.a", "sensor.b"]))

    # ensure module uses our test file
    mc.SELECTED_SENSORS_FILE = target

    options = {"client_id": "unit-hub"}
    try:
        c = CentralCoreClient(options)

        assert getattr(c, "selected_sensors", None) == ["sensor.a", "sensor.b"]
    finally:
        if prev is None:
            del sys.modules["mqtt_client"]
        else:
            sys.modules["mqtt_client"] = prev
