"""Every copy of the hub's timestamp normaliser sends UTC.

The old code converted to a fixed offset captured when the add-on started,
so an add-on started in summer kept sending +01:00 after the clocks went
back. UTC has no such drift, and the vault stores UTC."""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

HUB = os.path.join(os.path.dirname(__file__), "..", "..", "central-core-hub")
sys.path.insert(0, HUB)

CASES = [
    ("2026-07-01T03:10:00+01:00", datetime(2026, 7, 1, 2, 10, tzinfo=timezone.utc)),
    ("2026-07-01T02:10:00Z", datetime(2026, 7, 1, 2, 10, tzinfo=timezone.utc)),
    ("2026-12-01T02:10:00+00:00", datetime(2026, 12, 1, 2, 10, tzinfo=timezone.utc)),
]


def _load(name):
    """The real module from its file; other tests put fakes in sys.modules."""
    spec = importlib.util.spec_from_file_location(f"_tz_{name}", os.path.join(HUB, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _normalisers():
    return [_load("mqtt_client")._normalize_timestamp, _load("ha_client")._normalize_timestamp,
            _load("handlers")._normalize_ts, _load("telemetry_helpers")._normalize_timestamp]


@pytest.mark.parametrize("raw,expected", CASES)
def test_all_normalisers_send_utc(raw, expected):
    for fn in _normalisers():
        out = fn(raw)
        dt = datetime.fromisoformat(out.replace("Z", "+00:00"))
        assert dt.utcoffset() == timedelta(0), (fn.__module__, out)
        assert dt == expected


def test_naive_input_uses_the_local_rules_for_its_own_date(monkeypatch):
    """A naive time is local; its offset comes from that date's rules, not
    the offset in force when the add-on started."""
    if not hasattr(__import__("time"), "tzset"):
        pytest.skip("needs tzset")
    import time
    monkeypatch.setenv("TZ", "Europe/London")
    time.tzset()
    try:
        for fn in _normalisers():
            summer = datetime.fromisoformat(fn("2026-07-01T03:10:00").replace("Z", "+00:00"))
            winter = datetime.fromisoformat(fn("2026-12-01T03:10:00").replace("Z", "+00:00"))
            assert summer == datetime(2026, 7, 1, 2, 10, tzinfo=timezone.utc), fn.__module__
            assert winter == datetime(2026, 12, 1, 3, 10, tzinfo=timezone.utc), fn.__module__
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()
