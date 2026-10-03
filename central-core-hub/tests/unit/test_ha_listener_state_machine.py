"""HAWebSocketListener without a thread: subscription bookkeeping, how
subscribe_entities messages become state dicts, and request/reply matching."""

import json
import threading

import pytest

import ha_client

# conftest silences HAWebSocketListener._log for every test; these tests read the log.
_REAL_LOG = ha_client.HAWebSocketListener._log


@pytest.fixture(autouse=True)
def _real_log(monkeypatch):
    monkeypatch.setattr(ha_client.HAWebSocketListener, "_log", _REAL_LOG)


class _Sock:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send(self, data):
        if self.fail:
            raise OSError("socket closed")
        self.sent.append(json.loads(data))

    def close(self):
        pass


def _listener(**kw):
    logs = []
    lst = ha_client.HAWebSocketListener("http://homeassistant:8123", "tok", kw.pop("on_event", None),
                                        log_fn=logs.append, **kw)
    return lst, logs


def _connected(lst, sock=None):
    lst._ws = sock or _Sock()
    lst._authed = True
    return lst._ws


# --- selection and subscription ---------------------------------------------


def test_same_selection_does_not_resubscribe():
    lst, _ = _listener(selectors=["binary_sensor.door"])
    sock = _connected(lst)
    lst.update_selectors(["binary_sensor.door"])
    assert sock.sent == []


def test_new_selection_unsubscribes_old_and_drops_unwatched_states():
    lst, logs = _listener(selectors=["binary_sensor.door"])
    sock = _connected(lst)
    lst._sub_id = 7
    lst._states = {"binary_sensor.door": {"state": "on"}, "sensor.temp": {"state": "20"}}
    lst.update_selectors(["sensor.temp", "bad id!"])
    assert sock.sent[0] == {"type": "unsubscribe_events", "subscription": 7, "id": 3}
    assert sock.sent[1]["type"] == "subscribe_entities"
    assert sock.sent[1]["entity_ids"] == ["sensor.temp"]  # invalid ids never reach HA
    assert set(lst._states) == {"sensor.temp"}
    assert "HA WS watching 1 entities" in logs


def test_subscribe_failure_is_logged_not_raised():
    lst, logs = _listener()
    _connected(lst)

    def boom(_payload):
        raise RuntimeError("send failed")

    lst._send_command = boom
    lst.update_selectors(["sensor.temp"])
    assert any("HA WS subscribe failed: send failed" in m for m in logs)
    assert lst._sub_id is None


def test_streaming_and_connected_flags():
    lst, _ = _listener()
    assert lst.is_connected() is False and lst.is_streaming() is False
    _connected(lst)
    assert lst.is_connected() is True and lst.is_streaming() is False
    lst._handle_entities_event({"a": {}})
    assert lst.is_streaming() is True


# --- compressed states --------------------------------------------------------


@pytest.mark.parametrize("bad", ["soon", [], 1e30])
def test_unreadable_epoch_is_none(bad):
    assert ha_client.HAWebSocketListener._iso_from_epoch(bad) is None


def test_diff_with_only_last_updated_keeps_last_changed_and_removes_attributes():
    lst, _ = _listener()
    base = {"entity_id": "sensor.t", "state": "20", "attributes": {"unit": "C", "icon": "x"},
            "last_changed": "2026-01-01T00:00:00+00:00", "last_updated": "2026-01-01T00:00:00+00:00"}
    out = lst._apply_diff(base, {"+": {"lu": 0, "a": {"friendly_name": "T"}}, "-": {"a": ["icon"]}})
    assert out["state"] == "20"
    assert out["last_changed"] == "2026-01-01T00:00:00+00:00"
    assert out["last_updated"] == "1970-01-01T00:00:00+00:00"
    assert out["attributes"] == {"unit": "C", "friendly_name": "T"}
    assert base["attributes"] == {"unit": "C", "icon": "x"}  # base not modified


def test_snapshot_without_snapshot_callback_goes_to_on_event_then_changes_and_removals():
    events = []
    lst, _ = _listener(on_event=lambda eid, st: events.append((eid, st["state"])))
    lst._handle_entities_event({"a": {"binary_sensor.door": {"s": "off", "lc": 10}}})
    lst._handle_entities_event({"c": {"binary_sensor.door": {"+": {"s": "on", "lc": 20}},
                                      "sensor.unknown": {"+": {"s": "1"}}}})
    lst._handle_entities_event({"r": ["binary_sensor.door"]})
    assert events == [("binary_sensor.door", "off"), ("binary_sensor.door", "on")]  # unknown entity ignored
    assert lst._states == {}


def test_ws_url_follows_scheme():
    assert _listener()[0]._ws_url() == "ws://homeassistant:8123/api/websocket"
    lst, _ = _listener()
    lst.ha_api_url = "https://ha.example/"
    assert lst._ws_url() == "wss://ha.example/api/websocket"
    lst.ha_api_url = "  "
    assert lst._ws_url() is None


# --- start ------------------------------------------------------------------


def test_start_without_websocket_library_is_refused(monkeypatch):
    monkeypatch.setattr(ha_client, "websocket", None)
    lst, logs = _listener()
    assert lst.start() is False
    assert "websocket-client not installed; HA WS disabled" in logs


def test_start_is_idempotent_while_thread_runs(monkeypatch):
    lst, _ = _listener()
    alive = threading.Event()
    stop = threading.Event()
    lst._thread = threading.Thread(target=lambda: (alive.set(), stop.wait(2)))
    lst._thread.start()
    alive.wait(1)
    try:
        before = lst._thread
        assert lst.start() is True
        assert lst._thread is before  # no second thread
    finally:
        stop.set()
        before.join(1)


# --- request / call_service ---------------------------------------------------


def test_request_returns_none_when_not_connected():
    lst, _ = _listener()
    assert lst.request({"type": "get_states"}) is None
    assert lst.call_service("light", "turn_on") is None


def test_request_times_out_and_forgets_the_pending_id():
    lst, _ = _listener()
    sock = _connected(lst)
    assert lst.request({"type": "get_states"}, timeout=0.01) is None
    assert sock.sent == [{"type": "get_states", "id": 3}]
    assert lst._pending_requests == {}


def test_reply_for_the_request_id_is_returned():
    lst, _ = _listener()
    _connected(lst)
    reply = {"id": 3, "type": "result", "success": True, "result": [1]}
    threading.Timer(0.02, lambda: lst._set_pending_result(3, reply)).start()
    assert lst.request({"type": "get_states"}, timeout=2) == reply


def test_call_service_sends_service_data_and_returns_reply():
    lst, _ = _listener()
    sock = _connected(lst)
    threading.Timer(0.02, lambda: lst._set_pending_result(3, {"success": True})).start()
    assert lst.call_service("light", "turn_on", {"entity_id": "light.x"}, timeout=2) == {"success": True}
    assert sock.sent == [{"type": "call_service", "domain": "light", "service": "turn_on",
                          "service_data": {"entity_id": "light.x"}, "id": 3}]


def test_result_for_unknown_or_missing_id_is_ignored():
    lst, _ = _listener()
    lst._set_pending_result(None, {"x": 1})
    lst._set_pending_result(99, {"x": 1})
    assert lst._pending_requests == {}
