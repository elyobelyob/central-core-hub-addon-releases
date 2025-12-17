import json
import time
import pathlib
import importlib.util
import types


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


class FakeWS:
    def __init__(self, msgs):
        self._msgs = list(msgs)
        self.sent = []
        self.closed = False

    def send(self, s):
        self.sent.append(s)

    def recv(self):
        if not self._msgs:
            # simulate connection error to break loop
            raise RuntimeError("ws-done")
        return self._msgs.pop(0)

    def close(self):
        self.closed = True


def test_ha_ws_run_auth_and_event(tmp_path):
    # prepare fake websocket module
    msgs = [
        json.dumps({"type": "auth_required", "ha_version": "2025.1.0"}),
        json.dumps({"type": "auth_ok"}),
        # result for id=2 (get_config)
        json.dumps({"type": "result", "id": 2, "result": {"version": "2025.1.0"}}),
        # event for selector
        json.dumps({"type": "event", "event": {"data": {"entity_id": "sensor.a", "new_state": {"state": "on"}}}}),
    ]

    fake_ws = FakeWS(msgs)

    fake_ws_mod = types.SimpleNamespace()
    fake_ws_mod.create_connection = lambda url, timeout=None: fake_ws
    # provide exception classes so ha_client can match them (not strictly required)
    fake_ws_mod.WebSocketTimeoutException = RuntimeError
    fake_ws_mod.WebSocketAddressException = RuntimeError
    fake_ws_mod.WebSocketConnectionClosedException = RuntimeError

    # Monkeypatch module websocket and options path
    ha.websocket = fake_ws_mod
    ha.OPTIONS_PATH = str(tmp_path / "options.json")

    events = []

    def on_event(ent_id, new_state):
        events.append((ent_id, new_state))

    listener = ha.HAWebSocketListener("http://ha", "tok", on_event, log_fn=lambda m: None, selectors={"sensor.a"})

    started = listener.start()
    assert started is True

    # Wait for the event to be processed or timeout
    deadline = time.time() + 2.0
    while time.time() < deadline and not events:
        time.sleep(0.01)

    # stop the listener
    listener.stop()

    assert events, "expected on_event to be called"
    assert events[0][0] == "sensor.a"
    assert isinstance(events[0][1], dict)

    # ensure options file was written with ha_version
    opts = pathlib.Path(ha.OPTIONS_PATH)
    assert opts.exists()
    data = json.loads(opts.read_text())
    assert data.get("ha_version") == "2025.1.0"
