"""The system telemetry payload is checked against the shared MQTT schema.

Before, the hub sent cpu_percent where central-core-mqtt-shared wants cpu and
ram, so the shared SystemTelemetry model could never accept it.
"""

import importlib
import importlib.util
import json
import sys
import types
from importlib.machinery import PathFinder
from pathlib import Path

import pytest


@pytest.fixture
def schemas(monkeypatch):
    """The REAL shared schemas (the conftest swaps the package for a stand-in)."""
    spec = PathFinder.find_spec("central_core_mqtt_shared")
    assert spec is not None, "central_core_mqtt_shared is not installed: pip install -r requirements.txt"
    path = Path(list(spec.submodule_search_locations)[0]) / "schemas.py"
    name = "real_central_core_schemas"
    mod_spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(mod_spec)
    monkeypatch.setitem(sys.modules, name, module)
    mod_spec.loader.exec_module(module)
    return module


@pytest.fixture
def mc():
    return importlib.import_module("mqtt_client")


def _built(**kw):
    import telemetry

    args = dict(
        get_cpu_percent=lambda: 12.5,
        uptime_fn=lambda: 3600,
        loadavg_fn=lambda: [0.1, 0.2, 0.3],
        mem_info_fn=lambda: (1000, 250),
        mem_avail_fn=lambda: None,
        disk_info_fn=lambda: (5000, 4000),
        version="2.4.2",
        telemetry_interval=30,
    )
    args.update(kw)
    return json.loads(telemetry.build_telemetry("demo-home-001", **args))


def test_the_system_payload_has_the_shared_schema_fields(schemas):
    data = _built()
    assert data["cpu"] == 12.5
    assert data["ram"] == 75.0  # used share of memory
    assert data["uptime"] == 3600
    schemas.SystemTelemetry(**data)  # validates; raises on a mismatch
    # the vault still reads the older names
    assert data["cpu_percent"] == 12.5 and data["mem_free_kb"] == 250


def test_ram_counts_reclaimable_memory_as_free():
    data = _built(mem_info_fn=lambda: (1000, 50), mem_avail_fn=lambda: 600)
    assert data["ram"] == 40.0
    assert data["mem_free_kb"] == 50  # the older field keeps its meaning


def test_a_nan_cpu_is_left_out(monkeypatch):
    import telemetry

    monkeypatch.setattr(telemetry, "_get_cpu_percent", lambda: None)
    data = _built(get_cpu_percent=lambda: float("nan"))
    assert "cpu" not in data


def test_unknown_readings_are_left_out_not_made_up(monkeypatch):
    import telemetry

    monkeypatch.setattr(telemetry, "_get_cpu_percent", lambda: None)  # no fallback to the real machine
    data = _built(get_cpu_percent=lambda: None, uptime_fn=lambda: None, mem_info_fn=lambda: (None, None))
    assert "cpu" not in data and "ram" not in data


def test_out_of_range_readings_are_clamped(schemas):
    data = _built(get_cpu_percent=lambda: 250.0, mem_info_fn=lambda: (1000, -5))
    assert data["cpu"] == 100.0 and data["ram"] == 100.0
    schemas.SystemTelemetry(**data)


def test_the_timestamp_is_utc_iso(schemas):
    data = _built()
    assert data["timestamp"].endswith("Z")
    assert schemas.to_utc_iso(data["timestamp"]) == data["timestamp"]


def _client(mc, monkeypatch, tmp_path, listener):
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    monkeypatch.setattr(mc, "_log", lambda m, file=None: None)
    c = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker"})
    c._ha_ws_listener = listener
    sent = []
    c._publish = lambda topic, payload, qos=0, persist=None: sent.append(json.loads(payload))
    c._publish_reading = lambda kind, topic, payload, ts, legacy_qos=0: sent.append(dict(payload))
    c._resolve_ha_version = lambda: None
    import helpers

    monkeypatch.setattr(helpers, "get_cpu_percent", lambda: 10.0)
    monkeypatch.setattr(helpers, "mem_info_kb", lambda: (1000, 500))
    monkeypatch.setattr(helpers, "mem_available_kb", lambda: None)
    monkeypatch.setattr(helpers, "uptime_seconds", lambda: 99)
    monkeypatch.setattr(c, "outbox_stats", lambda: None)
    return c, sent


def test_the_published_payload_validates_with_the_liveness_fields(mc, monkeypatch, tmp_path, schemas):
    listener = types.SimpleNamespace(
        is_connected=lambda: True,
        last_event_at="2026-10-11T07:00:00Z",
        last_message_at="2026-10-11T08:30:00Z",
    )
    c, sent = _client(mc, monkeypatch, tmp_path, listener)
    c.publish_telemetry()
    model = schemas.SystemTelemetry(**sent[0])
    assert model.ha_connected is True
    assert model.ha_last_message_at == "2026-10-11T08:30:00Z"
    assert model.ha_last_event_at == "2026-10-11T07:00:00Z"


def test_a_disconnected_listener_keeps_the_last_message_time(mc, monkeypatch, tmp_path):
    listener = types.SimpleNamespace(
        is_connected=lambda: False, last_event_at=None, last_message_at="2026-10-11T08:30:00Z"
    )
    c, sent = _client(mc, monkeypatch, tmp_path, listener)
    c.publish_telemetry()
    assert sent[0]["ha_connected"] is False
    assert sent[0]["ha_last_message_at"] == "2026-10-11T08:30:00Z"


def test_not_configured_or_unheard_is_null(mc, monkeypatch, tmp_path):
    c, sent = _client(mc, monkeypatch, tmp_path, None)
    c.publish_telemetry()
    assert sent[0]["ha_connected"] is None and sent[0]["ha_last_message_at"] is None
    c2, sent2 = _client(mc, monkeypatch, tmp_path, types.SimpleNamespace(is_connected=lambda: True))
    c2.publish_telemetry()  # a listener that has heard nothing yet
    assert sent2[0]["ha_last_message_at"] is None


def _run_listener(monkeypatch, messages):
    import ha_client

    listener = ha_client.HAWebSocketListener("http://localhost:8123", "tok", on_event=lambda *a: None)
    assert listener.last_message_at is None
    msgs = iter(messages)

    class WS:
        def send(self, data):
            pass

        def recv(self):
            try:
                return next(msgs)
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
    return listener


def test_a_pong_alone_moves_the_last_message_time_but_not_the_last_event(monkeypatch):
    listener = _run_listener(monkeypatch, [
        json.dumps({"type": "auth_required"}),
        json.dumps({"type": "auth_ok"}),
        json.dumps({"type": "pong", "id": 3}),
    ])
    assert listener.last_message_at.endswith("Z")
    assert listener.last_event_at is None


def test_garbage_does_not_count_as_a_message(monkeypatch):
    listener = _run_listener(monkeypatch, [
        json.dumps({"type": "auth_required"}),
        json.dumps({"type": "auth_ok"}),
        "not json",
    ])
    assert listener.last_message_at is None


def test_mem_available_is_read_from_proc_meminfo(monkeypatch, tmp_path):
    import builtins

    import helpers

    f = tmp_path / "meminfo"
    f.write_text("MemTotal:  1000 kB\nMemFree: 50 kB\nMemAvailable:  600 kB\n")
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda p, *a, **k: real_open(f if p == "/proc/meminfo" else p, *a, **k))
    assert helpers.mem_available_kb() == 600
    f.write_text("MemTotal: 1000 kB\n")
    assert helpers.mem_available_kb() is None
    monkeypatch.undo()
