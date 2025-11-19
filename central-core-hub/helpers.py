import os
import time


def uptime_seconds():
    try:
        with open("/proc/uptime", "r") as f:
            return int(float(f.readline().split()[0]))
    except Exception:
        return None


def loadavg():
    try:
        with open("/proc/loadavg", "r") as f:
            parts = f.readline().split()
            return parts[0:3]
    except Exception:
        return []


def mem_info_kb():
    try:
        m = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    m[parts[0].rstrip(":")] = int(parts[1])
        return m.get("MemTotal"), m.get("MemFree")
    except Exception:
        return None, None


def disk_info_kb(path="/"):
    try:
        st = os.statvfs(path)
        total = (st.f_blocks * st.f_frsize) // 1024
        free = (st.f_bavail * st.f_frsize) // 1024
        return total, free
    except Exception:
        return None, None


def _read_proc_stat():
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
            if not line.startswith("cpu "):  # pragma: no cover
                return None, None
            parts = line.split()[1:]
            vals = [int(x) for x in parts]
            idle = vals[3]
            total = sum(vals)
            return idle, total
    except Exception:
        return None, None


def get_cpu_percent():
    idle1, total1 = _read_proc_stat()
    if idle1 is None:
        return None
    time.sleep(0.1)
    idle2, total2 = _read_proc_stat()
    if idle2 is None or total2 is None or total2 == total1:  # pragma: no cover
        return None
    idle_delta = idle2 - idle1
    total_delta = total2 - total1
    try:  # pragma: no cover
        usage = (1.0 - (idle_delta / total_delta)) * 100.0
        return round(usage, 1)
    except Exception:
        return None  # pragma: no cover
