"""Perf #1: no periodic GET /api/states while the websocket is streaming.

The 30 s loop used to fetch every Home Assistant state. Now the websocket is
the source of changes; the REST fallback runs only while it is not streaming,
and then fetches just the selected entities by id.
"""

import importlib
import json
import types

import pytest


@pytest.fixture
def mc(monkeypatch, tmp_path):
    mod = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mod, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    return mod


class _Listener:
    def __init__(self, streaming):
        self.streaming = streaming
        self.selectors = set()

    def is_streaming(self):
        return self.streaming

    def update_selectors(self, sel):
        self.selectors = set(sel)

    def stop(self):
        pass


def _client(mc, monkeypatch, streaming):
    c = mc.CentralCoreClient({"client_id": "hub1", "ha_api_url": "http://localhost:8123", "ha_api_token": "tok"})
    c._ha_ws_listener = _Listener(streaming)
    sent = []
    monkeypatch.setattr(c, "_publish", lambda topic, payload, qos=0: sent.append(json.loads(payload)))
    calls = {"all": 0, "ids": []}

    def all_states(*a, **k):
        calls["all"] += 1
        return []

    def by_ids(url, token, ids):
        calls["ids"].append(list(ids))
        return [{"entity_id": e, "state": "1", "attributes": {}} for e in ids]

    monkeypatch.setattr(mc, "fetch_sensors", all_states)
    monkeypatch.setattr(mc, "fetch_selected_sensors", by_ids)
    c.selected_sensors = ["sensor.a", "sensor.b"]
    return c, sent, calls


def test_no_rest_poll_while_streaming(mc, monkeypatch):
    c, sent, calls = _client(mc, monkeypatch, streaming=True)
    c.publish_selected_sensor_changes()
    assert calls == {"all": 0, "ids": []}
    assert sent == []


def test_rest_fallback_fetches_selected_ids_only(mc, monkeypatch):
    c, sent, calls = _client(mc, monkeypatch, streaming=False)
    c.publish_selected_sensor_changes()
    assert calls["all"] == 0
    assert calls["ids"] == [["sensor.a", "sensor.b"]]
    assert sent and set(sent[-1]["data"]) == {"sensor.a", "sensor.b"}


def test_ws_snapshot_is_published_once(mc, monkeypatch):
    c, sent, calls = _client(mc, monkeypatch, streaming=True)
    snap = [
        {"entity_id": "sensor.a", "state": "1", "attributes": {"friendly_name": "A"}, "last_changed": "2026-01-01T00:00:00+00:00"},
        {"entity_id": "sensor.b", "state": "2", "attributes": {}, "last_changed": "2026-01-01T00:00:01+00:00"},
    ]
    c._on_ha_snapshot(snap)
    assert len(sent) == 1
    assert sent[0]["data"] == {"sensor.a": "1", "sensor.b": "2"}
    # a reconnect delivers the same snapshot: nothing new to send
    c._on_ha_snapshot(snap)
    assert len(sent) == 1


def test_listener_is_given_the_snapshot_callback(mc, monkeypatch):
    created = {}

    class _L:
        def __init__(self, url, token, on_event=None, log_fn=None, selectors=None, on_ha_version=None, on_snapshot=None):
            created["on_snapshot"] = on_snapshot

        def start(self):
            return True

    monkeypatch.setattr(importlib.import_module("ha_client"), "HAWebSocketListener", _L)
    mc.CentralCoreClient({"client_id": "hub1", "ha_api_url": "http://localhost:8123", "ha_api_token": "tok"})
    assert callable(created["on_snapshot"])


def test_fetch_selected_sensors_applies_registry(mc, monkeypatch):
    class _R:
        def __init__(self, eid):
            self.eid = eid

        def raise_for_status(self):
            return None

        def json(self):
            return {"entity_id": self.eid, "state": "1", "attributes": {}}

    req = types.SimpleNamespace(get=lambda url, headers=None, timeout=None: _R(url.rsplit("/", 1)[-1]))
    monkeypatch.setattr(mc, "requests", req)
    monkeypatch.setattr(mc, "is_entity_allowed", lambda e: e != "sensor.private")
    out = mc.fetch_selected_sensors("http://localhost:8123", "tok", ["sensor.a", "sensor.private"])
    assert [s["entity_id"] for s in out] == ["sensor.a"]
