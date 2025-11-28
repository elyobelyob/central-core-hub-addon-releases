import importlib.util
import sys
import json
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


def test_build_telemetry_includes_home_assistant_dict():
    repo_root = Path(__file__).resolve().parents[3]
    tele = _load_module(repo_root / "central-core-hub" / "telemetry.py", "tele_test1")
    payload = tele.build_telemetry(
        "cid",
        get_cpu_percent=lambda: 5.5,
        version="1.2.3",
        telemetry_interval=30,
        home_assistant={"core": "2026.3.4", "supervisor": "sup"},
    )
    data = json.loads(payload)
    assert data.get("home_assistant")["core"] == "2026.3.4"
    assert data.get("ha_version") == "2026.3.4"


def test_build_telemetry_home_assistant_string():
    repo_root = Path(__file__).resolve().parents[3]
    tele = _load_module(repo_root / "central-core-hub" / "telemetry.py", "tele_test2")
    payload = tele.build_telemetry(
        "cid",
        get_cpu_percent=lambda: None,
        version="1.2.3",
        telemetry_interval=30,
        home_assistant="2026.9.0",
    )
    data = json.loads(payload)
    # When home_assistant is a string, the module stores a ha_version
    # but `home_assistant` may be set to None (attempt to dict() fails).
    assert data.get("home_assistant") is None
    assert data.get("ha_version") == "2026.9.0"


def test_build_telemetry_prefers_shared_schema_module(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    tele_path = repo_root / "central-core-hub" / "telemetry.py"

    # Create fake schema module with SystemTelemetry that provides json()
    class FakeModel:
        def __init__(self, **kwargs):
            self._data = kwargs

        def json(self):
            return json.dumps({"schema": "ok"})

    fake_schemas = type("M", (), {})()
    fake_schemas.SystemTelemetry = FakeModel

    monkeypatch.setitem(sys.modules, "central_core_mqtt_shared.schemas", fake_schemas)

    tele = _load_module(tele_path, "tele_test3")
    out = tele.build_telemetry("cid", get_cpu_percent=lambda: 1.0)
    # Because fake model.json returns a JSON string with schema key
    assert "schema" in out


def test_build_vault_payload_and_invalid():
    repo_root = Path(__file__).resolve().parents[3]
    tele = _load_module(repo_root / "central-core-hub" / "telemetry.py", "tele_test4")
    payload = {
        "client_id": "cid",
        "timestamp": "ts",
        "hostname": "host",
        "ip": "1.2.3.4",
        "cpu_count": 2,
        "cpu_percent": 10.5,
        "uptime": 100,
        "mem_total_kb": 1000,
        "mem_free_kb": 500,
        "disk_total_kb": 10000,
        "disk_free_kb": 8000,
        "home_assistant": {"core": "2026.0.0"},
    }
    vault = tele.build_vault_payload(json.dumps(payload))
    v = json.loads(vault)
    assert v.get("metrics")["cpu_count"] == 2
    assert v.get("ha_version") == "2026.0.0"

    # invalid JSON
    assert tele.build_vault_payload("not json") is None
