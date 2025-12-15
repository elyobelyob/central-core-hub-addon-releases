import importlib.util
from pathlib import Path
import types
import sys


def test_container_files_present_for_dockerfile_copy():
    """Test that all Python files required for container are present.

    The Dockerfile copies *.py files to root, so ensure all imported modules exist.
    """
    repo_root = Path(__file__).resolve().parents[3]
    central_core_hub_dir = repo_root / "central-core-hub"

    # Files that must be present for imports to work in container
    required_files = [
        "mqtt_client.py",
        "handlers.py",
        "telemetry.py",
        "helpers.py",
        "mqtt_runtime.py",
    ]

    missing_files = []
    for filename in required_files:
        if not (central_core_hub_dir / filename).exists():
            missing_files.append(filename)

    assert not missing_files, f"Missing required files for container: {missing_files}"


    # Arrange: inject a dummy 'helpers' and 'telemetry' module to force
    # the initial import in mqtt_client to raise ImportError for missing names.
    dummy_helpers = types.ModuleType("helpers")
    dummy_telemetry = types.ModuleType("telemetry")
    
    old_helpers = sys.modules.get("helpers")
    old_telemetry = sys.modules.get("telemetry")
    
    sys.modules["helpers"] = dummy_helpers
    sys.modules["telemetry"] = dummy_telemetry

    try:
        repo_root = Path(__file__).resolve().parents[3]
        src = repo_root / "central-core-hub" / "mqtt_client.py"
        spec = importlib.util.spec_from_file_location("fresh_mqtt_client", str(src))
        if spec is None or getattr(spec, "loader", None) is None:
            raise ImportError("could not load spec")
        mod = importlib.util.module_from_spec(spec)
        loader = spec.loader
        assert loader is not None
        loader.exec_module(mod)

        # After import, the fallback should have installed build_telemetry
        assert hasattr(mod, "build_telemetry")
        # calling build_telemetry should return JSON string
        res = mod.build_telemetry("cid-fallback")
        assert isinstance(res, str)
    finally:
        # cleanup fresh_mqtt_client
        if "fresh_mqtt_client" in sys.modules:
            del sys.modules["fresh_mqtt_client"]
            
        # restore helpers
        if old_helpers is not None:
            sys.modules["helpers"] = old_helpers
        else:
            sys.modules.pop("helpers", None)
            
        # restore telemetry
        if old_telemetry is not None:
            sys.modules["telemetry"] = old_telemetry
        else:
            sys.modules.pop("telemetry", None)
