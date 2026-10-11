"""Restoring a Home Assistant backup brings back an old outbox.

The restored /data/outbox.db has the same outbox_id and lower seqs than the
vault has already stored under that id, so the vault would drop every new
reading as a duplicate until the seqs passed the old high point (silently: no
night-door alerts meanwhile). The vault's acknowledgement then reaches past
anything the outbox has ever numbered; the hub answers by starting a new outbox
id and resending what it holds under it. Nothing is deleted, and a forged
acknowledgement can do this at most once an hour.
"""

import importlib
import json
import shutil
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


def _sent_box(ob, path, n, clock=None):
    box = ob.SqliteOutbox(path, clock=clock or Clock())
    for i in range(n):
        box.append("sensors", "t/sensors", {"data": {"binary_sensor.door": "on" if i % 2 else "off"}},
                   f"2026-10-02T10:00:0{i % 10}Z")
    box.mark_sent(list(range(1, n + 1)))
    return box


# --------------------------------------------------------------------------- outbox


def test_an_ack_racing_a_send_is_believed(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 3)
    box.append("system", "t", {}, "2026-10-02T10:00:10Z")  # seq 4
    box.begin_send([4])  # published, mark_sent not yet run
    assert box.ack(4, box.outbox_id) == 4  # the vault really has it
    assert box.mark_sent([4]) is True  # and the late mark_sent is harmless


def test_an_ack_covering_readings_that_were_never_sent_says_the_outbox_is_behind(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 3)
    box.append("system", "t", {}, "2026-10-02T10:00:10Z")  # seq 4, never sent
    box.append("system", "t", {}, "2026-10-02T10:00:11Z")  # seq 5, being sent
    box.begin_send([5])
    with pytest.raises(ob.AckBeyondSent) as err:
        box.ack(5, box.outbox_id)
    assert err.value.outbox_behind is True and err.value.unambiguous is False
    assert "seq 4-4" in str(err.value)
    assert box.stats()["backlog"] == 5


def test_a_failed_publish_is_not_in_flight(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 1)
    box.append("system", "t", {}, "2026-10-02T10:00:10Z")
    box.begin_send([2])
    box.end_send([2])
    with pytest.raises(ob.AckBeyondSent):
        box.ack(2, box.outbox_id)


def test_an_ack_past_every_numbered_seq_says_the_outbox_is_behind(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 3)
    with pytest.raises(ob.AckBeyondSent) as err:
        box.ack(10, box.outbox_id)
    assert err.value.outbox_behind is True and err.value.unambiguous is True
    assert isinstance(err.value, ob.AckRefused)


def test_rotation_keeps_and_rekeys_every_reading(ob, tmp_path):
    path = tmp_path / "o.db"
    box = _sent_box(ob, path, 3)
    box.append("system", "t/system", {"cpu": 1}, "2026-10-02T10:00:20Z")  # seq 4, never sent
    old_id = box.outbox_id
    old, new = box.rotate_outbox_id()
    assert old == old_id and new != old_id and new.startswith("ob-")
    assert box.outbox_id == new
    rows = box.due(10)  # all due again, oldest first
    assert [r["seq"] for r in rows] == [1, 2, 3, 4]
    assert all(r["payload"]["outbox_id"] == new for r in rows)
    stats = box.stats()
    assert stats["backlog"] == 4 and stats["last_acked_seq"] == 0 and stats["rotations_total"] == 1
    assert stats["next_seq"] == 5  # seq never goes back
    assert box.highest_sent_seq() == 0  # nothing has been sent under the new id yet
    box.close()
    again = ob.SqliteOutbox(path)
    assert again.outbox_id == new  # kept across a restart
    assert again.append("system", "t", {}, "2026-10-02T10:01:00Z")[1]["outbox_id"] == new


