import importlib.util
import sys
import types
import json


def load_telemetry():
    spec = importlib.util.spec_from_file_location("telemetry", "./central-core-hub/telemetry.py")
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    return mod


def test_external_get_cpu_percent_override_success():
    t = load_telemetry()
    # attach external override
    setattr(t, "_external_get_cpu_percent", lambda: 42)
    try:
        assert t._get_cpu_percent() == 42
    finally:
        delattr(t, "_external_get_cpu_percent")


def test_external_get_cpu_percent_exception_and_sys_module_fallback():
    t = load_telemetry()

    def bad():
        raise RuntimeError("bad ext")

    setattr(t, "_external_get_cpu_percent", bad)
    # add dummy mqtt_client module to sys.modules
    mod = types.ModuleType("mqtt_client")
    setattr(mod, "get_cpu_percent", lambda: 7)
    sys.modules.setdefault("mqtt_client", mod)
    try:
        # external raises, so fallback to mqtt_client.get_cpu_percent should return 7
        assert t._get_cpu_percent() == 7
    finally:
        try:
            delattr(t, "_external_get_cpu_percent")
        except Exception:
            pass
        # remove our dummy module
        if sys.modules.get("mqtt_client") is mod:
            del sys.modules["mqtt_client"]


def test_build_telemetry_get_cpu_callable_raises_uses_fallback():
    t = load_telemetry()
    # ensure no external override
    if hasattr(t, "_external_get_cpu_percent"):
        delattr(t, "_external_get_cpu_percent")

    # add dummy module for fallback
    mod = types.ModuleType("mqtt_client")
    setattr(mod, "get_cpu_percent", lambda: 5)
    sys.modules.setdefault("mqtt_client", mod)
    try:

        def raiseer():
            raise ValueError("boom")

        payload = t.build_telemetry("cid", get_cpu_percent=raiseer, version="v")
        data = json.loads(payload)
        assert data["cpu_percent"] == 5
    finally:
        if sys.modules.get("mqtt_client") is mod:
            del sys.modules["mqtt_client"]


def test_build_telemetry_socket_connect_fails_results_in_unknown_ip():
    t = load_telemetry()
    # monkeypatch socket.socket to an object whose connect raises
    import socket as _socket

    class BadSock:
        def __init__(self, *a, **k):
            pass

        def connect(self, *a, **k):
            raise OSError("no network")

        def close(self):
            pass

    orig = _socket.socket
    _socket.socket = BadSock
    try:
        payload = t.build_telemetry("cid")
        data = json.loads(payload)
        assert data["ip"] == "unknown"
    finally:
        _socket.socket = orig
