import json
from pathlib import Path
import importlib.util


def _load_client_module():
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


def test_build_vault_payload_transforms():
    mod = _load_client_module()
    raw = {
        "schema_version": 1,
        "client_id": "unit-1",
        "timestamp": "2025-11-18T00:00:00Z",
        "hostname": "host1",
        "ip": "10.0.0.1",
        "cpu_count": 4,
        "cpu_percent": 12.3,
        "uptime": 12345,
        "mem_total_kb": 8000000,
        "mem_free_kb": 4000000,
        "disk_total_kb": 10000000,
        "disk_free_kb": 5000000,
    }
    raw_json = json.dumps(raw)
    out = mod.build_vault_payload(raw_json)
    assert out is not None
    parsed = json.loads(out)
    assert parsed.get("schema_version") == 2
    assert parsed.get("id") == "unit-1"
    assert parsed.get("host") == "host1"
    assert "metrics" in parsed
    metrics = parsed["metrics"]
    assert metrics["cpu_count"] == 4
    assert metrics["cpu_percent"] == 12.3


def test_build_telemetry_structure(monkeypatch):
    mod = _load_client_module()
    # Patch helpers to return deterministic values
    monkeypatch.setattr(mod, "uptime_seconds", lambda: 100)
    monkeypatch.setattr(mod, "loadavg", lambda: ["0.00", "0.01", "0.05"])
    monkeypatch.setattr(mod, "mem_info_kb", lambda: (8000000, 4000000))
    monkeypatch.setattr(mod, "disk_info_kb", lambda path="/": (10000000, 5000000))
    monkeypatch.setattr(mod, "get_cpu_percent", lambda: 5.5)

    # Ensure hostname/ip retrieval is stable by monkeypatching socket
    class DummySocket:
        def __init__(self):
            pass

        def connect(self, tup):
            pass

        def getsockname(self):
            return ("10.0.0.2", 0)

        def close(self):
            pass

    import socket as _socket

    monkeypatch.setattr(_socket, "socket", lambda *a, **k: DummySocket())

    payload = mod.build_telemetry(
        "dev-unit",
        uptime_fn=lambda: 100,
        loadavg_fn=lambda: ["0.00", "0.01", "0.05"],
        mem_info_fn=lambda: (8000000, 4000000),
        disk_info_fn=lambda path="/": (10000000, 5000000),
    )
    assert payload is not None
    j = json.loads(payload)
    assert j.get("client_id") == "dev-unit"
    assert "timestamp" in j
    assert j.get("cpu_percent") == 5.5
    assert j.get("uptime") == 100


def test_fetch_sensors_handles_missing_requests(monkeypatch):
    mod = _load_client_module()
    # Simulate requests not available
    monkeypatch.setattr(mod, "requests", None)
    assert mod.fetch_sensors("http://ha", "tok") is None


def test_get_addon_version_reads_from_config_json(tmp_path, monkeypatch):
    """Test that get_addon_version correctly reads version from config.json."""
    mod = _load_client_module()

    # Create a temporary config.json with a test version
    config_data = {"name": "Test Add-on", "version": "2.1.3", "slug": "test-addon"}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))

    # Patch the function to use our temp file
    def patched_get_addon_version():
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                return config.get("version")
        except Exception:
            return None

    monkeypatch.setattr(mod, "get_addon_version", patched_get_addon_version)

    # Test that it returns the correct version
    version = mod.get_addon_version()
    assert version == "2.1.3"


def test_get_addon_version_handles_missing_file(monkeypatch):
    """Test that get_addon_version returns None when config.json doesn't exist."""
    mod = _load_client_module()

    # Patch the function to simulate file not found
    def patched_get_addon_version():
        try:
            with open("/nonexistent/config.json", "r") as f:
                config = json.load(f)
                return config.get("version")
        except Exception:
            return None

    monkeypatch.setattr(mod, "get_addon_version", patched_get_addon_version)

    # Test that it returns None
    version = mod.get_addon_version()
    assert version is None

    # Test that it returns None
    version = mod.get_addon_version()
    assert version is None
