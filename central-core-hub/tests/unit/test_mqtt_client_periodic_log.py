import importlib.util
from pathlib import Path


def _load_mqtt_module(name="mqtt_client_periodic_test"):
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location(name, str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    return mod


def test_periodic_monitor_log_with_sensors(monkeypatch):
    mod = _load_mqtt_module("mqtt_client_periodic_with")
    CentralCoreClient = mod.CentralCoreClient

    logged = []

    def fake_log(msg, file=None):
        # keep only the message part (timestamp is prepended by original)
        logged.append(str(msg))

    monkeypatch.setattr(mod, "_log", fake_log)
    # Make registry return some provided sensors
    monkeypatch.setattr(mod, "list_monitored_sensors", lambda: ["sensor.a", "sensor.b"])

    c = CentralCoreClient({"client_id": "unit-periodic-1"})
    # ensure we don't hit other code paths that print
    c._connected = True
    c.publish_telemetry = lambda: None
    c.publish_selected_sensor_changes = lambda: None
    c.publish_sensors = lambda: None

    # Force the periodic branch by ensuring last_monitor_log is zero
    c._last_monitor_log = 0

    c.run_iteration()

    # Expect at least two periodic logs: WS monitoring and registry provided
    assert any("Periodic: HA WS monitoring sensors" in m for m in logged)
    assert any("Periodic: Registry provided sensors" in m for m in logged)
    # _last_monitor_log should be updated to a positive integer
    assert isinstance(c._last_monitor_log, int) and c._last_monitor_log > 0


def test_periodic_monitor_log_no_sensors(monkeypatch):
    mod = _load_mqtt_module("mqtt_client_periodic_none")
    CentralCoreClient = mod.CentralCoreClient

    logged = []

    def fake_log(msg, file=None):
        logged.append(str(msg))

    monkeypatch.setattr(mod, "_log", fake_log)
    # Registry returns no sensors
    monkeypatch.setattr(mod, "list_monitored_sensors", lambda: [])

    c = CentralCoreClient({"client_id": "unit-periodic-2"})
    c._connected = True
    c.publish_telemetry = lambda: None
    c.publish_selected_sensor_changes = lambda: None
    c.publish_sensors = lambda: None
    # Ensure selected sensors set is empty
    c._selected_sensors_set = set()
    c._last_monitor_log = 0

    c.run_iteration()

    assert any("Periodic: HA WS monitoring sensors: none" in m for m in logged)
    assert any("Periodic: Registry provided sensors: none" in m for m in logged)
    assert isinstance(c._last_monitor_log, int) and c._last_monitor_log > 0
