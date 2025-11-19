import importlib.util
from pathlib import Path
import sys
import types


def _load_telemetry_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "telemetry.py"
    spec = importlib.util.spec_from_file_location("tele_mod", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_external_get_cpu_percent_override():
    t = _load_telemetry_module()
    # attach an external override
    t._external_get_cpu_percent = lambda: 12.5
    payload = t.build_telemetry("hub-x")
    import json

    j = json.loads(payload)
    assert j["cpu_percent"] == 12.5
    delattr(t, "_external_get_cpu_percent")


def test_helpers_module_get_cpu_percent(monkeypatch):
    t = _load_telemetry_module()
    # create a fake helpers module exposing get_cpu_percent
    mod = types.ModuleType("helpers")
    mod.get_cpu_percent = lambda: 7.7
    mod.uptime_seconds = lambda: 200
    mod.loadavg = lambda: ["0.1", "0.2", "0.3"]
    mod.mem_info_kb = lambda: (1000, 500)
    mod.disk_info_kb = lambda p="/": (10000, 4000)
    sys.modules["helpers"] = mod
    payload = t.build_telemetry("hub-y")
    import json

    j = json.loads(payload)
    assert j["cpu_percent"] == 7.7
    assert j["uptime"] == 200
    # clean up
    del sys.modules["helpers"]


def test_fallback_mqtt_client_candidate(monkeypatch):
    t = _load_telemetry_module()
    # inject a fake module named 'mqtt_client' with get_cpu_percent
    mod = types.ModuleType("mqtt_client")
    mod.get_cpu_percent = lambda: 3.3
    sys.modules["mqtt_client"] = mod
    # calling _get_cpu_percent directly should find it
    val = t._get_cpu_percent()
    assert val == 3.3
    del sys.modules["mqtt_client"]
