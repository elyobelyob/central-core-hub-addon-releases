"""HAWebSocketListener.request() returns Home Assistant's whole reply."""
import importlib.util
import pathlib


def _load():
    src = pathlib.Path(__file__).parents[2] / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client_req", str(src))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ha = _load()


def _listener(reply):
    listener = ha.HAWebSocketListener("http://ha", "tok", None)
    listener._ws = object()
    sent = []

    def fake_send(sock, obj):
        sent.append(obj)
        listener._set_pending_result(obj["id"], reply)

    listener._send_json = fake_send
    return listener, sent


def test_request_returns_the_full_reply_including_errors():
    reply = {"type": "result", "success": False, "error": {"code": "unauthorized", "message": "no"}}
    listener, sent = _listener(reply)
    assert listener.request({"type": "supervisor/api", "endpoint": "/store/reload"}, timeout=0.5) == reply
    assert sent[0]["type"] == "supervisor/api" and "id" in sent[0]


def test_request_does_not_modify_the_callers_payload():
    listener, _ = _listener({"success": True})
    payload = {"type": "get_states"}
    listener.request(payload, timeout=0.5)
    assert payload == {"type": "get_states"}


def test_request_without_a_connection_returns_none():
    listener = ha.HAWebSocketListener("http://ha", "tok", None)
    listener._ws = None
    assert listener.request({"type": "get_states"}) is None
