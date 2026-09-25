"""Perf #6: paho's network thread never waits on Home Assistant.

on_message and on_connect run on paho's network thread. Handlers that call
Home Assistant (sensors/poll, sensors/set, the on-connect sensor publish)
used to run there, stalling keepalives. Once the worker is started (run()
starts it) that work goes to a single worker thread, in arrival order.
"""

import importlib
import json
import threading
import types

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    c = mc.CentralCoreClient({"client_id": "hub1", "mqtt_host": "localhost"})
    c.start_worker()
    yield c, mc
    c.stop_worker()


def _msg(action, body):
    return types.SimpleNamespace(topic=f"hubs/hub1/v1/cmd/{action}", payload=json.dumps(body).encode(), retain=False)


def test_on_message_returns_before_the_handler_finishes(client, monkeypatch):
    c, mc = client
    release = threading.Event()
    handled = []
    threads = []

    def slow_handler(*args, **kwargs):
        threads.append(threading.current_thread().name)
        release.wait(5)
        handled.append(args[1].topic)

    handlers = importlib.import_module("handlers")
    monkeypatch.setattr(handlers, "handle_message", slow_handler)

    c.on_message(None, None, _msg("sensors/poll", {"command_id": "a"}))
    c.on_message(None, None, _msg("sensors/set", {"command_id": "b"}))
    assert handled == []  # both queued, network thread free
    release.set()
    assert c.wait_for_commands(timeout=5)
    assert handled == ["hubs/hub1/v1/cmd/sensors/poll", "hubs/hub1/v1/cmd/sensors/set"]
    assert threads and all(name == "hub-worker" for name in threads)


def test_on_connect_does_not_call_home_assistant_inline(client, monkeypatch):
    c, mc = client
    release = threading.Event()
    calls = []

    def slow_publish():
        release.wait(5)
        calls.append("published")

    monkeypatch.setattr(c, "publish_sensors_with_default_filter", slow_publish)
    fake = types.SimpleNamespace(subscribe=lambda *a, **k: (0, 1), publish=lambda *a, **k: types.SimpleNamespace(rc=0))
    c.on_connect(fake, None, None, 0)
    assert c._connected is True
    assert calls == []
    release.set()
    assert c.wait_for_commands(timeout=5)
    assert calls == ["published"]


def test_without_worker_work_runs_inline(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    c = mc.CentralCoreClient({"client_id": "hub1"})
    ran = []
    c._submit(lambda: ran.append(threading.current_thread() is threading.main_thread()))
    assert ran == [True]


def test_a_failing_job_does_not_stop_the_worker(client):
    c, mc = client
    ran = []
    c._submit(lambda: 1 / 0)
    c._submit(lambda: ran.append(1))
    assert c.wait_for_commands(timeout=5)
    assert ran == [1]