def test_after_rotation_the_old_id_is_refused_and_the_new_one_works(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 3)
    old, new = box.rotate_outbox_id()
    with pytest.raises(ob.AckRefused, match="another outbox"):
        box.ack(3, old)
    with pytest.raises(ob.AckBeyondSent):
        box.ack(1, new)  # not resent under the new id yet
    box.mark_sent([1, 2])
    assert box.ack(2, new) == 2
    assert [r["seq"] for r in box.due(10)] == [3]


def test_rotation_on_ambiguous_evidence_happens_at_most_once_an_hour(ob, tmp_path):
    mono = Clock(500.0)
    box = ob.SqliteOutbox(tmp_path / "o.db", monotonic=mono)
    first = box.rotate_outbox_id()
    assert first is not None
    mono.t += 3599
    assert box.rotate_outbox_id() is None
    assert box.outbox_id == first[1]
    mono.t += 2
    assert box.rotate_outbox_id() is not None
    assert box.stats()["rotations_total"] == 2


def test_clear_evidence_may_rotate_again_after_a_minute(ob, tmp_path):
    mono = Clock(500.0)
    box = ob.SqliteOutbox(tmp_path / "o.db", monotonic=mono)
    assert box.rotate_outbox_id() is not None
    mono.t += 59
    assert box.rotate_outbox_id(unambiguous=True) is None
    mono.t += 2
    assert box.rotate_outbox_id(unambiguous=True) is not None
    assert box.rotate_outbox_id() is None  # ambiguous evidence still waits an hour


def test_a_wall_clock_jump_cannot_block_rotation(ob, tmp_path):
    clock, mono = Clock(4_000_000_000.0), Clock(500.0)  # booted with the clock far ahead
    box = ob.SqliteOutbox(tmp_path / "o.db", clock=clock, monotonic=mono)
    assert box.rotate_outbox_id() is not None
    clock.t = 1_800_000_000.0  # NTP corrects it
    mono.t += 3601
    assert box.rotate_outbox_id() is not None


