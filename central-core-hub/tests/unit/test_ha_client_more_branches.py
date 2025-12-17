import importlib.util
import pathlib


def _load_ha_client():
    base = pathlib.Path(__file__).parents[2]
    src = base / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load ha_client spec")
    spec.loader.exec_module(mod)
    return mod


ha_client = _load_ha_client()


def test_register_and_set_pending_result():
    listener = ha_client.HAWebSocketListener("http://x", "t", None)
    # register two requests and ensure ids differ and events are set
    id1, ev1 = listener._register_request()
    id2, ev2 = listener._register_request()
    assert id1 != id2
    # set pending result for id1 and ensure event is set
    listener._set_pending_result(id1, {"ok": True})
    assert ev1.is_set()
    # setting pending for unknown id should be no-op
    listener._set_pending_result(99999, {"no": True})


def test_send_json_exception_path(monkeypatch):
    class BadSock:
        def send(self, data):
            raise RuntimeError("boom")

    listener = ha_client.HAWebSocketListener("http://x", "t", None)
    # Should not raise even when sock.send raises
    listener._send_json(BadSock(), {"a": 1})


def test_call_service_no_ws_returns_none():
    listener = ha_client.HAWebSocketListener("http://x", "t", None)
    listener._ws = None
    assert listener.call_service("d", "s") is None
