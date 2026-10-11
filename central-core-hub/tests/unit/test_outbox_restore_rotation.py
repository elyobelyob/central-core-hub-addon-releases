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


def test_every_start_gets_a_new_outbox_id_and_resends_what_it_kept(mc, monkeypatch, tmp_path):
    db = tmp_path / "outbox.db"
    hub = _hub(mc, monkeypatch, db)
    first = hub._store.outbox_id
    _ack(hub, 0, first)  # this vault confirms outboxes
    hub._connected = False
    _door(hub, "on", "2026-10-02T07:00:00Z")  # kept, not yet confirmed
    hub._store.close()
    hub = _hub(mc, monkeypatch, db)
    second = hub._store.outbox_id
    assert second != first
    assert hub._store.stats()["next_seq"] == 2  # seq keeps counting up
    assert hub._send_due_readings() == 1
    [batch] = hub._client.published
    assert batch["payload"]["outbox_id"] == second
    assert batch["payload"]["records"][0]["payload"]["outbox_id"] == second
    _ack(hub, 1, second)
    assert hub._store.stats()["backlog"] == 0
    assert hub._store.stats()["rotations_total"] == 0  # a start is not a detection
    hub.close()


def test_a_restored_backup_starts_under_a_new_id(mc, monkeypatch, tmp_path):
    """A backup taken with readings still waiting, restored after the vault has
    stored later seqs under the old ids: the restart gives it a new id, so the
    vault stores the readings it sends from here instead of taking them for
    duplicates."""
    db = tmp_path / "outbox.db"
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))

    hub = _hub(mc, monkeypatch, db)
    _door(hub, "on", "2026-10-02T07:00:00Z")
    _door(hub, "off", "2026-10-02T07:01:00Z")
    _ack(hub, 1, hub._store.outbox_id)  # seq 2 still waiting
    before = {hub._store.outbox_id}
    hub._store.close()
    shutil.copy(db, tmp_path / "backup.db")  # the backup is taken here

    hub = _hub(mc, monkeypatch, db)  # after the backup the hub goes on
    before.add(hub._store.outbox_id)
    assert hub._send_due_readings() == 1
    for i in range(3, 9):
        _door(hub, "on" if i % 2 else "off", f"2026-10-02T07:0{i}:00Z")
    _ack(hub, 8, hub._store.outbox_id)
    hub._store.close()

    shutil.copy(tmp_path / "backup.db", db)  # Home Assistant restores the backup
    hub = _hub(mc, monkeypatch, db)
    restored_id = hub._store.outbox_id
    assert restored_id not in before
    assert hub._store.stats()["backlog"] == 1  # seq 2 from the backup, due again
    _door(hub, "on", "2026-10-02T09:00:00Z")  # numbered seq 3 again, but under a new id
    assert hub._client.published[-1]["payload"]["outbox_id"] == restored_id
    for old_id in before:  # late acknowledgements for the old ids change nothing
        _ack(hub, 8, old_id)
    assert hub._store.outbox_id == restored_id and hub._store.stats()["backlog"] == 2
    assert not [m for m in lines if "backup is restored" in m]  # nothing for the backstop to do
    hub.close()


def test_a_restored_backup_with_nothing_waiting_starts_under_a_new_id(mc, monkeypatch, tmp_path):
    """The case the in-run check cannot see: the backup's outbox was empty, so
    no acknowledgement ever covers anything unsent."""
    db = tmp_path / "outbox.db"
    hub = _hub(mc, monkeypatch, db)
    for i in range(1, 11):
        _door(hub, "on" if i % 2 else "off", f"2026-10-02T07:{i:02d}:00Z")
    _ack(hub, 10, hub._store.outbox_id)
    assert hub._store.stats()["backlog"] == 0
    hub._store.close()
    shutil.copy(db, tmp_path / "backup.db")

    hub = _hub(mc, monkeypatch, db)
    later_id = hub._store.outbox_id
    for i in range(11, 16):
        _door(hub, "on" if i % 2 else "off", f"2026-10-02T08:{i:02d}:00Z")
    _ack(hub, 15, later_id)  # the vault has 11-15 under later_id
    hub._store.close()

    shutil.copy(tmp_path / "backup.db", db)
    hub = _hub(mc, monkeypatch, db)
    _door(hub, "on", "2026-10-02T09:00:00Z")  # seq 11 again
    sent = hub._client.published[-1]["payload"]
    assert sent["seq"] == 11 and sent["outbox_id"] not in (later_id,)
    hub.close()


