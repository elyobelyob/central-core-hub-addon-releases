import json
import threading
import importlib.util
from pathlib import Path


def load_ha_module():
    p = Path(__file__).resolve().parents[2] / "central-core-hub" / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_call_service_no_ws_returns_none():
    ha = load_ha_module()
    listener = ha.HAWebSocketListener("http://ha", "tok", lambda a, b: None)
    # _ws is None by default
    assert listener.call_service("domain", "svc") is None


def test_call_service_success_returns_result():
    ha = load_ha_module()
    listener = ha.HAWebSocketListener("http://ha", "tok", lambda a, b: None)
    # make a dummy _ws so send doesn't error
    listener._ws = object()
    # prepare pending request with event already set
    ev = threading.Event()
    ev.set()
    listener._pending_requests[5] = {"event": ev, "result": {"ok": True}}

    # monkeypatch _register_request to return our id
    def fake_reg():
        return 5, ev

    listener._register_request = fake_reg

    # also monkeypatch _send_json to no-op
    listener._send_json = lambda sock, obj: None

    res = listener.call_service("d", "s", {"a": 1}, timeout=0.1)
    assert res == {"ok": True}


def test_call_service_send_fails_cleans_up():
    ha = load_ha_module()
    listener = ha.HAWebSocketListener("http://ha", "tok", lambda a, b: None)
    listener._ws = object()
    ev = threading.Event()
    listener._pending_requests[7] = {"event": ev, "result": None}

    def fake_reg():
        return 7, ev

    listener._register_request = fake_reg

    def bad_send(sock, obj):
        raise RuntimeError("send fail")

    listener._send_json = bad_send

    res = listener.call_service("d", "s")
    assert res is None


def test_persist_ha_version_writes_and_calls_callback(tmp_path):
    ha = load_ha_module()
    opts = tmp_path / "options.json"
    opts.write_text(json.dumps({}))

    # point OPTIONS_PATH to our tmp file
    ha.OPTIONS_PATH = str(opts)

    called = {"cb": False}

    def cb(v):
        called["cb"] = True

    listener = ha.HAWebSocketListener("http://ha", "tok", None, on_ha_version=cb)
    ok = listener._persist_ha_version("9.9.9")
    assert ok is True
    data = json.loads(opts.read_text())
    assert data.get("ha_version") == "9.9.9"
    assert called["cb"] is True


def test_persist_ha_version_write_fails(monkeypatch, tmp_path):
    ha = load_ha_module()
    opts = tmp_path / "options.json"
    opts.write_text(json.dumps({}))
    ha.OPTIONS_PATH = str(opts)

    # make open raise on write
    import builtins

    real_open = builtins.open

    def fake_open(path, mode="r", *args, **kwargs):
        if "w" in mode:
            raise OSError("write fail")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)

    listener = ha.HAWebSocketListener("http://ha", "tok", None)
    ok = listener._persist_ha_version("1.0")
    assert ok is False