def test_a_failed_rotation_changes_nothing(ob, tmp_path, monkeypatch):
    box = _sent_box(ob, tmp_path / "o.db", 2)
    before = box.outbox_id

    def boom(*_a, **_k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(box, "_set_meta", boom)
    with pytest.raises(RuntimeError):
        box.rotate_outbox_id()
    monkeypatch.undo()
    assert box.outbox_id == before
    assert box.rotate_outbox_id() is None  # the failed attempt counts: not retried on every ack
    assert box.highest_sent_seq() == 2
    assert all(r["payload"]["outbox_id"] == before for r in box.due(10, sent_before=float("inf")))


def test_unreadable_payloads_survive_rotation(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 1)
    box._db.execute("UPDATE outbox SET payload = 'not json' WHERE seq = 1")
    box.rotate_outbox_id()
    assert box.stats()["backlog"] == 1


# --------------------------------------------------------------------------- the hub


@pytest.fixture
def mc():
    return importlib.import_module("mqtt_client")


class FakePaho:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": json.loads(payload), "qos": qos})
        return types.SimpleNamespace(rc=0)

    def subscribe(self, topic, qos=0):
        return (0, 1)


def _hub(mc, monkeypatch, db):
    monkeypatch.setenv("HUB_OUTBOX_DB", str(db))
    client = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker"})
    client._client = FakePaho()
    client._connected = True
    client.selected_sensors = ["binary_sensor.front_door"]
    monkeypatch.setattr(mc, "is_entity_allowed", lambda _e: True)
    monkeypatch.setattr(mc, "_is_selectable_entity", lambda _e: True)
    monkeypatch.setattr(client, "privacy_filter", lambda states, wait=True: list(states or []))
    return client


def _door(hub, state, ts):
    hub._on_ha_state_event("binary_sensor.front_door",
                           {"state": state, "last_changed": ts, "attributes": {"device_class": "door"}})


def _ack(hub, upto, outbox_id):
    msg = types.SimpleNamespace(topic=hub.store_ack_topic, retain=False,
                                payload=json.dumps({"upto": upto, "stored": 1, "outbox_id": outbox_id}).encode())
    hub.on_message(None, None, msg)


def test_a_restored_backup_gets_a_new_outbox_id_and_resends_under_it(mc, monkeypatch, tmp_path):
    db = tmp_path / "outbox.db"
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))

    hub = _hub(mc, monkeypatch, db)
    _door(hub, "on", "2026-10-02T07:00:00Z")
    _door(hub, "off", "2026-10-02T07:01:00Z")
    original_id = hub._store.outbox_id
    _ack(hub, 2, original_id)  # the vault stored seqs 1-2
    hub._store.close()
    shutil.copy(db, tmp_path / "backup.db")  # the backup is taken here

    hub = _hub(mc, monkeypatch, db)
    for i in range(3, 9):  # seqs 3-8 reach the vault after the backup
        _door(hub, "on" if i % 2 else "off", f"2026-10-02T07:0{i}:00Z")
    _ack(hub, 8, original_id)
    hub._store.close()

    shutil.copy(tmp_path / "backup.db", db)  # Home Assistant restores the backup
    hub = _hub(mc, monkeypatch, db)
    assert hub._store.outbox_id == original_id
    _door(hub, "on", "2026-10-02T09:00:00Z")  # numbered seq 3 again: the vault has a seq 3 already
    assert hub._client.published[-1]["payload"]["seq"] == 3
    lines.clear()
    _ack(hub, 8, original_id)  # the vault answers from its own (later) view of this outbox

    new_id = hub._store.outbox_id
    assert new_id != original_id
    warnings = [m for m in lines if m.startswith("WARNING") and "backup is restored" in m]
    assert len(warnings) == 1 and original_id in warnings[0] and new_id in warnings[0]
    assert hub._store.stats()["backlog"] == 1  # nothing deleted
    hub._client.published.clear()
    assert hub._send_due_readings() == 1
    [batch] = hub._client.published
    assert batch["topic"] == hub.batch_topic
    assert batch["payload"]["outbox_id"] == new_id
    assert batch["payload"]["records"][0]["seq"] == 3
    assert batch["payload"]["records"][0]["payload"]["outbox_id"] == new_id
    # the vault stores it under the new id and confirms it
    _ack(hub, 3, new_id)
    assert hub._store.stats()["backlog"] == 0
    # a late acknowledgement for the old id changes nothing and starts nothing new
    _door(hub, "off", "2026-10-02T09:01:00Z")
    _ack(hub, 8, original_id)
    assert hub._store.outbox_id == new_id and hub._store.stats()["backlog"] == 1
    hub.close()


def test_a_forged_ack_cannot_lose_readings_or_rotate_repeatedly(mc, monkeypatch, tmp_path):
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    hub._connected = False
    for i in range(3):
        _door(hub, "on" if i % 2 else "off", f"2026-10-02T07:0{i}:00Z")  # kept, never sent
    hub._connected = True
    first_id = hub._store.outbox_id
    _ack(hub, 10**9, first_id)  # forged, using the id seen on the broker
    second_id = hub._store.outbox_id
    assert second_id != first_id
    _ack(hub, 10**9, second_id)  # and again with the new id: within the hour, refused only
    assert hub._store.outbox_id == second_id
    assert hub._store.stats()["backlog"] == 3  # every reading is still here
    assert len([m for m in lines if "backup is restored" in m]) == 1
    hub.close()


def test_an_ack_racing_a_live_send_does_not_rotate(mc, monkeypatch, tmp_path):
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    _door(hub, "on", "2026-10-02T07:00:00Z")  # seq 1 sent
    before = hub._store.outbox_id
    real_publish = hub._client.publish

    def publish_then_ack(topic, payload, qos=0):
        result = real_publish(topic, payload, qos)
        _ack(hub, json.loads(payload)["seq"], before)  # the vault answers before mark_sent runs
        return result

    hub._client.publish = publish_then_ack
    _door(hub, "off", "2026-10-02T07:00:01Z")  # seq 2
    assert hub._store.outbox_id == before
    assert hub._store.stats()["backlog"] == 0  # both confirmed, nothing resent
    hub.close()


