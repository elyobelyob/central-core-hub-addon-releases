"""On-disk outbox: every reading stays on the hub until the vault confirms it stored it.

Store and confirm (central-core-mqtt-shared protocol 1.1):

1. Each telemetry or state-change message is written here first, in one
   SQLite transaction, with the next sequence number (`seq`), the time the
   reading happened (`event_ts`, Home Assistant's `last_changed` in UTC) and
   the time the hub queued it (`queued_at`). Then it is sent at QoS 1.
2. The vault publishes `hubs/<id>/v1/ack {"upto": N}` once it has committed
   everything up to N; `ack()` deletes those rows.
3. On (re)connect everything still here is resent, oldest first, in batches
   (`due()` / `mark_sent()`); the caller rate-limits.

`seq` never goes backwards for one outbox: the next number is kept in the
database, so it survives restarts and power cuts (synchronous=FULL), and
deleting rows never lowers it. A new database (reinstall, deleted /data) gets
a new random `outbox_id`, which the vault keys its dedupe on together with
`seq`, so numbers starting again from 1 are not mistaken for duplicates.

The outbox is capped by age (default 7 days) and size (default 50 MB of
payload); beyond either cap the oldest readings are dropped and the drop is
logged and counted (`dropped_total`).
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

DEFAULT_MAX_AGE_S = 7 * 24 * 3600
DEFAULT_MAX_BYTES = 50 * 1024 * 1024

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outbox (
    seq INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    topic TEXT NOT NULL,
    event_ts TEXT NOT NULL,
    queued_at TEXT NOT NULL,
    queued_epoch REAL NOT NULL,
    payload TEXT NOT NULL,
    size INTEGER NOT NULL,
    sent_count INTEGER NOT NULL DEFAULT 0,
    last_sent REAL
);
"""


