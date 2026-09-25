"""Perf #1/#5: the websocket watches only the selected entities.

The listener used `subscribe_events state_changed` (every change in the house,
filtered after json.loads). It now uses `subscribe_entities` with the selected
entity ids, re-subscribes when the selection changes, and expands HA's
compressed state/diff messages into ordinary state dicts.
"""

import json
import queue
import threading
import time

import pytest

import ha_client


class _FakeWS:
    def __init__(self):
        self.sent = []
        self.inbox = queue.Queue()
        self.closed = False

    def send(self, data):
        self.sent.append(json.loads(data))

    def recv(self):
        try:
            return self.inbox.get(timeout=0.05)
        except queue.Empty:
            raise ha_client.WebSocketTimeoutException("timeout")

    def close(self):
        self.closed = True

    def push(self, obj):
        self.inbox.put(json.dumps(obj))

    def wait_sent(self, pred, timeout=2.0):
        end = time.time() + timeout
        while time.time() < end:
            for m in list(self.sent):
                if pred(m):
                    return m
            time.sleep(0.01)
        raise AssertionError(f"not sent; sent={self.sent}")


@pytest.fixture
def ws(monkeypatch):
    sock = _FakeWS()
    sock.push({"type": "auth_required", "ha_version": "2026.9.0"})
    sock.push({"type": "auth_ok"})

    class _Mod:
        def create_connection(self, url, timeout=None):
            return sock

    monkeypatch.setattr(ha_client, "websocket", _Mod())
    monkeypatch.setattr(ha_client, "OPTIONS_PATH", "/nonexistent/options.json")
    return sock


def _listener(selectors, events, snapshots=None):
    lst = ha_client.HAWebSocketListener(
        "http://ha",
        "tok",
        on_event=lambda eid, st: events.append((eid, st)),
        selectors=selectors,
        on_snapshot=(lambda states: snapshots.append(states)) if snapshots is not None else None,
    )
    assert lst.start()
    return lst


def _wait(pred, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met")


def test_subscribes_only_to_selected_entities(ws):
    events = []
    lst = _listener({"sensor.b", "sensor.a"}, events)
    try:
        sub = ws.wait_sent(lambda m: m.get("type") == "subscribe_entities")
        assert sub["entity_ids"] == ["sensor.a", "sensor.b"]
        assert not any(m.get("type") == "subscribe_events" for m in ws.sent)
    finally:
        lst.stop()


def test_no_selection_means_no_subscription(ws):
    lst = _listener(set(), [])
    try:
        ws.wait_sent(lambda m: m.get("type") == "get_config")
        time.sleep(0.1)
        assert not any(m.get("type", "").startswith("subscribe") for m in ws.sent)
        assert lst.is_streaming() is False
    finally:
        lst.stop()


def test_snapshot_then_diffs_are_expanded(ws):
    events, snapshots = [], []
    lst = _listener({"binary_sensor.door"}, events, snapshots)
    try:
        sub = ws.wait_sent(lambda m: m.get("type") == "subscribe_entities")
        ws.push({"type": "result", "id": sub["id"], "success": True, "result": None})
        ws.push(
            {
                "type": "event",
                "id": sub["id"],
                "event": {
                    "a": {
                        "binary_sensor.door": {
                            "s": "off",
                            "a": {"device_class": "door", "friendly_name": "Door", "access_token": "x"},
                            "c": "ctx1",
                            "lc": 1758800000.5,
                        }
                    }
                },
            }
        )
        _wait(lambda: snapshots)
        snap = snapshots[0]
        assert len(snap) == 1
        st = snap[0]
        assert st["entity_id"] == "binary_sensor.door"
        assert st["state"] == "off"
        assert st["attributes"]["friendly_name"] == "Door"
        assert st["last_changed"].startswith("2025-09-25T11:33:20.5")
        assert st["last_updated"] == st["last_changed"]
        assert lst.is_streaming() is True

        # state change: new state, new last_changed, one attribute changed, one removed
        ws.push(
            {
                "type": "event",
                "id": sub["id"],
                "event": {
                    "c": {
                        "binary_sensor.door": {
                            "+": {"s": "on", "lc": 1758800100.0, "a": {"friendly_name": "Front door"}},
                            "-": {"a": ["device_class"]},
                        }
                    }
                },
            }
        )
        _wait(lambda: events)
        eid, st2 = events[-1]
        assert eid == "binary_sensor.door"
        assert st2["state"] == "on"
        assert st2["attributes"]["friendly_name"] == "Front door"
        assert "device_class" not in st2["attributes"]
        assert st2["last_changed"].startswith("2025-09-25T11:35:00")
        assert st2["last_updated"] == st2["last_changed"]

        # attribute-only update: last_updated moves, last_changed stays
        ws.push(
            {"type": "event", "id": sub["id"], "event": {"c": {"binary_sensor.door": {"+": {"lu": 1758800200.0}}}}}
        )
        _wait(lambda: len(events) >= 2)
        st3 = events[-1][1]
        assert st3["last_changed"] == st2["last_changed"]
        assert st3["last_updated"].startswith("2025-09-25T11:36:40")
    finally:
        lst.stop()


def test_selection_change_resubscribes(ws):
    lst = _listener({"sensor.a"}, [])
    try:
        first = ws.wait_sent(lambda m: m.get("type") == "subscribe_entities")
        lst.update_selectors({"sensor.a", "sensor.c"})
        unsub = ws.wait_sent(lambda m: m.get("type") == "unsubscribe_events")
        assert unsub["subscription"] == first["id"]
        second = ws.wait_sent(lambda m: m.get("type") == "subscribe_entities" and m["id"] != first["id"])
        assert second["entity_ids"] == ["sensor.a", "sensor.c"]
        ids = [m["id"] for m in ws.sent if "id" in m]
        assert ids == sorted(ids) and len(set(ids)) == len(ids), "HA requires increasing message ids"
        # same selection again: nothing new is sent
        count = len(ws.sent)
        lst.update_selectors({"sensor.c", "sensor.a"})
        time.sleep(0.1)
        assert len(ws.sent) == count
    finally:
        lst.stop()


def test_events_for_an_old_subscription_are_ignored(ws):
    events = []
    lst = _listener({"sensor.a"}, events)
    try:
        first = ws.wait_sent(lambda m: m.get("type") == "subscribe_entities")
        lst.update_selectors({"sensor.b"})
        ws.wait_sent(lambda m: m.get("type") == "subscribe_entities" and m["id"] != first["id"])
        ws.push({"type": "event", "id": first["id"], "event": {"a": {"sensor.a": {"s": "1", "a": {}, "lc": 1.0}}}})
        time.sleep(0.2)
        assert events == []
    finally:
        lst.stop()


def test_invalid_selector_ids_are_not_subscribed(ws):
    lst = _listener({"sensor.a", "../x", "Sensor.B"}, [])
    try:
        sub = ws.wait_sent(lambda m: m.get("type") == "subscribe_entities")
        assert sub["entity_ids"] == ["sensor.a"]
    finally:
        lst.stop()


def test_listener_thread_is_not_blocked_by_update_selectors(ws):
    lst = _listener({"sensor.a"}, [])
    try:
        ws.wait_sent(lambda m: m.get("type") == "subscribe_entities")
        t = threading.Thread(target=lambda: [lst.update_selectors({f"sensor.x{i}"}) for i in range(20)])
        t.start()
        t.join(timeout=2)
        assert not t.is_alive()
    finally:
        lst.stop()
