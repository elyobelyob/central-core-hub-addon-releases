import json
from pathlib import Path
import importlib.util


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_vault_payload_basic():
    mod = _load_client_module()
    build_vault_payload = mod.build_vault_payload
    # create a basic telemetry payload with expected fields
    payload = {
        "client_id": "test-hub",
        "timestamp": "2025-11-18T00:00:00Z",
        "hostname": "host1",
        "ip": "192.0.2.1",
        "cpu_count": 4,
        "cpu_percent": 12.3,
        "uptime": 3600,
        "mem_total_kb": 1024000,
        "mem_free_kb": 512000,
        "disk_total_kb": 2048000,
        "disk_free_kb": 1024000,
    }
    raw = json.dumps(payload)
    v = build_vault_payload(raw)
    assert v is not None
    data = json.loads(v)
    assert data.get("schema_version") == 2
    assert data.get("id") == "test-hub"
    assert data.get("ts") == payload["timestamp"]
    assert data.get("host") == payload["hostname"]
    assert data.get("ip") == payload["ip"]
    metrics = data.get("metrics")
    assert metrics["cpu_count"] == 4
    assert metrics["cpu_percent"] == 12.3
    assert metrics["uptime"] == 3600


def test_build_vault_payload_missing_fields():
    mod = _load_client_module()
    build_vault_payload = mod.build_vault_payload
    # payload missing metrics should still return a vault object with empty metrics
    payload = {
        "client_id": "test-hub-2",
        "timestamp": "2025-11-18T01:00:00Z",
        "hostname": "host2",
    }
    raw = json.dumps(payload)
    v = build_vault_payload(raw)
    assert v is not None
    data = json.loads(v)
    assert data.get("id") == "test-hub-2"
    assert isinstance(data.get("metrics"), dict)
