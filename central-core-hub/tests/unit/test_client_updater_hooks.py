"""CentralCoreClient exposes the updater and switches off HA auto-update once."""
import importlib.util
import threading
from pathlib import Path


def _load():
    src = Path(__file__).resolve().parents[2] / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_hooks", str(src))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mc = _load()


class Listener:
    def request(self, payload, timeout=15.0):
        return None


def test_no_listener_no_updater():
    c = mc.CentralCoreClient({"client_id": "u1"})
    c._ha_ws_listener = None
    assert c.addon_updater() is None


def test_updater_uses_the_listener():
    c = mc.CentralCoreClient({"client_id": "u2"})
    c._ha_ws_listener = Listener()
    up = c.addon_updater()
    assert up is not None and up.listener is c._ha_ws_listener


def test_auto_update_switched_off_once_off_the_listener_thread(monkeypatch):
    c = mc.CentralCoreClient({"client_id": "u3"})
    calls, done = [], threading.Event()

    class FakeUpdater:
        def disable_auto_update(self):
            calls.append(threading.current_thread().name)
            done.set()
            return True

    monkeypatch.setattr(c, "addon_updater", lambda: FakeUpdater())
    c._on_ha_version("2026.9.3")
    c._on_ha_version("2026.9.3")
    assert done.wait(2)
    assert len(calls) == 1
    # must not run on the caller's thread: the caller is HA's receive loop,
    # which is what delivers the reply the updater waits for
    assert calls[0] != threading.current_thread().name
