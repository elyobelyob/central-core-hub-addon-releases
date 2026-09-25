"""Perf #9: one paho network loop, paho's own reconnect backoff, and a Last Will.

- loop_start() is called once; after that paho reconnects by itself
  (reconnect_delay_set(1, 120)), so the main loop no longer calls connect()
  again (which fought paho's reconnect);
- the Last Will is {"status": "offline", "timestamp": <float>} on
  hubs/<id>/v1/status/offline, which the vault subscribes to (QoS 1) and
  handles as the hub going offline (shared schema StatusOffline).
"""

import importlib
import json
import types

import pytest

import mqtt_runtime


class _Paho:
    def __init__(self, *a, **k):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def record(*a, **k):
            self.calls.append((name, a, k))
            return 0

        return record


def _ctx():
    return types.SimpleNamespace(
        client_id="hub1",
        mqtt_username="",
        mqtt_password="",
        mqtt_tls=False,
        status_offline_topic="hubs/hub1/v1/status/offline",
        on_connect=None,
        on_disconnect=None,
        on_message=None,
    )


def test_last_will_and_backoff_are_configured():
    ctx = _ctx()
    mqtt_runtime.setup_mqtt_client(ctx, types.SimpleNamespace(Client=_Paho))
    calls = {name: (a, k) for name, a, k in ctx._client.calls}
    a, k = calls["will_set"]
    topic = a[0] if a else k["topic"]
    assert topic == "hubs/hub1/v1/status/offline"
    payload = json.loads(k.get("payload") if "payload" in k else a[1])
    assert payload["status"] == "offline"
    assert isinstance(payload["timestamp"], float)
    assert k.get("qos", a[2] if len(a) > 2 else None) == 1
    assert k.get("retain", False) is False
    a, k = calls["reconnect_delay_set"]
    assert (k.get("min_delay", a[0] if a else None), k.get("max_delay", a[1] if len(a) > 1 else None)) == (1, 120)


@pytest.fixture
def client(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    c = mc.CentralCoreClient({"client_id": "hub1", "mqtt_host": "broker"})
    c._client = _Paho()
    return c


def test_status_offline_topic(client):
    assert client.status_offline_topic == "hubs/hub1/v1/status/offline"


def test_loop_is_started_once(client):
    assert client.connect_once() is True
    assert client.connect_once() is True
    names = [n for n, _, _ in client._client.calls]
    assert names.count("loop_start") == 1
    assert names.count("connect") == 1


def test_main_loop_leaves_reconnecting_to_paho(client, monkeypatch):
    client.connect_once()
    client._connected = False
    called = []
    monkeypatch.setattr(client, "connect", lambda: called.append(1) or True)
    for name in ("publish_telemetry", "publish_selected_sensor_changes", "publish_sensors"):
        monkeypatch.setattr(client, name, lambda: None)
    client.run_iteration()
    assert called == []


def test_main_loop_still_makes_the_first_connection(client, monkeypatch):
    called = []
    monkeypatch.setattr(client, "connect", lambda: called.append(1) or True)
    for name in ("publish_telemetry", "publish_selected_sensor_changes", "publish_sensors"):
        monkeypatch.setattr(client, name, lambda: None)
    client.run_iteration()
    assert called == [1]


def test_initial_connect_retries_back_off(client, monkeypatch):
    waits = []
    attempts = iter([False, False, False, False, True])
    monkeypatch.setattr(client, "connect_once", lambda: next(attempts))
    monkeypatch.setattr(client, "wait_for_connected", lambda timeout=5: True)
    monkeypatch.setattr(client._stop_event, "wait", lambda timeout=None: waits.append(timeout))
    assert client.connect() is True
    assert len(waits) == 4
    assert waits == sorted(waits) and waits[-1] > waits[0]
    assert max(waits) <= 120
