"""CPU percentage from /proc/stat, and telemetry fields when the host
helpers return something unexpected (missing, wrong shape, or raising)."""

import builtins
import io
import json

import pytest

import helpers
import telemetry


def _proc_stat(monkeypatch, *first_lines):
    lines = iter(first_lines)
    real_open = builtins.open

    def fake_open(path, *a, **k):
        if path == "/proc/stat":
            return io.StringIO(next(lines))
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(helpers.time, "sleep", lambda s: None)


def test_cpu_percent_from_two_samples(monkeypatch):
    # second sample: 100 more jiffies, 25 of them idle -> 75% busy
    _proc_stat(monkeypatch, "cpu  100 0 100 800 0 0 0 0\n", "cpu  150 0 125 825 0 0 0 0\n")
    assert helpers.get_cpu_percent() == 75.0


def test_cpu_percent_none_when_first_line_is_not_cpu_total(monkeypatch):
    _proc_stat(monkeypatch, "intr 12345\n")
    assert helpers._read_proc_stat() == (None, None)
    _proc_stat(monkeypatch, "intr 12345\n")
    assert helpers.get_cpu_percent() is None


def test_cpu_percent_none_when_no_time_passed(monkeypatch):
    same = "cpu  100 0 100 800 0 0 0 0\n"
    _proc_stat(monkeypatch, same, same)
    assert helpers.get_cpu_percent() is None  # no division by zero


def test_cpu_percent_none_when_second_sample_unreadable(monkeypatch):
    _proc_stat(monkeypatch, "cpu  100 0 100 800 0 0 0 0\n", "garbage\n")
    assert helpers.get_cpu_percent() is None


# --- telemetry shapes ---------------------------------------------------------


def _build(**kw):
    defaults = dict(uptime_fn=lambda: 5, loadavg_fn=lambda: (0.1, 0.2, 0.3), mem_info_fn=lambda: (10, 4),
                    disk_info_fn=lambda: (100, 40), get_cpu_percent=lambda: 3.5)
    defaults.update(kw)
    return json.loads(telemetry.build_telemetry("hub", **defaults))


@pytest.mark.parametrize("bad", ["0.1 0.2", None, 3])
def test_loadavg_of_wrong_shape_is_empty(bad):
    assert _build(loadavg_fn=lambda: bad)["load_avg"] == []


@pytest.mark.parametrize("bad", [(1,), None, "10 4"])
def test_mem_and_disk_of_wrong_shape_are_null(bad):
    out = _build(mem_info_fn=lambda: bad, disk_info_fn=lambda: bad)
    assert out["mem_total_kb"] is None and out["mem_free_kb"] is None
    assert out["disk_total_kb"] is None and out["disk_free_kb"] is None


def test_raising_helpers_give_nulls_not_a_crash():
    def boom():
        raise OSError("no /proc")

    out = _build(uptime_fn=boom, loadavg_fn=boom, mem_info_fn=boom, disk_info_fn=boom)
    assert (out["uptime"], out["load_avg"], out["mem_total_kb"], out["disk_total_kb"]) == (None, [], None, None)


def test_uptime_non_number_is_null():
    assert _build(uptime_fn=lambda: "5 days")["uptime"] is None
    assert _build(uptime_fn=lambda: 12.9)["uptime"] == 12


def test_cpu_falls_back_to_external_override_when_injected_fails(monkeypatch):
    def boom():
        raise RuntimeError("x")

    monkeypatch.setattr(telemetry, "_external_get_cpu_percent", lambda: 42.0, raising=False)
    assert _build(get_cpu_percent=boom)["cpu_percent"] == 42.0


def test_cpu_null_when_override_and_helpers_fail(monkeypatch):
    def boom():
        raise RuntimeError("x")

    monkeypatch.setattr(telemetry, "_external_get_cpu_percent", boom, raising=False)
    monkeypatch.setattr(helpers, "get_cpu_percent", boom)
    assert _build(get_cpu_percent=lambda: None)["cpu_percent"] is None
