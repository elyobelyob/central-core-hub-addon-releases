import importlib.util
import pathlib
import json
import time
import types


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
        # msgs: list of bytes/str or Exception instances to raise
        self._msgs = list(msgs)
        self.sent = []
        self.closed = False

    def send(self, data):
        self.sent.append(data)

    def recv(self):
        if not self._msgs:
            # simulate no data
            time.sleep(0.01)
            return ""
        v = self._msgs.pop(0)
        if isinstance(v, Exception):
            raise v
        return v

    def close(self):
        self.closed = True


def _make_ws_module(msgs):
    mod = types.SimpleNamespace()

    def create_connection(*a, **k):
        return FakeWS(msgs)

    mod.create_connection = create_connection
    # set exception classes so _run can detect them if needed
    mod.WebSocketTimeoutException = Exception
    mod.WebSocketAddressException = Exception
    mod.WebSocketConnectionClosedException = Exception
    return mod


def test_unexpected_hello(monkeypatch):
    msgs = [json.dumps({"type": "hello"}), ""]
    monkeypatch.setattr(ha_client, "websocket", _make_ws_module(msgs))
    # silence logging
    monkeypatch.setattr(ha_client.HAWebSocketListener, "_log", lambda self, m: None)

    evs = []

    def on_event(eid, new):
        evs.append((eid, new))

    listener = ha_client.HAWebSocketListener("http://ha", "tok", on_event)
    started = listener.start()
    assert started
    # give the thread a short moment to process
    time.sleep(0.05)
    listener.stop()
    # we didn't get events; just ensure thread stopped and ws closed
    assert not getattr(listener, "_thread", None)


def test_auth_failed(monkeypatch):
    msgs = [json.dumps({"type": "auth_required"}), json.dumps({"type": "auth_invalid"}), ""]
    monkeypatch.setattr(ha_client, "websocket", _make_ws_module(msgs))
    monkeypatch.setattr(ha_client.HAWebSocketListener, "_log", lambda self, m: None)

    listener = ha_client.HAWebSocketListener("http://ha", "tok", None)
    assert listener.start()
    time.sleep(0.05)
    listener.stop()
    assert getattr(listener, "_thread", None) is None


def test_event_dispatch(monkeypatch):
    # auth_required with ha_version, auth_ok, then an event
    ev = {"type": "event", "event": {"data": {"entity_id": "sensor.x", "new_state": {"state": "1"}}}}
    msgs = [
        json.dumps({"type": "auth_required", "ha_version": "v"}),
        json.dumps({"type": "auth_ok"}),
        json.dumps(ev),
        "",
    ]
    monkeypatch.setattr(ha_client, "websocket", _make_ws_module(msgs))
    monkeypatch.setattr(ha_client.HAWebSocketListener, "_log", lambda self, m: None)

    collected = []

    def on_event(eid, new_state):
        collected.append((eid, new_state))

    listener = ha_client.HAWebSocketListener("http://ha", "tok", on_event, selectors={"sensor.x"})
    assert listener.start()
    # wait for event processing
    timeout = time.time() + 1.0
    while time.time() < timeout and not collected:
        time.sleep(0.02)
    listener.stop()
    assert collected and collected[0][0] == "sensor.x"
