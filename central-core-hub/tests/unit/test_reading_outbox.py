"""Store and confirm: the hub keeps every reading until the vault confirms it stored it.

Covers the SQLite outbox (outbox.py) and how the client uses it: persistence
across a restart, acknowledgement deletes, resend order and rate, the age and
size caps, sequence numbers that never go back, and the event time (Home
Assistant's last_changed) travelling unchanged however late a reading is sent.
"""

import importlib
import json
import sys
import types

import pytest


@pytest.fixture
def ob():
    return importlib.import_module("outbox")


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def _open(ob, path, **kw):
    return ob.SqliteOutbox(path, **kw)


# ---------------------------------------------------------------------------
# The outbox on its own
# ---------------------------------------------------------------------------


def test_readings_survive_a_restart(ob, tmp_path):
    path = tmp_path / "outbox.db"
    box = _open(ob, path)
    box.append("sensors", "t/sensors", {"data": {"binary_sensor.door": "on"}}, "2026-10-02T10:00:00Z")
    box.append("system", "t/system", {"cpu_percent": 3}, "2026-10-02T10:00:30Z")
    outbox_id = box.outbox_id
    box.close()  # the add-on restarts (or the power goes)

    again = _open(ob, path)
    rows = again.due(10)
    assert [r["seq"] for r in rows] == [1, 2]
    assert rows[0]["payload"]["data"] == {"binary_sensor.door": "on"}
    assert again.outbox_id == outbox_id
    assert again.stats()["backlog"] == 2


def test_seq_never_goes_back_across_restarts_even_when_everything_was_acknowledged(ob, tmp_path):
    path = tmp_path / "outbox.db"
    box = _open(ob, path)
    seqs = [box.append("system", "t", {}, "2026-10-02T10:00:00Z")[0] for _ in range(3)]
    assert seqs == [1, 2, 3]
    box.ack(3)
    assert box.stats()["backlog"] == 0
    box.close()

    again = _open(ob, path)
    assert again.append("system", "t", {}, "2026-10-02T10:01:00Z")[0] == 4


def test_a_new_database_gets_a_new_outbox_id(ob, tmp_path):
    a = _open(ob, tmp_path / "a.db")
    b = _open(ob, tmp_path / "b.db")
    assert a.outbox_id != b.outbox_id
    assert a.outbox_id.startswith("ob-")


def test_ack_deletes_up_to_and_including_upto(ob, tmp_path):
    box = _open(ob, tmp_path / "o.db")
    for _ in range(5):
        box.append("system", "t", {}, "2026-10-02T10:00:00Z")
    assert box.ack(3) == 3
    assert [r["seq"] for r in box.due(10)] == [4, 5]
    assert box.stats()["last_acked_seq"] == 3
    assert box.oldest_seq() == 4
    # an older ack changes nothing and does not lower the high-water mark
    assert box.ack(2) == 0
    assert box.stats()["last_acked_seq"] == 3


def test_ack_for_another_outbox_is_ignored(ob, tmp_path):
    box = _open(ob, tmp_path / "o.db")
    box.append("system", "t", {}, "2026-10-02T10:00:00Z")
    assert box.ack(1, outbox_id="ob-someone-else") == 0
    assert box.stats()["backlog"] == 1
    assert box.ack(1, outbox_id=box.outbox_id) == 1


def test_bad_ack_values_delete_nothing(ob, tmp_path):
    box = _open(ob, tmp_path / "o.db")
    box.append("system", "t", {}, "2026-10-02T10:00:00Z")
    assert box.ack("lots") == 0
    assert box.ack(None) == 0
    assert box.stats()["backlog"] == 1


