import importlib.util
from pathlib import Path
import types
import sys


def test_mqtt_client_import_uses_file_fallback_when_helpers_missing(monkeypatch):
    # Arrange: inject a dummy 'helpers' and 'telemetry' module to force
    # the initial import in mqtt_client to raise ImportError for missing names.
    dummy_helpers = types.ModuleType("helpers")
    dummy_telemetry = types.ModuleType("telemetry")
    sys.modules["helpers"] = dummy_helpers
    sys.modules["telemetry"] = dummy_telemetry

    try:
        repo_root = Path(__file__).resolve().parents[3]
        src = repo_root / "central-core-hub" / "mqtt_client.py"
        spec = importlib.util.spec_from_file_location("fresh_mqtt_client", str(src))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # After import, the fallback should have installed build_telemetry
        assert hasattr(mod, "build_telemetry")
        # calling build_telemetry should return JSON string
        res = mod.build_telemetry("cid-fallback")
        assert isinstance(res, str)
    finally:
        # cleanup
        for k in ("helpers", "telemetry", "fresh_mqtt_client"):
            if k in sys.modules:
                del sys.modules[k]