def utc_iso(value: Any = None) -> str:
    """UTC ISO 8601 ending in "Z" for a datetime, an epoch number or an ISO
    string with an offset (None: now). A string without an offset is local
    time, with that date's rules."""
    if value is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), timezone.utc)
    elif isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class SqliteOutbox:
    """The hub's outbox. Thread-safe: paho's thread acknowledges, the
    websocket thread appends, the sender thread resends."""

    def __init__(
        self,
        path,
        max_age_s: float = DEFAULT_MAX_AGE_S,
        max_bytes: int = DEFAULT_MAX_BYTES,
        log: Optional[Callable[[str], None]] = None,
        clock: Callable[[], float] = time.time,
    ):
        self.path = Path(path)
        self.max_age_s = float(max_age_s)
        self.max_bytes = int(max_bytes)
        self._log = log or (lambda _msg: None)
        self._clock = clock
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        # A reading is only "stored" once it is on disk: survive a power cut.
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(_SCHEMA)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                if self._meta("outbox_id") is None:
                    self._set_meta("outbox_id", "ob-" + secrets.token_hex(8))
                if self._meta("next_seq") is None:
                    self._set_meta("next_seq", "1")
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------------ meta

    def _meta(self, key):
        row = self._db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else row[0]

    def _set_meta(self, key, value):
        self._db.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def _meta_int(self, key, default=0):
        value = self._meta(key)
        try:
            return int(value) if value is not None else default
        except ValueError:
            return default

    @property
    def outbox_id(self) -> str:
        with self._lock:
            return str(self._meta("outbox_id"))

    # ---------------------------------------------------------------- writes

    def append(self, record_type: str, topic: str, payload: dict, event_ts: Any) -> tuple[int, dict]:
        """Store one reading and return (seq, payload as stored).

        The stored payload is `payload` plus `seq`, `event_ts` (UTC) and
        `outbox_id`. Caps are applied after the write, so the new reading
        itself is never the one dropped (unless it alone is over the size cap).
        """
        now = self._clock()
        event = utc_iso(event_ts)
        queued = utc_iso(now)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                seq = self._meta_int("next_seq", 1)
                stored = dict(payload)
                stored.update({"seq": seq, "event_ts": event, "outbox_id": self._meta("outbox_id")})
                text = json.dumps(stored, separators=(",", ":"))
                self._db.execute(
                    "INSERT INTO outbox (seq, type, topic, event_ts, queued_at, queued_epoch, payload, size) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (seq, record_type, topic, event, queued, now, text, len(text.encode("utf-8"))),
                )
                self._set_meta("next_seq", seq + 1)
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        self.enforce_caps(now)
        return seq, stored

    def ack(self, upto: int, outbox_id: Optional[str] = None) -> int:
        """Delete every reading up to and including `upto`; returns how many.

        An acknowledgement naming another outbox (the vault answering for a
        database this hub no longer has) is ignored.
        """
        try:
            upto = int(upto)
        except (TypeError, ValueError):
            return 0
        with self._lock:
            if outbox_id is not None and str(outbox_id) != self._meta("outbox_id"):
                return 0
            self._db.execute("BEGIN IMMEDIATE")
            try:
                cur = self._db.execute("DELETE FROM outbox WHERE seq <= ?", (upto,))
                if upto > self._meta_int("last_acked_seq", 0):
                    self._set_meta("last_acked_seq", upto)
                self._set_meta("last_ack_epoch", self._clock())
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
            return cur.rowcount or 0

    def mark_sent(self, seqs, when: Optional[float] = None) -> None:
        seqs = [int(s) for s in seqs]
        if not seqs:
            return
        when = self._clock() if when is None else when
        with self._lock:
            self._db.executemany(
                "UPDATE outbox SET sent_count = sent_count + 1, last_sent = ? WHERE seq = ?",
                [(when, s) for s in seqs],
            )

    def mark_unsent(self) -> None:
        """Make every reading due again (after a reconnect: resend them all)."""
        with self._lock:
            self._db.execute("UPDATE outbox SET last_sent = NULL")

    def enforce_caps(self, now: Optional[float] = None) -> int:
        """Drop the oldest readings beyond the age and size caps; returns how many."""
        now = self._clock() if now is None else now
        dropped = 0
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                old = self._db.execute(
                    "SELECT COUNT(*), MIN(seq), MAX(seq) FROM outbox WHERE queued_epoch < ?",
                    (now - self.max_age_s,),
                ).fetchone()
                if old[0]:
                    self._db.execute("DELETE FROM outbox WHERE queued_epoch < ?", (now - self.max_age_s,))
                    dropped += old[0]
                    self._log(
                        f"Outbox: dropped {old[0]} readings older than {self.max_age_s / 86400:g} days "
                        f"(seq {old[1]}-{old[2]}) that the vault never confirmed"
                    )
                total = self._db.execute("SELECT COALESCE(SUM(size), 0) FROM outbox").fetchone()[0]
                if total > self.max_bytes:
                    over = total - self.max_bytes
                    cut, freed, count, first = None, 0, 0, None
                    for seq, size in self._db.execute("SELECT seq, size FROM outbox ORDER BY seq"):
                        first = seq if first is None else first
                        freed += size
                        count += 1
                        cut = seq
                        if freed >= over:
                            break
                    if cut is not None:
                        self._db.execute("DELETE FROM outbox WHERE seq <= ?", (cut,))
                        dropped += count
                        self._log(
                            f"Outbox: over {self.max_bytes // (1024 * 1024)} MB; dropped the oldest {count} "
                            f"readings (seq {first}-{cut}) that the vault never confirmed"
                        )
                if dropped:
                    self._set_meta("dropped_total", self._meta_int("dropped_total", 0) + dropped)
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        return dropped

    # ----------------------------------------------------------------- reads

    def due(self, limit: int, sent_before: Optional[float] = None) -> list[dict]:
        """Up to `limit` readings to (re)send, oldest first: never sent since
        `mark_unsent()`, or last sent before `sent_before`."""
        with self._lock:
            if sent_before is None:
                rows = self._db.execute(
                    "SELECT seq, type, topic, event_ts, queued_at, payload FROM outbox "
                    "WHERE last_sent IS NULL ORDER BY seq LIMIT ?",
                    (int(limit),),
                ).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT seq, type, topic, event_ts, queued_at, payload FROM outbox "
                    "WHERE last_sent IS NULL OR last_sent < ? ORDER BY seq LIMIT ?",
                    (sent_before, int(limit)),
                ).fetchall()
        out = []
        for seq, rtype, topic, event_ts, queued_at, payload in rows:
            try:
                body = json.loads(payload)
            except ValueError:
                body = {}
            out.append({"seq": seq, "type": rtype, "topic": topic, "event_ts": event_ts,
                        "queued_at": queued_at, "payload": body})
        return out

    def vault_confirms(self) -> bool:
        """Whether a vault has ever acknowledged this outbox. Until one has (a
        vault older than protocol 1.1 never will), resending would only repeat
        readings nobody confirms, so the hub just keeps them (within the caps)."""
        with self._lock:
            return self._meta("last_ack_epoch") is not None

    def oldest_seq(self) -> Optional[int]:
        with self._lock:
            row = self._db.execute("SELECT MIN(seq) FROM outbox").fetchone()
        return row[0] if row and row[0] is not None else None

    def stats(self) -> dict:
        """Backlog figures for the hub's status telemetry."""
        with self._lock:
            count, size, oldest_event, oldest_queued = self._db.execute(
                "SELECT COUNT(*), COALESCE(SUM(size), 0), MIN(event_ts), MIN(queued_at) FROM outbox"
            ).fetchone()
            return {
                "backlog": count,
                "bytes": size,
                "oldest_event_ts": oldest_event,
                "oldest_queued_at": oldest_queued,
                "last_acked_seq": self._meta_int("last_acked_seq", 0),
                "next_seq": self._meta_int("next_seq", 1),
                "dropped_total": self._meta_int("dropped_total", 0),
                "outbox_id": self._meta("outbox_id"),
            }

    def close(self) -> None:
        with self._lock:
            try:
                self._db.close()
            except Exception:
                pass