def test_event_ts_is_stored_in_utc_and_queue_time_is_separate(ob, tmp_path):
    clock = Clock()
    box = _open(ob, tmp_path / "o.db", clock=clock)
    seq, stored = box.append("sensors", "t", {"data": {"x": "on"}}, "2026-10-25T01:30:00.250000+01:00")
    assert stored["event_ts"] == "2026-10-25T00:30:00.250000Z"
    assert stored["seq"] == seq and stored["outbox_id"] == box.outbox_id
    row = box.due(1)[0]
    assert row["event_ts"] == "2026-10-25T00:30:00.250000Z"
    assert row["queued_at"] == ob.utc_iso(clock.t)
    assert row["queued_at"] != row["event_ts"]


def test_due_is_oldest_first_and_skips_recently_sent(ob, tmp_path):
    clock = Clock()
    box = _open(ob, tmp_path / "o.db", clock=clock)
    for i in range(5):
        box.append("system", "t", {"i": i}, "2026-10-02T10:00:00Z")
    first = box.due(2)
    assert [r["seq"] for r in first] == [1, 2]
    box.mark_sent([1, 2])
    assert [r["seq"] for r in box.due(10, sent_before=clock.t - 300)] == [3, 4, 5]
    clock.t += 301  # no ack for five minutes: due again
    assert [r["seq"] for r in box.due(10, sent_before=clock.t - 300)] == [1, 2, 3, 4, 5]


def test_mark_unsent_makes_everything_due_again(ob, tmp_path):
    box = _open(ob, tmp_path / "o.db")
    for _ in range(3):
        box.append("system", "t", {}, "2026-10-02T10:00:00Z")
    box.mark_sent([1, 2, 3])
    assert box.due(10) == []
    box.mark_unsent()
    assert [r["seq"] for r in box.due(10)] == [1, 2, 3]


def test_age_cap_drops_the_oldest_and_logs_it(ob, tmp_path):
    clock = Clock()
    logs = []
    box = _open(ob, tmp_path / "o.db", clock=clock, max_age_s=7 * 86400, log=logs.append)
    box.append("system", "t", {"n": 1}, "2026-09-20T10:00:00Z")
    box.append("system", "t", {"n": 2}, "2026-09-20T10:00:00Z")
    clock.t += 3 * 86400
    box.append("system", "t", {"n": 3}, "2026-09-23T10:00:00Z")
    clock.t += 4 * 86400 + 1  # the first two are now over 7 days old
    assert box.enforce_caps() == 2
    assert [r["seq"] for r in box.due(10)] == [3]
    assert box.stats()["dropped_total"] == 2
    assert any("older than 7 days" in m and "seq 1-2" in m for m in logs)


def test_size_cap_drops_the_oldest_and_keeps_the_newest(ob, tmp_path):
    logs = []
    box = _open(ob, tmp_path / "o.db", max_bytes=1000, log=logs.append)
    for i in range(10):
        box.append("sensors", "t", {"pad": "x" * 200, "i": i}, "2026-10-02T10:00:00Z")
    stats = box.stats()
    assert stats["bytes"] <= 1000
    kept = [r["seq"] for r in box.due(20)]
    assert kept and kept[-1] == 10 and kept == list(range(kept[0], 11))
    assert stats["dropped_total"] == 10 - len(kept)
    assert any("dropped the oldest" in m for m in logs)


def test_size_cap_never_lowers_the_next_seq(ob, tmp_path):
    box = _open(ob, tmp_path / "o.db", max_bytes=300)
    for _ in range(5):
        box.append("sensors", "t", {"pad": "x" * 200}, "2026-10-02T10:00:00Z")
    assert box.append("sensors", "t", {}, "2026-10-02T10:00:00Z")[0] == 6


def test_utc_iso_accepts_epochs_datetimes_and_offsets(ob):
    from datetime import datetime, timezone

    assert ob.utc_iso(0) == "1970-01-01T00:00:00Z"
    assert ob.utc_iso(datetime(2026, 1, 1, tzinfo=timezone.utc)) == "2026-01-01T00:00:00Z"
    assert ob.utc_iso("2026-06-01T12:00:00+02:00") == "2026-06-01T10:00:00Z"


