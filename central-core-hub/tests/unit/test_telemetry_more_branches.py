import importlib.util
import pathlib
import json
import sys
from types import SimpleNamespace


def _load_module():
    base = pathlib.Path(__file__).parents[2]
    src = base / "telemetry.py"
    spec = importlib.util.spec_from_file_location("telemetry", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load telemetry spec")
    spec.loader.exec_module(mod)
    return mod


tel = _load_module()


def test_get_cpu_percent_external_override_and_fallback():
    # External override should be respected
    tel._external_get_cpu_percent = lambda: 12
    try:
        assert tel._get_cpu_percent() == 12
    finally:
        tel._external_get_cpu_percent = None

    # If external override raises, it should fall through to other checks
    def bad():
        raise RuntimeError("boom")

    tel._external_get_cpu_percent = bad
    helpers_orig = sys.modules.get("helpers")
    sys.modules["helpers"] = SimpleNamespace(get_cpu_percent=lambda: None)
    try:
        # Remove any mqtt_client entries to avoid other fallbacks
        orig = sys.modules.pop("mqtt_client", None)
        try:
            assert tel._get_cpu_percent() is None
        finally:
            if orig is not None:
                sys.modules["mqtt_client"] = orig
    finally:
        tel._external_get_cpu_percent = None
        if helpers_orig is not None:
            sys.modules["helpers"] = helpers_orig
        else:
            sys.modules.pop("helpers", None)


def test_build_telemetry_with_helpers_and_ha_info():
    def fake_cpu():
        return 7

    def fake_uptime():
        return 123

    def fake_load():
        return (0.1, 0.2, 0.3)

    def fake_mem():
        return (1000, 400)

    def fake_disk():
        return (5000, 2000)

    payload_json = tel.build_telemetry(
        "cid",
        get_cpu_percent=fake_cpu,
        uptime_fn=fake_uptime,
        loadavg_fn=fake_load,
        mem_info_fn=fake_mem,
        disk_info_fn=fake_disk,
        version="v1",
        telemetry_interval=60,
        home_assistant={"core": "2025.5.0", "installation_method": "test"},
    )
    data = json.loads(payload_json)
    assert data["client_id"] == "cid"
    assert data["cpu_percent"] == 7
    assert data["uptime"] == 123
    assert data["load_avg"] == [0.1, 0.2, 0.3]
    assert data["mem_total_kb"] == 1000
    assert data["disk_free_kb"] == 2000
    assert data["addon_version"] == "v1"
    assert data.get("home_assistant") is not None
    assert data.get("ha_version") == "2025.5.0"


def test_build_vault_payload_extracts_metrics_and_ha():
    raw = {
        "client_id": "cid",
        "timestamp": "t",
        "hostname": "h",
        "ip": "1.2.3.4",
        "cpu_count": 1,
        "cpu_percent": 5,
        "uptime": 10,
        "mem_total_kb": 100,
        "mem_free_kb": 50,
        "disk_total_kb": 200,
        "disk_free_kb": 150,
        "telemetry_interval": 30,
        "home_assistant": {"core": "2025.0.0"},
    }
    vault = tel.build_vault_payload(json.dumps(raw))
    obj = json.loads(vault)
    assert obj["id"] == "cid"
    assert obj["metrics"]["cpu_percent"] == 5
    assert obj["telemetry_interval"] == 30
    assert obj.get("ha_version") == "2025.0.0"