def test_in_a_run_an_ack_covering_unsent_readings_starts_a_new_id(mc, monkeypatch, tmp_path):
    """The backstop: within one run, the vault confirming readings this outbox
    never sent means it is ahead of it. The readings are kept and resent."""
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    for i in range(1, 11):
        _door(hub, "on" if i % 2 else "off", f"2026-10-02T07:{i:02d}:00Z")
    current = hub._store.outbox_id
    _ack(hub, 10, current)
    hub._connected = False
    for i in range(11, 16):  # queued while offline: never sent
        _door(hub, "on" if i % 2 else "off", f"2026-10-02T08:{i:02d}:00Z")
    hub._connected = True
    _door(hub, "off", "2026-10-02T09:00:00Z")  # seq 16 sent live
    _ack(hub, 15, current)
    assert hub._store.stats()["backlog"] == 6  # 11-15 kept, and 16
    assert hub._store.outbox_id != current
    assert len([m for m in lines if "backup is restored" in m]) == 1
    assert [r["seq"] for r in hub._store.due(10)] == [11, 12, 13, 14, 15, 16]
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

    def boom(**_kw):
        raise RuntimeError("disk")

    monkeypatch.setattr(hub._store, "rotate_outbox_id", boom)
    assert hub._start_new_outbox(5, "x", hub._store.outbox_id) is None
    assert any("could not start a new outbox id" in m for m in lines)
    hub.close()


def test_a_rotation_for_an_id_that_has_moved_on_does_nothing(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 2)
    old = box.outbox_id
    box.start_new_id()
    current = box.outbox_id
    assert box.rotate_outbox_id(expected_id=old) is None
    assert box.outbox_id == current
    assert box.rotate_outbox_id(expected_id=current) is not None


def test_a_start_does_not_use_up_the_rate_limit(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 2)
    box.start_new_id()
    assert box.rotation_allowed() and box.rotation_allowed(unambiguous=True)
    assert box.rotate_outbox_id() is not None
    assert not box.rotation_allowed() and not box.rotation_allowed(unambiguous=True)
    assert box.stats()["rotations_total"] == 1


def test_a_flood_of_acks_queues_one_rotation(mc, monkeypatch, tmp_path):
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    _door(hub, "on", "2026-10-02T07:00:00Z")
    queued = []
    hub._submit = lambda fn, *args: queued.append((fn, args)) or True
    current = hub._store.outbox_id
    for _ in range(50):
        _ack(hub, 10**6, current)
    assert len(queued) == 1  # one queued, the rest dropped
    fn, args = queued[0]
    fn(*args)  # runs: a new id
    assert hub._store.outbox_id != current
    for _ in range(50):
        _ack(hub, 10**6, hub._store.outbox_id)
    assert len(queued) == 1  # rate-limited now: nothing queued at all
    hub.close()


def test_a_full_work_queue_does_not_block_later_requests(mc, monkeypatch, tmp_path):
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    _door(hub, "on", "2026-10-02T07:00:00Z")
    hub._submit = lambda fn, *args: False  # queue full
    current = hub._store.outbox_id
    _ack(hub, 10**6, current)
    assert hub._new_outbox_queued is False
    hub._submit = lambda fn, *args: fn(*args) or True
    _ack(hub, 10**6, current)
    assert hub._store.outbox_id != current
    hub.close()


def test_a_batch_queued_by_paho_while_disconnected_counts_as_sent(mc, monkeypatch, tmp_path):
    hub = _hub(mc, monkeypatch, tmp_path / "outbox.db")
    _ack(hub, 0, hub._store.outbox_id)
    hub._connected = False
    _door(hub, "on", "2026-10-02T07:00:00Z")
    hub._connected = True
    hub._client.publish = lambda topic, payload, qos=0: types.SimpleNamespace(rc=4)  # MQTT_ERR_NO_CONN
    assert hub._send_due_readings() == 1
    assert hub._store.highest_sent_seq() == 1
    hub._client.publish = lambda topic, payload, qos=0: types.SimpleNamespace(rc=1)
    _door(hub, "off", "2026-10-02T07:00:01Z")  # live: failed, left for the resend
    assert hub._store.highest_sent_seq() == 1
    hub.close()