# ---------------------------------------------------------------------------
# The client with an outbox
# ---------------------------------------------------------------------------


class FakePaho:
    def __init__(self, rc=0):
        self.published = []
        self.subscribed = []
        self.rc = rc

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": json.loads(payload), "qos": qos})
        return types.SimpleNamespace(rc=self.rc)

    def subscribe(self, topic, qos=0):
        self.subscribed.append((topic, qos))
        return (0, 1)


@pytest.fixture
def mc():
    return importlib.import_module("mqtt_client")


@pytest.fixture
def hub(mc, tmp_path, monkeypatch):
    """A client with an outbox in tmp_path, a fake broker, and one selected door."""
    monkeypatch.setenv("HUB_OUTBOX_DB", str(tmp_path / "outbox.db"))
    client = mc.CentralCoreClient({"client_id": "hub-ob", "mqtt_host": "broker"})
    client._client = FakePaho()
    client._connected = True
    client.selected_sensors = ["binary_sensor.front_door"]
    monkeypatch.setattr(mc, "is_entity_allowed", lambda _e: True)
    monkeypatch.setattr(mc, "_is_selectable_entity", lambda _e: True)
    monkeypatch.setattr(client, "privacy_filter", lambda states, wait=True: list(states or []))
    yield client
    client.close()


def _door(state, last_changed):
    return {"state": state, "last_changed": last_changed, "attributes": {"device_class": "door"}}


def test_without_an_outbox_the_hub_publishes_as_before(mc, monkeypatch):
    monkeypatch.setenv("HUB_OUTBOX_DB", "")
    client = mc.CentralCoreClient({"client_id": "hub-plain", "mqtt_host": "broker"})
    assert client._store is None
    sent = []
    monkeypatch.setattr(client, "_publish", lambda t, p, qos=0, persist=None: sent.append((t, qos)))
    client._publish_reading("sensors", "topic/x", {"a": 1}, "2026-10-02T10:00:00Z")
    assert sent == [("topic/x", 0)]


def test_the_default_location_is_used_only_inside_the_add_on(mc, monkeypatch):
    monkeypatch.delenv("HUB_OUTBOX_DB", raising=False)
    monkeypatch.setattr(mc, "OUTBOX_DB_DEFAULT", "/no-such-dir-for-tests/outbox.db")
    assert mc._open_reading_store() is None


