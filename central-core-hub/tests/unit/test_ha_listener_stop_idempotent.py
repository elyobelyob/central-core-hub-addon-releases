import importlib.util
import pathlib


# Load the ha_client module via importlib to mimic other tests' loading strategy
def _load_ha_client():
    base = pathlib.Path(__file__).parents[2]
    src = base / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load ha_client spec")
    spec.loader.exec_module(mod)
    return mod


def test_ha_listener_stop_idempotent():
    ha_client = _load_ha_client()

    # Create listener instance without starting network activity
    listener = ha_client.HAWebSocketListener("http://example", "token", on_event=None)

    # Provide a dummy websocket object that records close() calls
    class DummyWS:
        def __init__(self):
            self.closed = 0

        def close(self):
            self.closed += 1

    dummy = DummyWS()
    listener._ws = dummy

    # Provide a dummy thread object that's not alive
    class DummyThread:
        def is_alive(self):
            return False

    listener._thread = DummyThread()

    # First stop should close the websocket once
    listener.stop()
    # Second stop should be a no-op and not raise; dummy.closed remains 1
    listener.stop()

    assert dummy.closed == 1
