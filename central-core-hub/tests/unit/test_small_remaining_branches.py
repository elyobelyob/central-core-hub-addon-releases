import importlib.util
import pathlib
import types
import threading


def _load_ha_client():
    base = pathlib.Path(__file__).parents[2]
    src = base / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load ha_client spec")
    spec.loader.exec_module(mod)
    return mod


def _load_handlers():
    base = pathlib.Path(__file__).parents[2]
    src = base / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load handlers spec")
    spec.loader.exec_module(mod)
    return mod


ha_client = _load_ha_client()
handlers = _load_handlers()


def test_call_service_timeout_path():
    listener = ha_client.HAWebSocketListener("http://x", "t", None)
    # make it appear connected
    listener._ws = object()

    # replace register_request with an event that never gets set
    def reg():
        ev = threading.Event()
        return 99999, ev

    listener._register_request = reg

    # _send_json does nothing
    listener._send_json = lambda sock, obj: None

    res = listener.call_service("d", "s", timeout=0.01)
    assert res is None


def test_is_entity_allowed_variants(monkeypatch):
    # Simulate mqtt_client.is_entity_allowed True/False/exception
    fake = types.SimpleNamespace()

    # True
    fake.is_entity_allowed = lambda e: True
    import sys

    sys.modules["mqtt_client"] = fake
    assert handlers._is_entity_allowed("sensor.x") is True

    # False
    fake.is_entity_allowed = lambda e: False
    assert handlers._is_entity_allowed("sensor.x") is False

    # Exception -> fallback True
    def bad(e):
        raise RuntimeError("boom")

    fake.is_entity_allowed = bad
    assert handlers._is_entity_allowed("sensor.x") is True

    # cleanup
    del sys.modules["mqtt_client"]