def test_a_reading_sent_just_before_a_new_id_is_not_marked_sent_under_it(mc, monkeypatch, tmp_path):
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    real_publish = hub._client.publish

    def publish_then_rotate(topic, payload, qos=0):
        result = real_publish(topic, payload, qos)
        hub._store.rotate_outbox_id()  # a restore was detected meanwhile
        return result

    hub._client.publish = publish_then_rotate
    _door(hub, "on", "2026-10-02T07:00:00Z")
    assert hub._store.highest_sent_seq() == 0  # sent under the old id only
    assert [r["seq"] for r in hub._store.due(10)] == [1]  # so it is due under the new one
    hub.close()


def test_the_new_id_is_started_on_the_worker_thread(mc, monkeypatch, tmp_path):
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    _door(hub, "on", "2026-10-02T07:00:00Z")
    queued = []
    hub._submit = lambda fn, *args: queued.append((fn, args)) or True
    before = hub._store.outbox_id
    _ack(hub, 50, before)
    assert hub._store.outbox_id == before  # not on paho's network thread
    [(fn, args)] = queued
    assert fn == hub._start_new_outbox
    fn(*args)
    assert hub._store.outbox_id != before
    hub.close()


def test_a_recent_backup_past_the_vault_mark_is_caught_before_unsent_rows_go(mc, monkeypatch, tmp_path):
    """The other restore shape: the restored outbox has already numbered past
    the vault's high mark, so the vault's ack is not past every numbered seq,
    but it covers readings this outbox never sent. Those must not be deleted."""
    db = tmp_path / "outbox.db"
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    hub = _hub(mc, monkeypatch, db)
    for i in range(1, 11):  # seqs 1-10 sent and confirmed
        _door(hub, "on" if i % 2 else "off", f"2026-10-02T07:{i:02d}:00Z")
    original_id = hub._store.outbox_id
    _ack(hub, 10, original_id)
    hub._connected = False
    for i in range(11, 16):  # seqs 11-15 queued while offline: in the backup, never sent
        _door(hub, "on" if i % 2 else "off", f"2026-10-02T08:{i:02d}:00Z")
    hub._store.close()
    shutil.copy(db, tmp_path / "backup.db")

    hub = _hub(mc, monkeypatch, db)  # the old timeline goes on: 11-15 are sent and stored
    assert hub._send_due_readings() == 5
    _ack(hub, 15, original_id)
    assert hub._store.stats()["backlog"] == 0 and hub._store.outbox_id == original_id
    hub._store.close()
    shutil.copy(tmp_path / "backup.db", db)  # restore

    hub = _hub(mc, monkeypatch, db)
    _door(hub, "on", "2026-10-02T09:00:00Z")  # seq 16 sent live
    lines.clear()
    _ack(hub, 15, original_id)  # the vault's view: 1-15 stored
    assert hub._store.stats()["backlog"] == 6  # 11-15 never sent from this outbox: kept, and 16
    assert hub._store.outbox_id != original_id
    assert len([m for m in lines if "backup is restored" in m]) == 1
    assert [r["seq"] for r in hub._store.due(10)] == [11, 12, 13, 14, 15, 16]
    hub.close()


def test_without_a_rotating_store_the_hub_only_refuses(mc, monkeypatch, tmp_path):
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    hub._store.close()
    hub._store = types.SimpleNamespace(
        ack=lambda upto, outbox_id: (_ for _ in ()).throw(importlib.import_module("outbox").AckBeyondSent("x", True))
    )
    assert hub._handle_store_ack(b'{"upto": 5, "outbox_id": "ob-x"}') == 0
    assert hub._start_new_outbox(5, "x") is None


def test_a_rotation_error_is_logged_not_raised(mc, monkeypatch, tmp_path):
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    monkeypatch.setattr(hub._store, "rotate_outbox_id", lambda: (_ for _ in ()).throw(RuntimeError("disk")))
    assert hub._start_new_outbox(5, "x") is None
    assert any("could not start a new outbox id" in m for m in lines)
    hub.close()
