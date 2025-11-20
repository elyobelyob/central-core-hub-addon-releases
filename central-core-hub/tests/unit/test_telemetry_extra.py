import json
import importlib.util
from pathlib import Path


def _load_telemetry():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "telemetry.py"
    spec = importlib.util.spec_from_file_location("telemetry", str(src))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

tele = _load_telemetry()


def test_build_vault_payload_missing_metrics():
    # minimal telemetry payload with only identifying fields
    raw = json.dumps({"client_id": "hub1", "timestamp": "2025-01-01T00:00:00Z", "hostname": "h"})
    v = tele.build_vault_payload(raw)
    assert v is not None
    obj = json.loads(v)
    assert obj.get("schema_version") == 2
    assert obj.get("id") == "hub1"
    assert isinstance(obj.get("metrics"), dict)
    # metrics should be empty dict when none present
    assert obj.get("metrics") == {}


def test_build_vault_payload_invalid_json_returns_none():
    assert tele.build_vault_payload("not-json") is None
