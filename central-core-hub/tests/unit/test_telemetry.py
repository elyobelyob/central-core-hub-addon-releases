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


def test_build_telemetry_structure():
    mod = _load_client_module()
    build_telemetry = mod.build_telemetry
    raw = build_telemetry("unit-test-hub", telemetry_interval=42)
    assert raw is not None
    data = json.loads(raw)
    assert data.get("schema_version") == 1
    assert data.get("client_id") == "unit-test-hub"
    assert "timestamp" in data
    # core numeric fields exist (may be None on some systems but present)
    assert "cpu_count" in data
    assert "mem_total_kb" in data
    assert data.get("telemetry_interval") == 42


def test_telemetry_to_vault_transformation():
    mod = _load_client_module()
    build_telemetry = mod.build_telemetry
    build_vault_payload = mod.build_vault_payload
    tele_raw = build_telemetry("unit-test-hub-2", telemetry_interval=55)
    vault_raw = build_vault_payload(tele_raw)
    assert vault_raw is not None
    vault = json.loads(vault_raw)
    assert vault.get("schema_version") == 2
    assert vault.get("id") == "unit-test-hub-2"
    assert "metrics" in vault and isinstance(vault["metrics"], dict)
    assert vault.get("telemetry_interval") == 55


def test_build_vault_payload_invalid_json():
    mod = _load_client_module()
    build_vault_payload = mod.build_vault_payload
    assert build_vault_payload("not a json") is None
