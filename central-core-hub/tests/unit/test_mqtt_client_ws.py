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


def test_ha_ws_listener_started_and_stop_called(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    mqtt_path = repo_root / "central-core-hub" / "mqtt_client.py"

    # Prepare a fake ha_client module with HAWebSocketListener
    class FakeListener:
        _instances = []

        def __init__(self, url, token, on_event=None, log_fn=None, selectors=None, on_ha_version=None):
            self.url = url
            self.token = token
            self.on_event = on_event
            self.log_fn = log_fn
            self.selectors = selectors
            self.on_ha_version = on_ha_version
            self.started = False
            self.stopped = False
            FakeListener._instances.append(self)

        def start(self):
            self.started = True
            return True

        def stop(self):
            self.stopped = True

        def update_selectors(self, selectors):
            self.selectors = selectors

    fake_ha = type("M", (), {"HAWebSocketListener": FakeListener, "OPTIONS_PATH": str(tmp_path / "options.json")})

    # Ensure mqtt_client imports our fake ha_client
    monkeypatch.setitem(sys.modules, "ha_client", fake_ha)

    mqtt = _load_module(mqtt_path, "mqtt_client_testmod_ws")

    opts = {
        "client_id": "test-hub",
        "mqtt_host": "127.0.0.1",
        "mqtt_port": 1883,
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
    }
    c = mqtt.CentralCoreClient(opts)

    # Listener should have been created and started
    assert getattr(c, "_ha_ws_listener", None) is not None
    inst = c._ha_ws_listener
    assert isinstance(inst, FakeListener)
    assert inst.started is True
    assert inst.on_event == c._on_ha_state_event

    # Updating the client's selected sensors should update selectors on the listener
    c.selected_sensors = ["sensor.test"]
    assert inst.selectors == {"sensor.test"}

    # Calling close should stop the listener
    c.close()
    assert inst.stopped is True