def test_an_unopenable_outbox_falls_back_to_plain_publishing(mc, tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    monkeypatch.setenv("HUB_OUTBOX_DB", str(blocker / "outbox.db"))
    assert mc._open_reading_store() is None


def test_a_state_change_is_stored_then_sent_at_qos1_with_its_event_time(hub):
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T08:15:00.500000+01:00"))
    [msg] = hub._client.published
    assert msg["topic"] == hub.preferred_sensors_topic
    assert msg["qos"] == 1
    body = msg["payload"]
    assert body["seq"] == 1
    assert body["event_ts"] == "2026-10-02T07:15:00.500000Z"
    assert body["outbox_id"] == hub._store.outbox_id
    assert body["oldest_seq"] == 1
    assert body["hub_time"].endswith("Z")
    assert body["data"] == {"binary_sensor.front_door": "on"}
    # kept until the vault confirms it
    assert hub._store.stats()["backlog"] == 1


def test_a_state_change_while_offline_is_kept_and_not_sent(hub):
    hub._connected = False
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T07:15:00Z"))
    assert hub._client.published == []
    assert hub._store.stats()["backlog"] == 1


def test_store_ack_message_deletes_confirmed_readings(hub):
    for i, state in enumerate(["on", "off", "on"]):
        hub._on_ha_state_event("binary_sensor.front_door", _door(state, f"2026-10-02T07:15:0{i}Z"))
    msg = types.SimpleNamespace(topic=hub.store_ack_topic, payload=json.dumps({"upto": 2, "stored": 2}).encode())
    dispatched = []
    hub._submit = lambda fn, *a: dispatched.append(fn)
    hub.on_message(None, None, msg)
    assert dispatched == []  # never handled as a command
    assert [r["seq"] for r in hub._store.due(10, sent_before=float("inf"))] == [3]


@pytest.mark.parametrize("payload", [b"not json", b'{"upto": -1}', b'{"upto": "3"}', b'{"upto": true}', b"[]"])
def test_malformed_store_acks_delete_nothing(hub, payload):
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T07:15:00Z"))
    assert hub._handle_store_ack(payload) == 0
    assert hub._store.stats()["backlog"] == 1


def test_connect_subscribes_to_store_acks_and_queues_a_full_resend(hub):
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T07:15:00Z"))
    assert hub._store.due(10) == []  # sent live
    hub._submit = lambda fn, *a: None
    hub.on_connect(hub._client, None, None, 0)
    assert (hub.store_ack_topic, 1) in hub._client.subscribed
    assert [r["seq"] for r in hub._store.due(10)] == [1]


def test_nothing_is_resent_until_the_vault_has_acknowledged_once(hub):
    hub._connected = False
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T07:15:00Z"))
    hub._connected = True
    assert hub._send_due_readings() == 0  # an older vault: it would never confirm
    assert hub._handle_store_ack(b'{"upto": 0, "stored": 0}') == 0
    assert hub._store.vault_confirms()
    assert hub._send_due_readings() == 1


def test_catch_up_resends_oldest_first_in_rate_limited_batches_with_the_hub_clock(hub, mc):
    hub._store.ack(0)
    hub._connected = False
    times = [f"2026-10-02T0{h}:00:00Z" for h in range(1, 6)]
    for _ in range(9):  # 45 readings queued while offline
        for i, t in enumerate(times):
            hub._on_ha_state_event("binary_sensor.front_door", _door("on" if i % 2 else "off", t))
            hub._selected_sensor_cache.clear()
    assert hub._store.stats()["backlog"] == 45
    hub._connected = True

    sent = [hub._send_due_readings(now=1_000_000.0) for _ in range(4)]
    assert sent == [mc.CATCHUP_BATCH_SIZE, mc.CATCHUP_BATCH_SIZE, 5, 0]  # one batch per call (per second)
    batches = [m for m in hub._client.published if m["topic"] == hub.batch_topic]
    assert len(batches) == 3
    seqs = [r["seq"] for b in batches for r in b["payload"]["records"]]
    assert seqs == list(range(1, 46))
    first = batches[0]["payload"]
    assert first["hub_time"].endswith("Z")
    assert first["outbox_id"] == hub._store.outbox_id
    assert first["oldest_seq"] == 1
    rec = first["records"][0]
    assert rec["type"] == "sensors"
    # the event time travels unchanged, however late the reading is resent
    assert rec["event_ts"] == "2026-10-02T01:00:00Z" == rec["payload"]["event_ts"]
    assert rec["queued_at"] != rec["event_ts"]


def test_unconfirmed_readings_are_resent_after_five_minutes(hub, mc):
    hub._store.ack(0)  # the vault has confirmed this outbox before
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T07:15:00Z"))
    import time as _time

    now = _time.time()
    assert hub._send_due_readings(now=now) == 0  # just sent live
    assert hub._send_due_readings(now=now + mc.RESEND_AFTER_S + 1) == 1


def test_nothing_is_resent_while_disconnected(hub):
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T07:15:00Z"))
    hub._store.mark_unsent()
    hub._connected = False
    assert hub._send_due_readings() == 0


def test_a_failed_live_publish_is_left_for_the_resend(hub):
    hub._client.rc = 4
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T07:15:00Z"))
    assert [r["seq"] for r in hub._store.due(10)] == [1]


def test_status_telemetry_reports_the_backlog_and_goes_through_the_outbox(hub, mc, monkeypatch):
    hub._connected = False
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T07:15:00Z"))
    hub._connected = True
    monkeypatch.setattr(hub, "_resolve_ha_version", lambda: None)
    monkeypatch.setattr(mc, "get_addon_version", lambda: "2.3.0")
    hub.publish_telemetry()
    [msg] = [m for m in hub._client.published if m["topic"] == hub.telemetry_topic]
    assert msg["qos"] == 1
    assert msg["payload"]["outbox"]["backlog"] == 1  # the waiting door change (before this message)
    assert msg["payload"]["seq"] == 2
    assert msg["payload"]["event_ts"].endswith("Z")


def test_selected_state_snapshot_uses_the_latest_last_changed_as_its_event_time(hub):
    states = [
        {"entity_id": "binary_sensor.front_door", "state": "off", "last_changed": "2026-10-02T06:00:00+00:00",
         "attributes": {}},
    ]
    hub.selected_sensors = ["binary_sensor.front_door"]
    hub._publish_selected_states(states, wait=False)
    [msg] = hub._client.published
    assert msg["payload"]["event_ts"] == "2026-10-02T06:00:00Z"


def test_an_unusable_event_time_falls_back_to_the_queue_time(hub):
    hub._publish_reading("sensors", hub.preferred_sensors_topic, {"data": {}}, "not a time")
    [msg] = hub._client.published
    assert msg["payload"]["event_ts"].endswith("Z")


def test_latest_time_picks_the_latest_and_skips_garbage(mc):
    assert mc._latest_time(["2026-01-01T00:00:00Z", "junk", None, "2026-01-01T01:00:00+02:00"], "d") == (
        "2026-01-01T00:00:00Z"
    )
    assert mc._latest_time([], "default") == "default"


def _real_shared_schemas(monkeypatch):
    """The installed central_core_mqtt_shared.schemas, loaded by path (the test
    conftest replaces the package in sys.modules with a small shim)."""
    import importlib.util
    from importlib.machinery import PathFinder
    from pathlib import Path

    spec = PathFinder.find_spec("central_core_mqtt_shared")
    for location in (spec.submodule_search_locations or []) if spec else []:
        path = Path(location) / "schemas.py"
        if path.exists():
            file_spec = importlib.util.spec_from_file_location("_cc_shared_schemas_real", str(path))
            assert file_spec is not None and file_spec.loader is not None
            module = importlib.util.module_from_spec(file_spec)
            # pydantic resolves the models' annotations through sys.modules
            monkeypatch.setitem(sys.modules, file_spec.name, module)
            file_spec.loader.exec_module(module)
            return module
    pytest.skip("real central_core_mqtt_shared not importable here")


def test_batches_match_the_shared_protocol_when_it_is_installed(hub, monkeypatch):
    hub._store.ack(0)  # the vault has confirmed this outbox before
    schemas = _real_shared_schemas(monkeypatch)
    if not hasattr(schemas, "TelemetryBatch"):
        pytest.skip("installed central-core-mqtt-shared predates protocol 1.1")
    hub._connected = False
    hub._on_ha_state_event("binary_sensor.front_door", _door("on", "2026-10-02T07:15:00Z"))
    hub._connected = True
    hub._send_due_readings()
    batch = [m for m in hub._client.published if m["topic"] == hub.batch_topic][0]["payload"]
    parsed = schemas.TelemetryBatch.model_validate(batch)
    assert parsed.records[0].event_ts == "2026-10-02T07:15:00Z"
    live = hub._store.due(1, sent_before=float("inf"))[0]["payload"]
    assert schemas.OutboxFields.model_validate(live).seq == 1
    assert schemas.StoreAck.model_validate({"upto": 1, "stored": 1}).upto == 1


def test_topics_for_store_and_confirm(hub):
    assert hub.store_ack_topic == "hubs/hub-ob/v1/ack"
    assert hub.batch_topic == "hubs/hub-ob/v1/telemetry/batch"
