import importlib.util
from pathlib import Path


def _load_telemetry():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "telemetry.py"
    spec = importlib.util.spec_from_file_location("telemetry", str(src))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_telemetry_with_injected_helpers(monkeypatch):
    tele = _load_telemetry()

    # Provide deterministic helper functions
    def uptime_fn():
        return 12345

    def loadavg_fn():
        return [0.1, 0.2, 0.3]

    def mem_info_fn():
        return (8000000, 4000000)

    def disk_info_fn(path="/"):
        return (16000000, 8000000)

    def get_cpu():
        return 12.3

    # Monkeypatch socket.socket to return a known local IP
    class Sock:
        def __init__(self, *a, **k):
            pass

        def connect(self, addr):
            return None

        def getsockname(self):
            return ("10.20.30.40", 12345)

        def close(self):
            return None

    monkeypatch.setattr("socket.socket", lambda *a, **k: Sock())

    payload = tele.build_telemetry(
        "hub-x",
        get_cpu_percent=get_cpu,
        uptime_fn=uptime_fn,
        loadavg_fn=loadavg_fn,
        mem_info_fn=mem_info_fn,
        disk_info_fn=disk_info_fn,
        version="v1",
        telemetry_interval=30,
    )

    obj = __import__("json").loads(payload)
    assert obj["client_id"] == "hub-x"
    assert obj["uptime"] == 12345
    assert obj["load_avg"] == [0.1, 0.2, 0.3]
    assert obj["mem_total_kb"] == 8000000
    assert obj["disk_free_kb"] == 8000000
    assert obj["cpu_percent"] == 12.3
    assert obj["ip"] == "10.20.30.40"


def test__get_cpu_percent_external_override_and_fallback(monkeypatch):
    tele = _load_telemetry()

    # set external override that raises -> should be handled gracefully
    def bad():
        raise RuntimeError("boom")

    tele._external_get_cpu_percent = bad
    # ensure no exception when building telemetry
    p = tele.build_telemetry("hub-y")
    obj = __import__("json").loads(p)
    # cpu_percent may be None in this case
    assert "cpu_percent" in obj
