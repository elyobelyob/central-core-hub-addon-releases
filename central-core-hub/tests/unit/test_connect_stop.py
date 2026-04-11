import importlib.util
import pathlib
import threading


def _load():
    src = pathlib.Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_cs", str(src))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_connect_exits_when_stop_event_set():
    mod = _load()
    c = mod.CentralCoreClient({"client_id": "test"})
    # Make connect_once always fail (broker unreachable)
    c.connect_once = lambda: False
    # Set the stop event so the loop exits on first check
    c._stop_event.set()
    result = c.connect()
    assert result is False


def test_close_sets_stop_event():
    mod = _load()
    c = mod.CentralCoreClient({"client_id": "test"})
    assert not c._stop_event.is_set()
    c.close()
    assert c._stop_event.is_set()
