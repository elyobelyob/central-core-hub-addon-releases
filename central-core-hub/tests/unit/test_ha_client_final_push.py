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


def _ws_mod(msgs):
    m = types.SimpleNamespace()

    def create_connection(*a, **k):
        return FakeWS(msgs)

    m.create_connection = create_connection
    m.WebSocketTimeoutException = Exception
    m.WebSocketAddressException = Exception
    m.WebSocketConnectionClosedException = Exception
    return m


def test_pending_result_is_set(monkeypatch):
    # register a pending request, then run loop which will deliver a result
    listener = ha_client.HAWebSocketListener("http://ha", "tok", None)
    req_id, ev = listener._register_request()

    # craft messages: auth_required, auth_ok, then a result for req_id
    msgs = [
        json.dumps({"type": "auth_required"}),
        json.dumps({"type": "auth_ok"}),
        json.dumps({"type": "result", "id": req_id, "result": {"x": 1}}),
        "",
    ]
    monkeypatch.setattr(ha_client, "websocket", _ws_mod(msgs))
    monkeypatch.setattr(ha_client.HAWebSocketListener, "_log", lambda self, m: None)

    assert listener.start()
    # wait for event to be set by _run
    timeout = time.time() + 1.0
    while time.time() < timeout and not ev.is_set():
        time.sleep(0.01)
    listener.stop()

    assert ev.is_set()
    # pending result should be present (the stored payload is the full
    # result message; the actual result is nested under the `result` key)
    with listener._prot_req_lock:
        pending = listener._pending_requests.get(req_id)
    assert pending is not None and pending.get("result", {}).get("result") == {"x": 1}


def test_pong_and_unknown_message_ignored(monkeypatch):
    msgs = [
        json.dumps({"type": "auth_required"}),
        json.dumps({"type": "auth_ok"}),
        json.dumps({"type": "pong"}),
        json.dumps({"type": "something_else"}),
        "",
    ]
    monkeypatch.setattr(ha_client, "websocket", _ws_mod(msgs))
    monkeypatch.setattr(ha_client.HAWebSocketListener, "_log", lambda self, m: None)
    called = []

    def on_event(eid, new):
        called.append((eid, new))

    listener = ha_client.HAWebSocketListener("http://ha", "tok", on_event)
    assert listener.start()
    time.sleep(0.05)
    listener.stop()
    # no events delivered
    assert not called


def test_event_filtered_by_selectors(monkeypatch):
    ev = {"type": "event", "event": {"data": {"entity_id": "sensor.skip", "new_state": {}}}}
    ev2 = {"type": "event", "event": {"data": {"entity_id": "sensor.yes", "new_state": {"state": "1"}}}}
    msgs = [json.dumps({"type": "auth_required"}), json.dumps({"type": "auth_ok"}), json.dumps(ev), json.dumps(ev2), ""]
    monkeypatch.setattr(ha_client, "websocket", _ws_mod(msgs))
    monkeypatch.setattr(ha_client.HAWebSocketListener, "_log", lambda self, m: None)

    collected = []

    def on_event(eid, new_state):
        collected.append((eid, new_state))

    listener = ha_client.HAWebSocketListener("http://ha", "tok", on_event, selectors={"sensor.yes"})
    assert listener.start()
    timeout = time.time() + 1.0
    while time.time() < timeout and not collected:
        time.sleep(0.01)
    listener.stop()
    assert collected and collected[0][0] == "sensor.yes"
