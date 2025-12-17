import importlib.util
import pathlib


def _load_module():
    base = pathlib.Path(__file__).parents[2]
    src = base / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load ha_client spec")
    spec.loader.exec_module(mod)
    return mod


ha = _load_module()


class BadSock:
    def send(self, _s):
        raise RuntimeError("send-bad")


def test_send_json_swallow_exception(capfd):
    sock = BadSock()
    # should not raise
    ha.HAWebSocketListener._send_json(None, sock, {"type": "ping"})
    # prints traceback to stderr; ensure function returned without raising
    captured = capfd.readouterr()
    assert captured.err != ""


def test_call_service_returns_none_when_no_ws():
    listener = ha.HAWebSocketListener("http://ha", "tok", None)
    listener._ws = None
    res = listener.call_service("domain", "svc", {"a": 1}, timeout=0.1)
    assert res is None


def test_persist_ha_version_write_fails(tmp_path, monkeypatch):
    opts = tmp_path / "options.json"
    # create a directory at the options path so writing fails
    opts.mkdir()
    ha.OPTIONS_PATH = str(opts)

    listener = ha.HAWebSocketListener("http://ha", "tok", None)
    ok = listener._persist_ha_version("9.9.9")
    assert ok is False
    # ensure the directory still exists and no file was created
    assert opts.exists() and opts.is_dir()
