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


def test_an_ack_racing_a_send_is_refused_but_does_not_start_a_new_outbox(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 3)
    box.append("system", "t", {}, "2026-10-02T10:00:10Z")  # seq 4 numbered, not yet marked sent
    with pytest.raises(ob.AckBeyondSent) as err:
        box.ack(4, box.outbox_id)
    assert err.value.outbox_behind is False


def test_an_ack_past_every_numbered_seq_says_the_outbox_is_behind(ob, tmp_path):
    box = _sent_box(ob, tmp_path / "o.db", 3)
    with pytest.raises(ob.AckBeyondSent) as err:
        box.ack(10, box.outbox_id)
    assert err.value.outbox_behind is True
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


def test_rotation_happens_at_most_once_an_hour(ob, tmp_path):
    clock = Clock()
    box = _sent_box(ob, tmp_path / "o.db", 2, clock=clock)
    first = box.rotate_outbox_id()
    assert first is not None
    clock.t += 3599
    assert box.rotate_outbox_id() is None
    assert box.outbox_id == first[1]
    clock.t += 2
    assert box.rotate_outbox_id() is not None
    assert box.stats()["rotations_total"] == 2


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
    hub._store.append("sensors", hub.preferred_sensors_topic, {"data": {}}, "2026-10-02T07:00:01Z")  # seq 2
    before = hub._store.outbox_id
    _ack(hub, 2, before)  # the vault answers before seq 2 is marked sent
    assert hub._store.outbox_id == before
    _ack(hub, 1, before)
    assert hub._store.stats()["backlog"] == 1
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
