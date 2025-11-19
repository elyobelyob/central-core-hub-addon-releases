import importlib.util
from pathlib import Path
import types


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_init_falls_back_to_shim_when_runtime_and_file_fail(monkeypatch):
    mcpath = Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("fresh_mqtt_client", str(mcpath))
    mc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mc)

    # Create a fake mqtt_runtime module whose setup raises
    fake_rt = types.ModuleType("mqtt_runtime")

    def bad_setup(ctx, mqtt_mod):
        raise RuntimeError("setup fail")

    fake_rt.setup_mqtt_client = bad_setup

    import sys

    sys.modules["mqtt_runtime"] = fake_rt

    # Monkeypatch importlib.util.spec_from_file_location to raise when attempting file fallback
    real_spec = importlib.util.spec_from_file_location

    def raise_spec(name, path):
        if "mqtt_runtime.py" in str(path):
            raise RuntimeError("fallback load fail")
        return real_spec(name, path)

    monkeypatch.setattr(importlib.util, "spec_from_file_location", raise_spec)

    try:
        # instantiate client; both setup attempts should fail and shim created
        CentralCoreClient = mc.CentralCoreClient
        c = CentralCoreClient({"client_id": "shim-test"})
        # shim should provide publish method
        assert hasattr(c, "_client")
        assert hasattr(c._client, "publish")
        # publishing should return an object or not raise
        c._client.publish("t", "p")
    finally:
        # cleanup
        del sys.modules["mqtt_runtime"]
        monkeypatch.setattr(importlib.util, "spec_from_file_location", real_spec)


def test_on_message_handler_imports_fail_silently(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({"client_id": "onmsg-fallback"})

    # Ensure no handlers module is present and file-based import will fail
    import sys

    if "handlers" in sys.modules:
        del sys.modules["handlers"]

    real_spec = importlib.util.spec_from_file_location

    def raise_spec(name, path):
        if "handlers.py" in str(path):
            raise RuntimeError("no handlers file")
        return real_spec(name, path)

    monkeypatch.setattr(importlib.util, "spec_from_file_location", raise_spec)

    try:
        # call on_message with a buffer payload; should not raise
        msg = types.SimpleNamespace(
            topic=f"hubs/{c.client_id}/cmd/sensors/poll", payload=b"{}"
        )
        c.on_message(None, None, msg)
    finally:
        monkeypatch.setattr(importlib.util, "spec_from_file_location", real_spec)


def test_telemetry_get_cpu_uses_m2_module(monkeypatch):
    # load telemetry module directly
    repo_root = Path(__file__).resolve().parents[3]
    tele_path = repo_root / "central-core-hub" / "telemetry.py"
    spec = importlib.util.spec_from_file_location("telemetry_test", str(tele_path))
    tele = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tele)

    # use the telemetry module's external override path to exercise that branch
    fake = types.ModuleType("m2")
    fake.get_cpu_percent = lambda: 9.9
    tele._external_get_cpu_percent = fake.get_cpu_percent
    try:
        assert tele._get_cpu_percent() == 9.9
    finally:
        delattr(tele, "_external_get_cpu_percent")
