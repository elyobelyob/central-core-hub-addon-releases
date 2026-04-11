import importlib.util
from pathlib import Path
import sys
import types


def _load_telemetry_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "telemetry.py"
    spec = importlib.util.spec_from_file_location("tele_mod", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_external_get_cpu_percent_override():
    t = _load_telemetry_module()
    # attach an external override
    setattr(t, "_external_get_cpu_percent", lambda: 12.5)
    payload = t.build_telemetry("hub-x")
    import json

    j = json.loads(payload)
    assert j["cpu_percent"] == 12.5
    delattr(t, "_external_get_cpu_percent")


def test_helpers_module_get_cpu_percent(monkeypatch):
    t = _load_telemetry_module()
    # create a fake helpers module exposing get_cpu_percent
    mod = types.ModuleType("helpers")
    setattr(mod, "get_cpu_percent", lambda: 7.7)
    setattr(mod, "uptime_seconds", lambda: 200)
    setattr(mod, "loadavg", lambda: ["0.1", "0.2", "0.3"])
    setattr(mod, "mem_info_kb", lambda: (1000, 500))
    setattr(mod, "disk_info_kb", lambda p="/": (10000, 4000))
    sys.modules["helpers"] = mod
    payload = t.build_telemetry("hub-y")
    import json

    j = json.loads(payload)
    assert j["cpu_percent"] == 7.7
    assert j["uptime"] == 200
    # clean up
    del sys.modules["helpers"]


def test_fallback_external_get_cpu_percent(monkeypatch):
    t = _load_telemetry_module()
    # inject via the _external_get_cpu_percent hook (new API)
    t._external_get_cpu_percent = lambda: 3.3
    try:
        val = t._get_cpu_percent()
        assert val == 3.3
    finally:
        t._external_get_cpu_percent = None
