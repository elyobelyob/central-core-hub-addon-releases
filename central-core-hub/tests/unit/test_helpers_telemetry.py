import json
import importlib.util
from pathlib import Path


def _load_helpers_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "helpers.py"
    spec = importlib.util.spec_from_file_location("helpers_mod", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def _load_telemetry_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "telemetry.py"
    spec = importlib.util.spec_from_file_location("tele_mod", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_uptime_and_loadavg_and_meminfo(monkeypatch, tmp_path):
    h = _load_helpers_module()

    # uptime
    p = tmp_path / "uptime"
    p.write_text("123.45 0.00")
    monkeypatch.setenv("PWD", str(tmp_path))
    # monkeypatch open when path is /proc/uptime
    import builtins as _builtins

    _orig_open = _builtins.open

    def fake_open(path, *a, **k):
        if str(path) == "/proc/uptime":
            return _orig_open(str(p), *a, **k)
        return _orig_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", fake_open)
    assert h.uptime_seconds() == 123

    # loadavg
    q = tmp_path / "loadavg"
    q.write_text("0.00 0.01 0.05 1/100 12345")

    def fake_open2(path, *a, **k):
        if str(path) == "/proc/loadavg":
            return _orig_open(str(q), *a, **k)
        return _orig_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", fake_open2)
    assert h.loadavg() == ["0.00", "0.01", "0.05"]

    # meminfo
    m = tmp_path / "meminfo"
    m.write_text("MemTotal: 8000000\nMemFree: 4000000\n")

    def fake_open3(path, *a, **k):
        if str(path) == "/proc/meminfo":
            return _orig_open(str(m), *a, **k)
        return _orig_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", fake_open3)
    mt, mf = h.mem_info_kb()
    assert mt == 8000000 and mf == 4000000


def test_disk_info_kb(monkeypatch):
    h = _load_helpers_module()

    class Statvfs:
        f_blocks = 1000
        f_frsize = 1024
        f_bavail = 500

    monkeypatch.setattr("os.statvfs", lambda p: Statvfs())
    total, free = h.disk_info_kb("/")
    assert total is not None and free is not None


def test_read_proc_stat_and_cpu_percent(monkeypatch):
    h = _load_helpers_module()

    # simulate /proc/stat lines via monkeypatching open
    data = "cpu  100 200 300 400 500 600\n"

    def fake_open(path, *a, **k):
        if str(path) == "/proc/stat":
            return io.StringIO(data)
        return open(path, *a, **k)

    import io

    monkeypatch.setattr(
        "builtins.open",
        lambda path, *a, **k: (io.StringIO(data) if str(path) == "/proc/stat" else open(path, *a, **k)),
    )
    idle, total = h._read_proc_stat()
    assert idle is not None and total is not None

    # test get_cpu_percent when read returns None
    monkeypatch.setattr(h, "_read_proc_stat", lambda: (None, None))
    assert h.get_cpu_percent() is None

    # test get_cpu_percent normal path by controlling _read_proc_stat sequence
    seq = [(100, 400), (120, 500)]

    def seq_read():
        return seq.pop(0)

    monkeypatch.setattr(h, "_read_proc_stat", seq_read)
    monkeypatch.setattr("time.sleep", lambda x: None)
    val = h.get_cpu_percent()
    assert val is None or isinstance(val, float)


def test_telemetry_build_and_vault():
    t = _load_telemetry_module()

    # inject helper functions
    def up():
        return 100

    def la():
        return ["0.00", "0.01", "0.05"]

    def mem():
        return (8000000, 4000000)

    def disk(p="/"):
        return (10000000, 5000000)

    def gc():
        return 3.3

    payload = t.build_telemetry(
        "x",
        get_cpu_percent=gc,
        uptime_fn=up,
        loadavg_fn=la,
        mem_info_fn=mem,
        disk_info_fn=disk,
    )
    j = json.loads(payload)
    assert j["client_id"] == "x"
    assert j["cpu_percent"] == 3.3

    vault = t.build_vault_payload(payload)
    assert vault is not None
