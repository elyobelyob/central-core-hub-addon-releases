import importlib.util
from pathlib import Path


def load_ha_module():
    p = Path(__file__).resolve().parents[2] / "central-core-hub" / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ws_url_variants():
    ha = load_ha_module()
    Listener = ha.HAWebSocketListener
    assert Listener("", "t", None)._ws_url() is None
    assert Listener("http://ha", "t", None)._ws_url().startswith("ws://")
    assert Listener("https://ha", "t", None)._ws_url().startswith("wss://")


def test_start_without_websocket(monkeypatch):
    ha = load_ha_module()
    monkeypatch.setattr(ha, "websocket", None)
    listener = ha.HAWebSocketListener("http://ha", "t", lambda e: None)
    assert listener.start() is False


def test_stop_handles_exceptions(monkeypatch):
    ha = load_ha_module()
    listener = ha.HAWebSocketListener("http://ha", "t", lambda e: None)

    # Ensure stop proceeds (is_set False by default)
    class BadWS:
        def close(self):
            raise RuntimeError("close fail")

    class BadThread:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            raise RuntimeError("join fail")

    listener._ws = BadWS()
    listener._thread = BadThread()

    # Should not raise despite inner exceptions
    listener.stop()

    # After stop, attributes should be cleared
    assert getattr(listener, "_ws") is None
    assert getattr(listener, "_thread") is None


def test_run_auth_persist_called(monkeypatch):
    ha = load_ha_module()

    persisted = {"called": False}

    def fake_persist(self, v):
        persisted["called"] = True
        return True

    monkeypatch.setattr(ha.HAWebSocketListener, "_persist_ha_version", fake_persist)

    # Fake websocket module
    class FakeWS:
        def __init__(self):
            self._msgs = [
                '{"type": "auth_required", "ha_version": "1.2"}',
                '{"type": "auth_ok"}',
            ]

        def recv(self):
            if self._msgs:
                return self._msgs.pop(0)
            return ""

        def send(self, payload):
            return None

        def close(self):
            return None

    class FakeWebsocketModule:
        def create_connection(self, url, timeout=None):
            return FakeWS()

    monkeypatch.setattr(ha, "websocket", FakeWebsocketModule())

    listener = ha.HAWebSocketListener("http://ha", "tok", lambda a, b: None)

    import threading
    import time

    t = threading.Thread(target=listener._run, daemon=True)
    t.start()
    # Let it run briefly so it processes the fake messages
    time.sleep(0.1)
    listener._stop.set()
    t.join(timeout=2)

    assert persisted["called"] is True
