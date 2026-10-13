"""Status telemetry says whether Home Assistant is feeding the hub.

Without it a hub whose Home Assistant websocket is down (so no door or motion
changes reach the vault) looks healthy: its heartbeats keep arriving.
"""

import importlib
import json
import types

import pytest


@pytest.fixture
def mc():
    return importlib.import_module("mqtt_client")


def _client(mc, monkeypatch, tmp_path, listener):
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    monkeypatch.setattr(mc, "_log", lambda m, file=None: None)
    c = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker"})
    c._ha_ws_listener = listener
    sent = []
    c._publish = lambda topic, payload, qos=0, persist=None: sent.append(json.loads(payload))
    c._publish_reading = lambda kind, topic, payload, ts, legacy_qos=0: sent.append(dict(payload))
    c._resolve_ha_version = lambda: None
    return c, sent


@pytest.mark.parametrize("with_outbox", [False, True])
def test_a_connected_listener_is_reported(mc, monkeypatch, tmp_path, with_outbox):
    listener = types.SimpleNamespace(is_connected=lambda: True, last_event_at="2026-10-11T07:00:00Z")
    c, sent = _client(mc, monkeypatch, tmp_path, listener)
    monkeypatch.setattr(c, "outbox_stats", lambda: {"backlog": 0, "bytes": 0, "oldest_event_ts": None,
                                                     "last_acked_seq": 0, "dropped_total": 0}
                        if with_outbox else None)
    c.publish_telemetry()
    assert sent[0]["ha_connected"] is True
    assert sent[0]["ha_last_event_at"] == "2026-10-11T07:00:00Z"


def test_a_dropped_websocket_is_reported(mc, monkeypatch, tmp_path):
    listener = types.SimpleNamespace(is_connected=lambda: False, last_event_at="2026-10-11T06:00:00Z")
    c, sent = _client(mc, monkeypatch, tmp_path, listener)
    monkeypatch.setattr(c, "outbox_stats", lambda: None)
    c.publish_telemetry()
    assert sent[0]["ha_connected"] is False
    assert sent[0]["ha_last_event_at"] == "2026-10-11T06:00:00Z"  # when it last heard anything


def test_without_home_assistant_configured_the_hub_reports_null(mc, monkeypatch, tmp_path):
    c, sent = _client(mc, monkeypatch, tmp_path, None)
    monkeypatch.setattr(c, "outbox_stats", lambda: None)
    c.publish_telemetry()
    assert sent[0]["ha_connected"] is None and sent[0]["ha_last_event_at"] is None


def test_configured_but_no_listener_reports_false(mc, monkeypatch, tmp_path):
    c, sent = _client(mc, monkeypatch, tmp_path, None)
    monkeypatch.setattr(c, "_ha_configured", True)
    monkeypatch.setattr(c, "outbox_stats", lambda: None)
    c.publish_telemetry()
    assert sent[0]["ha_connected"] is False and sent[0]["ha_last_event_at"] is None


def test_a_broken_listener_does_not_stop_telemetry(mc, monkeypatch, tmp_path):
    def boom():
        raise RuntimeError("no")

    c, sent = _client(mc, monkeypatch, tmp_path, types.SimpleNamespace(is_connected=boom, last_event_at=12))
    monkeypatch.setattr(c, "outbox_stats", lambda: None)
    c.publish_telemetry()
    assert sent[0]["ha_connected"] is False and sent[0]["ha_last_event_at"] is None


def test_the_listener_records_when_home_assistant_last_sent_an_event(monkeypatch):
    import ha_client

    listener = ha_client.HAWebSocketListener("http://localhost:8123", "tok", on_event=lambda *a: None)
    assert listener.last_event_at is None
    messages = iter([
        json.dumps({"type": "auth_required"}),
        json.dumps({"type": "auth_ok"}),
        json.dumps({"type": "event", "id": 1, "event": {"a": {}}}),
    ])

    class WS:
        def send(self, data):
            pass

        def recv(self):
            try:
                return next(messages)
            except StopIteration:
                listener._stop.set()
                raise ConnectionError("closed")

        def close(self):
            pass

        def settimeout(self, t):
            pass

    monkeypatch.setattr(ha_client, "websocket", types.SimpleNamespace(create_connection=lambda url, timeout=None: WS()))
    monkeypatch.setattr(listener, "_log", lambda m: None)
    monkeypatch.setattr(ha_client.traceback, "print_exc", lambda *a, **k: None)
    listener._run()
    assert isinstance(listener.last_event_at, str) and listener.last_event_at.endswith("Z")


def test_rejected_unsafe_url_reports_false_not_null(mc, monkeypatch, tmp_path):
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    monkeypatch.setattr(mc, "_log", lambda m, file=None: None)
    monkeypatch.setattr(
        mc, "_ha_safety", lambda: types.SimpleNamespace(check_token_url=lambda url: (False, "not allowed"))
    )
    c = mc.CentralCoreClient(
        {"client_id": "demo-home-001", "mqtt_host": "broker",
         "ha_api_url": "http://ha.example:8123", "ha_api_token": "t"}
    )
    assert c.ha_api_url == "" and c.ha_api_token == ""  # rejected and wiped
    assert c._ha_status() == {"ha_connected": False, "ha_last_event_at": None, "ha_last_message_at": None}
