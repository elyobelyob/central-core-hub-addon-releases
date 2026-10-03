"""SqliteOutbox edge cases: failed writes leave the outbox as it was,
damaged rows and meta values do not stop a resend, and timestamps are UTC."""

import re
from datetime import datetime, timedelta, timezone

import pytest

import outbox as ob


class _Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def _box(tmp_path, **kw):
    return ob.SqliteOutbox(tmp_path / "outbox.db", clock=kw.pop("clock", _Clock()), **kw)


# --- utc_iso ----------------------------------------------------------------


def test_utc_iso_now_is_utc_with_z():
    before = datetime.now(timezone.utc) - timedelta(seconds=1)
    text = ob.utc_iso()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", text)
    assert datetime.fromisoformat(text.replace("Z", "+00:00")) >= before


def test_utc_iso_naive_datetime_is_local_time(monkeypatch):
    naive = datetime(2026, 7, 1, 12, 0, 0)
    expected = naive.astimezone().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    assert ob.utc_iso(naive) == expected


def test_utc_iso_converts_offsets_and_epochs():
    assert ob.utc_iso("2026-07-01T13:00:00+01:00") == "2026-07-01T12:00:00Z"
    assert ob.utc_iso(0) == "1970-01-01T00:00:00Z"


# --- failed writes roll back ------------------------------------------------


def test_append_of_unserialisable_payload_stores_nothing_and_keeps_seq(tmp_path):
    box = _box(tmp_path)
    with pytest.raises(TypeError):
        box.append("state", "t", {"bad": object()}, 0)
    assert box.stats()["backlog"] == 0
    seq, _ = box.append("state", "t", {"ok": 1}, 0)
    assert seq == 1  # the failed append did not use up a sequence number


def test_failed_ack_leaves_readings_in_place(tmp_path, monkeypatch):
    box = _box(tmp_path)
    box.append("state", "t", {"a": 1}, 0)

    def boom(*_a, **_k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(box, "_set_meta", boom)
    with pytest.raises(RuntimeError):
        box.ack(1)
    monkeypatch.undo()
    assert box.stats()["backlog"] == 1  # delete rolled back with the meta write
    assert box.vault_confirms() is False
    assert box.ack(1) == 1  # and the outbox still works afterwards


def test_failed_cap_enforcement_rolls_back(tmp_path, monkeypatch):
    clock = _Clock()
    box = _box(tmp_path, clock=clock, max_age_s=10)
    box.append("state", "t", {"a": 1}, 0)
    clock.t += 100

    def boom(*_a, **_k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(box, "_set_meta", boom)
    with pytest.raises(RuntimeError):
        box.enforce_caps()
    monkeypatch.undo()
    assert box.stats()["backlog"] == 1
    assert box.enforce_caps() == 1
    assert box.stats()["dropped_total"] == 1


def test_init_rolls_back_when_meta_cannot_be_written(tmp_path, monkeypatch):
    def boom(self, *_a, **_k):
        raise RuntimeError("read-only")

    monkeypatch.setattr(ob.SqliteOutbox, "_set_meta", boom)
    with pytest.raises(RuntimeError):
        ob.SqliteOutbox(tmp_path / "outbox.db")
    monkeypatch.undo()
    box = ob.SqliteOutbox(tmp_path / "outbox.db")  # the half-made database is usable
    assert box.outbox_id.startswith("ob-")
    assert box.stats()["next_seq"] == 1


# --- damaged data -----------------------------------------------------------


def test_damaged_next_seq_falls_back_to_one(tmp_path):
    box = _box(tmp_path)
    box._db.execute("UPDATE meta SET value = 'garbage' WHERE key = 'next_seq'")
    assert box.stats()["next_seq"] == 1
    seq, stored = box.append("state", "t", {"a": 1}, 0)
    assert seq == 1 and stored["seq"] == 1


def test_damaged_payload_is_resent_with_empty_body(tmp_path):
    box = _box(tmp_path)
    box.append("state", "t", {"a": 1}, 0)
    box._db.execute("UPDATE outbox SET payload = '{not json'")
    [row] = box.due(10)
    assert row["seq"] == 1 and row["payload"] == {}


def test_mark_sent_with_no_seqs_changes_nothing(tmp_path):
    box = _box(tmp_path)
    box.append("state", "t", {"a": 1}, 0)
    box.mark_sent([])
    assert [r["seq"] for r in box.due(10)] == [1]


def test_close_is_safe_to_call_twice_and_on_a_broken_connection(tmp_path, monkeypatch):
    box = _box(tmp_path)
    box.close()
    box.close()

    class _Broken:
        def close(self):
            raise RuntimeError("already gone")

    monkeypatch.setattr(box, "_db", _Broken())
    box.close()  # must not raise during shutdown
