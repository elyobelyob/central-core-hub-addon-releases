import importlib.util
import sys
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_ha_version_ttl(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    ha_path = repo_root / "central-core-hub" / "ha_client.py"
    ha = _load_module(ha_path, "ha_client_testmod_ttl")

    # Ensure clean state
    ha.set_ha_version(None)

    ha.set_ha_version("1.2.3")
    assert ha.get_ha_version() == "1.2.3"
    assert ha.get_ha_version(ttl_seconds=1000) == "1.2.3"

    # Advance time so TTL expires
    base = ha._HA_VERSION_CACHE.get("ts")
    assert base is not None

    monkeypatch.setattr(ha.time, "time", lambda: base + 2)
    assert ha.get_ha_version(ttl_seconds=1) is None


def test_one_shot_publish_on_ha_version(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    mqtt_path = repo_root / "central-core-hub" / "mqtt_client.py"

    # Create a fake HA module where the listener immediately reports a version
    class FakeListener:
        def __init__(self, url, token, on_event=None, log_fn=None, selectors=None, on_ha_version=None):
            self.url = url
            self.token = token
            self.on_event = on_event
            self.log_fn = log_fn
            self.selectors = selectors
            self.on_ha_version = on_ha_version

        def start(self):
            # simulate discovery
            if callable(self.on_ha_version):
                self.on_ha_version("2.3.4")
            return True

        def stop(self):
            return None

        def update_selectors(self, selectors):
            self.selectors = selectors

    fake_ha = type("M", (), {"HAWebSocketListener": FakeListener, "OPTIONS_PATH": "/tmp/options.json"})

    # Ensure mqtt_client imports our fake ha_client
    monkeypatch.setitem(sys.modules, "ha_client", fake_ha)

    mqtt = _load_module(mqtt_path, "mqtt_client_testmod_one_shot")

    # Replace publish_telemetry on the class so we can detect it
    def _mark_publish(self):
        setattr(self, "_published_once", True)

    monkeypatch.setattr(mqtt.CentralCoreClient, "publish_telemetry", _mark_publish, raising=False)

    opts = {
        "client_id": "test-hub",
        "mqtt_host": "127.0.0.1",
        "mqtt_port": 1883,
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
    }
    c = mqtt.CentralCoreClient(opts)

    assert getattr(c, "_published_once", False) is True