# --------------------------------------------------------------------------- a start that cannot re-key


def test_a_failed_new_id_at_start_keeps_the_outbox_under_its_old_id(mc, monkeypatch, tmp_path):
    ob = importlib.import_module("outbox")
    db = tmp_path / "outbox.db"
    hub = _hub(mc, monkeypatch, db)
    hub._connected = False
    _door(hub, "on", "2026-10-02T07:00:00Z")  # one reading waiting
    kept_id = hub._store.outbox_id
    hub._store.close()

    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))

    def disk_full(self):
        raise OSError("disk full")

    monkeypatch.setattr(ob.SqliteOutbox, "start_new_id", disk_full)
    hub = _hub(mc, monkeypatch, db)
    assert hub._store is not None  # not switched off
    assert hub._store.outbox_id == kept_id
    assert hub._store.stats()["backlog"] == 1  # the waiting reading is still there
    assert any(m.startswith("WARNING: could not start a new outbox id") and kept_id in m for m in lines)
    _door(hub, "off", "2026-10-02T07:01:00Z")  # and it keeps working
    assert hub._client.published[-1]["payload"]["outbox_id"] == kept_id
    assert hub._store.stats()["backlog"] == 2
    hub.close()


def test_a_failure_that_leaves_a_transaction_open_is_cleaned_up_by_reopening(mc, monkeypatch, tmp_path):
    ob = importlib.import_module("outbox")
    db = tmp_path / "outbox.db"
    ob.SqliteOutbox(db).close()

    def fail_mid_transaction(self):
        self._db.execute("BEGIN IMMEDIATE")  # left open, as a failed ROLLBACK would
        raise OSError("I/O error")

    monkeypatch.setattr(ob.SqliteOutbox, "start_new_id", fail_mid_transaction)
    monkeypatch.setattr(mc, "_log", lambda m, file=None: None)
    hub = _hub(mc, monkeypatch, db)
    assert hub._store is not None
    hub._store.append("system", "t", {}, "2026-10-02T07:00:00Z")  # writes are not blocked
    assert hub._store.stats()["backlog"] == 1
    hub.close()


def test_if_the_outbox_cannot_even_reopen_the_hub_publishes_without_it(mc, monkeypatch, tmp_path):
    ob = importlib.import_module("outbox")
    real_init = ob.SqliteOutbox.__init__
    opened = []

    def init_once(self, *a, **k):
        if opened:
            raise OSError("gone")
        opened.append(1)
        real_init(self, *a, **k)

    def fail(self):
        raise OSError("disk full")

    monkeypatch.setattr(ob.SqliteOutbox, "__init__", init_once)
    monkeypatch.setattr(ob.SqliteOutbox, "start_new_id", fail)
    monkeypatch.setattr(mc, "_log", lambda m, file=None: None)
    monkeypatch.setenv("HUB_OUTBOX_DB", str(tmp_path / "outbox.db"))
    assert mc._open_reading_store() is None


# --------------------------------------------------------------------------- end to end


def test_a_reading_paho_queued_before_a_restart_is_resent_under_the_new_id(mc, monkeypatch, tmp_path):
    """MQTT_ERR_NO_CONN marks a reading sent (paho queued it). If the add-on
    restarts before paho delivers it, paho's queue is gone: the reading must be
    resent from the outbox under the new id."""
    db = tmp_path / "outbox.db"
    hub = _hub(mc, monkeypatch, db)
    first = hub._store.outbox_id
    _ack(hub, 0, first)  # this vault confirms outboxes
    hub._client.publish = lambda topic, payload, qos=0: types.SimpleNamespace(rc=4)  # queued by paho
    _door(hub, "on", "2026-10-02T07:00:00Z")
    assert hub._store.highest_sent_seq() == 1 and hub._store.due(10) == []
    hub._store.close()  # the add-on restarts; paho's queue is lost

    hub = _hub(mc, monkeypatch, db)
    second = hub._store.outbox_id
    assert second != first
    assert hub._send_due_readings() == 1
    [batch] = [m for m in hub._client.published if m["topic"] == hub.batch_topic]
    assert batch["payload"]["outbox_id"] == second
    assert [r["seq"] for r in batch["payload"]["records"]] == [1]
    assert batch["payload"]["records"][0]["payload"]["outbox_id"] == second
    _ack(hub, 1, second)
    assert hub._store.stats()["backlog"] == 0
    hub.close()
