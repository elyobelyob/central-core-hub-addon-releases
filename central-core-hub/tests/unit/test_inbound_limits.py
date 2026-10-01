"""Inbound MQTT is bounded: a flood of commands cannot grow memory without limit.

on_message drops payloads over 64 KB before they are queued, and the queue to
the worker holds at most WORK_QUEUE_MAX jobs; beyond that messages are dropped
and logged (rate-limited), never blocking paho's network thread.
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
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    c = mc.CentralCoreClient({"client_id": "hub1", "mqtt_host": "localhost"})
    c.start_worker()
    yield c, mc, lines
    c.stop_worker()


def _msg(body):
    payload = body if isinstance(body, bytes) else json.dumps(body).encode()
    return types.SimpleNamespace(topic="hubs/hub1/v1/cmd/sensors/poll", payload=payload, retain=False)


def test_oversized_message_is_dropped_before_queueing(client, monkeypatch):
    c, mc, lines = client
    handled = []
    monkeypatch.setattr(importlib.import_module("handlers"), "handle_message", lambda *a, **k: handled.append(1))

    c.on_message(None, None, _msg(b"x" * (mc.MAX_INBOUND_BYTES + 1)))
    assert c._work_queue.qsize() == 0
    assert c.wait_for_commands(timeout=5)
    assert handled == []
    assert any("over" in m and "dropped" in m for m in lines)


def test_message_at_the_limit_is_queued(client, monkeypatch):
    c, mc, lines = client
    handled = []
    monkeypatch.setattr(importlib.import_module("handlers"), "handle_message", lambda *a, **k: handled.append(1))
    c.on_message(None, None, _msg(b"x" * mc.MAX_INBOUND_BYTES))
    assert c.wait_for_commands(timeout=5)
    assert handled == [1]


def test_queue_is_bounded_and_drops_are_logged_once_per_interval(client, monkeypatch):
    c, mc, lines = client
    release = threading.Event()
    started = threading.Event()

    def blocking(*a, **k):
        started.set()
        release.wait(5)

    monkeypatch.setattr(importlib.import_module("handlers"), "handle_message", blocking)
    c.on_message(None, None, _msg({"command_id": "first"}))
    assert started.wait(5)  # worker busy with the first job
    for i in range(mc.WORK_QUEUE_MAX + 50):
        c.on_message(None, None, _msg({"command_id": f"c{i}"}))
    assert c._work_queue.qsize() == mc.WORK_QUEUE_MAX
    drops = [m for m in lines if "work queue full" in m]
    assert len(drops) == 1  # rate-limited
    assert c._drops == 50
    release.set()
    assert c.wait_for_commands(timeout=10)


def test_submit_reports_whether_the_job_was_queued(client):
    c, mc, lines = client
    release = threading.Event()
    c._submit(lambda: release.wait(5))
    results = [c._submit(lambda: None) for _ in range(mc.WORK_QUEUE_MAX + 1)]
    assert results.count(False) >= 1
    release.set()
    assert c.wait_for_commands(timeout=10)


def test_startup_warns_when_mqtt_tls_is_off(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    mc.CentralCoreClient({"client_id": "hub1", "mqtt_host": "vault.example", "mqtt_port": 1883})
    warning = [m for m in lines if "mqtt_tls is off" in m]
    assert len(warning) == 1 and "vault.example:1883" in warning[0] and "unencrypted" in warning[0]


def test_no_tls_warning_when_tls_is_on(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    monkeypatch.setattr(mc.CentralCoreClient, "_setup_cert_files", lambda self: None)
    mc.CentralCoreClient({"client_id": "hub1", "mqtt_host": "vault.example", "mqtt_port": 8883, "mqtt_tls": True})
    assert not any("mqtt_tls is off" in m for m in lines)
