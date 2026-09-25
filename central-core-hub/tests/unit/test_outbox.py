"""Perf #8: the persistent outbox appends instead of rewriting, is capped in
bytes and items, keeps only ACKs and change messages, and is flushed from the
main loop rather than paho's network thread."""

import importlib
import json
import types

import pytest


@pytest.fixture
def mc():
    return importlib.import_module("mqtt_client")


def _entries(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_append_does_not_rewrite_the_file(mc, tmp_path):
    path = tmp_path / "outbox.jsonl"
    box = mc.PersistentOutbox(path, max_items=100, max_bytes=1_000_000)
    assert box.append("hubs/h/v1/ack/a/1", "{}", 1)
    inode = path.stat().st_ino
    assert box.append("hubs/h/v1/ack/a/2", "{}", 1)
    assert path.stat().st_ino == inode  # same file, appended (a rewrite replaces it)
    assert [e["topic"] for e in _entries(path)] == ["hubs/h/v1/ack/a/1", "hubs/h/v1/ack/a/2"]


def test_item_cap_keeps_the_newest(mc, tmp_path):
    path = tmp_path / "outbox.jsonl"
    box = mc.PersistentOutbox(path, max_items=5, max_bytes=1_000_000)
    for i in range(12):
        box.append("t", str(i), 0)
    got = [e["payload"] for e in _entries(path)]
    assert len(got) <= 5
    assert got[-1] == "11"
    assert got == sorted(got, key=int)


def test_byte_cap(mc, tmp_path):
    path = tmp_path / "outbox.jsonl"
    box = mc.PersistentOutbox(path, max_items=10_000, max_bytes=4_000)
    for i in range(100):
        box.append("t", f"{i:04d}" + "x" * 100, 0)
    assert path.stat().st_size <= 4_000
    assert _entries(path)[-1]["payload"].startswith("0099")


def test_a_single_oversized_message_is_not_stored(mc, tmp_path):
    path = tmp_path / "outbox.jsonl"
    box = mc.PersistentOutbox(path, max_items=10, max_bytes=1_000)
    assert box.append("t", "x" * 5_000, 0) is False
    assert not path.exists() or _entries(path) == []


def test_flush_sends_in_order_and_keeps_failures(mc, tmp_path):
    path = tmp_path / "outbox.jsonl"
    box = mc.PersistentOutbox(path, max_items=10, max_bytes=100_000)
    for i in range(4):
        box.append("t", str(i), 1)
    sent = []
    assert box.flush_with_sender(lambda t, p, q: sent.append(p) or p != "2") == 3
    assert sent == ["0", "1", "2", "3"]
    assert [e["payload"] for e in _entries(path)] == ["2"]
    box.append("t", "4", 1)
    assert [e["payload"] for e in _entries(path)] == ["2", "4"]


def test_sensor_dumps_are_not_persisted(mc, monkeypatch, tmp_path):
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    c = mc.CentralCoreClient({"client_id": "hub1", "mqtt_host": "localhost"})
    queued = []
    c._outbox = types.SimpleNamespace(append=lambda t, p, q: queued.append(t) or True)
    c._connected = False

    class _Paho:
        def publish(self, *a, **k):
            return types.SimpleNamespace(rc=4)  # MQTT_ERR_NO_CONN

    monkeypatch.setattr(mc, "mqtt", types.SimpleNamespace(Client=_Paho))
    c._client = _Paho()
    c._publish("hubs/hub1/v1/telemetry/sensors", "{}", persist=False)
    c._publish("hubs/hub1/v1/ack/sensors.set/x", "{}", qos=1)
    c._publish("hubs/hub1/v1/telemetry/sensors", '{"data": {}}')
    assert queued == ["hubs/hub1/v1/ack/sensors.set/x", "hubs/hub1/v1/telemetry/sensors"]


def test_outbox_is_flushed_by_the_main_loop_not_on_connect(mc, monkeypatch, tmp_path):
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    c = mc.CentralCoreClient({"client_id": "hub1", "mqtt_host": "localhost"})
    flushes = []
    c._outbox = types.SimpleNamespace(flush_with_sender=lambda fn: flushes.append(1) or 0, has_entries=lambda: True)
    monkeypatch.setattr(c, "publish_sensors_with_default_filter", lambda: None)
    fake = types.SimpleNamespace(subscribe=lambda *a, **k: (0, 1))
    c.on_connect(fake, None, None, 0)
    assert flushes == []
    for name in ("publish_telemetry", "publish_selected_sensor_changes", "publish_sensors"):
        monkeypatch.setattr(c, name, lambda: None)
    c.run_iteration()
    assert flushes == [1]
