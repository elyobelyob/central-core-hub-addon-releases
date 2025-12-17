import importlib.util
import pathlib
import json
import types
import builtins
import time


def _load_ha_client():
    base = pathlib.Path(__file__).parents[2]
    src = base / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load ha_client spec")
    spec.loader.exec_module(mod)
    return mod


ha_client = _load_ha_client()


class FakeWS:
    def __init__(self, msgs):
        self._msgs = list(msgs)
        self.sent = []
        self.closed = False

    def send(self, data):
        self.sent.append(data)

    def recv(self):
        if not self._msgs:
            time.sleep(0.01)
            return ""
        v = self._msgs.pop(0)
        if isinstance(v, Exception):
            raise v
        return v

    def close(self):
        self.closed = True


def _ws_module_for(msgs):
    mod = types.SimpleNamespace()

    def create_connection(*a, **k):
        return FakeWS(msgs)

    mod.create_connection = create_connection
    mod.WebSocketTimeoutException = Exception
    mod.WebSocketAddressException = Exception
    mod.WebSocketConnectionClosedException = Exception
    return mod


def test_get_config_result_writes_version(tmp_path, monkeypatch):
    # result with top-level version
    res_msg = {"type": "result", "id": 2, "result": {"version": "9.9.9"}}
    msgs = [json.dumps({"type": "auth_required"}), json.dumps({"type": "auth_ok"}), json.dumps(res_msg), ""]
    monkeypatch.setattr(ha_client, "websocket", _ws_module_for(msgs))
    monkeypatch.setattr(ha_client.HAWebSocketListener, "_log", lambda self, m: None)

    # point options path to tmp file
    opts = tmp_path / "opts.json"
    ha_client.OPTIONS_PATH = str(opts)

    called = []

    def on_ha_version(v):
        called.append(v)

    listener = ha_client.HAWebSocketListener("http://ha", "tok", None, on_ha_version=on_ha_version)
    assert listener.start()
    time.sleep(0.05)
    listener.stop()
    assert opts.exists()
    data = json.loads(opts.read_text())
    assert data.get("ha_version") == "9.9.9"
    assert called and called[0] == "9.9.9"


def test_get_config_result_with_config_key(tmp_path, monkeypatch):
    # result with nested config.version
    res_msg = {"type": "result", "id": 2, "result": {"config": {"version": "7.7.7"}}}
    msgs = [json.dumps({"type": "auth_required"}), json.dumps({"type": "auth_ok"}), json.dumps(res_msg), ""]
    monkeypatch.setattr(ha_client, "websocket", _ws_module_for(msgs))
    monkeypatch.setattr(ha_client.HAWebSocketListener, "_log", lambda self, m: None)

    opts = tmp_path / "opts2.json"
    ha_client.OPTIONS_PATH = str(opts)

    listener = ha_client.HAWebSocketListener("http://ha", "tok", None)
    assert listener.start()
    time.sleep(0.05)
    listener.stop()
    assert opts.exists()
    data = json.loads(opts.read_text())
    assert data.get("ha_version") == "7.7.7"


def test_persist_ha_version_write_failure(monkeypatch):
    # make open raise on write
    def fake_open(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(ha_client, "set_ha_version", lambda v, ts=None: None)
    listener = ha_client.HAWebSocketListener("http://ha", "tok", None)
    # should return False when persistence fails
    assert listener._persist_ha_version("x.y.z") is False
