"""Tests for central-core-hub/helpers.py.

The helpers read /proc/* files which don't exist on macOS.
Tests mock builtins.open (or os.statvfs) to inject controlled data.
"""

import importlib.util
import pathlib
from io import StringIO
from unittest.mock import patch, MagicMock


def _load_module():
    base = pathlib.Path(__file__).resolve().parents[2] / "central-core-hub"
    spec = importlib.util.spec_from_file_location("helpers", str(base / "helpers.py"))
    if spec is None or spec.loader is None:
        raise ImportError("could not load helpers")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h = _load_module()


# ---------------------------------------------------------------------------
# uptime_seconds
# ---------------------------------------------------------------------------


class TestUptimeSeconds:
    def test_returns_integer_uptime(self):
        with patch("builtins.open", return_value=StringIO("12345.67 890.12\n")):
            assert h.uptime_seconds() == 12345

    def test_returns_none_on_missing_file(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert h.uptime_seconds() is None

    def test_returns_none_on_parse_error(self):
        with patch("builtins.open", return_value=StringIO("notanumber\n")):
            assert h.uptime_seconds() is None

    def test_truncates_float_to_int(self):
        with patch("builtins.open", return_value=StringIO("999.99 0\n")):
            assert h.uptime_seconds() == 999


# ---------------------------------------------------------------------------
# loadavg
# ---------------------------------------------------------------------------


class TestLoadavg:
    def test_returns_three_load_values(self):
        with patch("builtins.open", return_value=StringIO("0.10 0.20 0.30 1/100 12345\n")):
            result = h.loadavg()
            assert result == ["0.10", "0.20", "0.30"]

    def test_returns_empty_list_on_missing_file(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert h.loadavg() == []

    def test_returns_empty_list_on_empty_file(self):
        with patch("builtins.open", return_value=StringIO("")):
            assert h.loadavg() == []


# ---------------------------------------------------------------------------
# mem_info_kb
# ---------------------------------------------------------------------------


class TestMemInfoKb:
    def test_returns_mem_total_and_free(self):
        content = "MemTotal:       8192000 kB\nMemFree:        4096000 kB\n"
        with patch("builtins.open", return_value=StringIO(content)):
            total, free = h.mem_info_kb()
            assert total == 8192000
            assert free == 4096000

    def test_returns_none_none_on_missing_file(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            total, free = h.mem_info_kb()
            assert total is None
            assert free is None

    def test_returns_none_none_when_keys_absent(self):
        content = "SomeOtherKey: 100 kB\n"
        with patch("builtins.open", return_value=StringIO(content)):
            total, free = h.mem_info_kb()
            assert total is None
            assert free is None

    def test_ignores_short_lines(self):
        content = "BadLine\nMemTotal:       1000 kB\nMemFree:        500 kB\n"
        with patch("builtins.open", return_value=StringIO(content)):
            total, free = h.mem_info_kb()
            assert total == 1000
            assert free == 500


# ---------------------------------------------------------------------------
# disk_info_kb
# ---------------------------------------------------------------------------


class TestDiskInfoKb:
    def test_returns_total_and_free_kb(self):
        st = MagicMock()
        st.f_blocks = 2000
        st.f_bavail = 1000
        st.f_frsize = 4096
        with patch("os.statvfs", return_value=st):
            total, free = h.disk_info_kb("/")
            assert total == (2000 * 4096) // 1024
            assert free == (1000 * 4096) // 1024

    def test_returns_none_none_on_error(self):
        with patch("os.statvfs", side_effect=OSError):
            total, free = h.disk_info_kb("/")
            assert total is None
            assert free is None

    def test_uses_custom_path(self):
        st = MagicMock()
        st.f_blocks = 100
        st.f_bavail = 50
        st.f_frsize = 1024
        with patch("os.statvfs", return_value=st) as mock_stat:
            h.disk_info_kb("/data")
            mock_stat.assert_called_once_with("/data")


# ---------------------------------------------------------------------------
# _read_proc_stat
# ---------------------------------------------------------------------------


class TestReadProcStat:
    def test_returns_idle_and_total(self):
        # cpu  user nice sys idle iowait irq softirq steal guest
        content = "cpu  100 10 50 800 20 5 5 0 0 0\n"
        with patch("builtins.open", return_value=StringIO(content)):
            idle, total = h._read_proc_stat()
            assert idle == 800
            assert total == sum([100, 10, 50, 800, 20, 5, 5, 0, 0, 0])

    def test_returns_none_none_on_missing_file(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            idle, total = h._read_proc_stat()
            assert idle is None
            assert total is None


# ---------------------------------------------------------------------------
# get_cpu_percent
# ---------------------------------------------------------------------------


class TestGetCpuPercent:
    def test_returns_float_between_0_and_100(self):
        # First call: idle=800, total=1000. Second call: idle=810, total=1100 (100 more total, 10 more idle → 90% busy)
        call_count = [0]
        results = [(800, 1000), (810, 1100)]

        def fake_read():
            r = results[call_count[0]]
            call_count[0] += 1
            return r

        with patch.object(h, "_read_proc_stat", side_effect=fake_read):
            with patch("time.sleep"):
                result = h.get_cpu_percent()
                assert result is not None
                assert 0.0 <= result <= 100.0

    def test_returns_none_when_first_read_fails(self):
        with patch.object(h, "_read_proc_stat", return_value=(None, None)):
            with patch("time.sleep"):
                assert h.get_cpu_percent() is None

    def test_cpu_percent_calculation(self):
        # delta_total=200, delta_idle=100 → usage = (1 - 100/200) * 100 = 50.0
        results = [(1000, 2000), (1100, 2200)]
        call_count = [0]

        def fake_read():
            r = results[call_count[0]]
            call_count[0] += 1
            return r

        with patch.object(h, "_read_proc_stat", side_effect=fake_read):
            with patch("time.sleep"):
                result = h.get_cpu_percent()
                assert result == 50.0
