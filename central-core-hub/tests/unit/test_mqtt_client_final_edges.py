import importlib
import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapped_build_telemetry_sets_external_get_cpu(monkeypatch):
    mc = _load_module()
    # find the underlying telemetry module used by _orig_bt
    _orig = getattr(mc, "_orig_bt", None)
    modname = getattr(_orig, "__module__", None)
    tele_mod = None
    if modname:
        tele_mod = sys.modules.get(modname)
        if tele_mod is None:
            try:
                tele_mod = importlib.import_module(modname)
            except Exception:
                tele_mod = None

    # Replace telemetry.build_telemetry with function that reads the
    # _external_get_cpu_percent attribute placed by the wrapper
    if tele_mod is not None:

        def fake_bt(cid):
            val = getattr(tele_mod, "_external_get_cpu_percent", lambda: None)()
            return json.dumps({"client_id": cid, "cpu_percent": val})

        monkeypatch.setattr(tele_mod, "build_telemetry", fake_bt)

    # monkeypatch mqtt_client.get_cpu_percent so wrapper will set it
    monkeypatch.setattr(mc, "get_cpu_percent", lambda: 77.7)

    out = mc.build_telemetry("cid-edge")
    j = json.loads(out)
    assert j.get("cpu_percent") == 77.7


def test_get_cpu_percent_proc_stat(monkeypatch):
    mc = _load_module()

    # provide a _read_proc_stat that returns two different snapshots
    seq = {"calls": 0}

    def fake_read():
        seq["calls"] += 1
        if seq["calls"] == 1:
            return 100, 200
        else:
            return 110, 220

    monkeypatch.setattr(mc, "_read_proc_stat", fake_read)
    monkeypatch.setattr(mc.time, "sleep", lambda s: None)
    res = mc.get_cpu_percent()
    assert res is not None
    # Expect 50.0 from the chosen numbers
    assert abs(res - 50.0) < 0.1


def test_run_calls_loop_stop_and_disconnect(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({"client_id": "run-cleanup"})

    called = {"loop_stop": False, "disconnect": False}

    class ClientShim:
        def loop_stop(self):
            called["loop_stop"] = True

        def disconnect(self):
            called["disconnect"] = True

    c._client = ClientShim()

    # ensure connect returns and run_iteration raises to exit loop
    monkeypatch.setattr(c, "connect", lambda: True)

    def boom():
        raise RuntimeError("stop-run")

    monkeypatch.setattr(c, "run_iteration", boom)

    try:
        c.run()
    except RuntimeError:
        pass

    assert called["loop_stop"] is True
    assert called["disconnect"] is True
