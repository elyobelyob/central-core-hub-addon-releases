import json
import time
import pathlib
import importlib.util


def _load_module():
    base = pathlib.Path(__file__).parents[2]
    src = base / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load ha_client spec")
    spec.loader.exec_module(mod)
    return mod


ha = _load_module()


def test_set_get_ha_version_with_ttl():
    # set explicit timestamp and verify TTL behavior
    ha.set_ha_version("2025.12.0", ts=1000.0)
    assert ha.get_ha_version() == "2025.12.0"
    # TTL smaller than age -> should return None
    assert ha.get_ha_version(ttl_seconds=1.0) is None
    # recent timestamp should be returned when TTL large
    now = time.time()
    ha.set_ha_version("9000.0", ts=now)
    assert ha.get_ha_version(ttl_seconds=10.0) == "9000.0"


def test_persist_ha_version_writes_options_and_calls_callback(tmp_path):
    opts = tmp_path / "options.json"
    # monkeypatch module-level OPTIONS_PATH
    ha.OPTIONS_PATH = str(opts)

    called = {}

    def cb(v):
        called["v"] = v

    listener = ha.HAWebSocketListener("http://ha", "tok", None, on_ha_version=cb)
    ok = listener._persist_ha_version("2025.99.1")
    assert ok is True
    assert opts.exists()
    data = json.loads(opts.read_text())
    assert data.get("ha_version") == "2025.99.1"
    assert called.get("v") == "2025.99.1"

    # If options file contains non-dict, persistence should overwrite it
    opts.write_text("not-a-json")
    ok2 = listener._persist_ha_version("2025.99.2")
    assert ok2 is True
    data2 = json.loads(opts.read_text())
    assert data2.get("ha_version") == "2025.99.2"


def test_persist_callback_exception_handled(tmp_path):
    opts = tmp_path / "options.json"
    ha.OPTIONS_PATH = str(opts)

    def cb_fail(v):
        raise RuntimeError("boom")

    listener = ha.HAWebSocketListener("http://ha", "tok", None, on_ha_version=cb_fail)
    # callback raises but _persist_ha_version should still return True
    ok = listener._persist_ha_version("2025.0.0")
    assert ok is True
    data = json.loads(opts.read_text())
    assert data.get("ha_version") == "2025.0.0"


def test_call_service_sets_and_returns_pending_result():
    listener = ha.HAWebSocketListener("http://ha", "tok", None)
    # make _ws truthy so call_service doesn't bail early
    listener._ws = object()

    # Replace _send_json so it simulates a backend that immediately
    # responds with a 'result' message using the provided id.
    def fake_send(sock, obj):
        try:
            req_id = obj.get("id")
        except Exception:
            req_id = None
        if req_id is not None:
            listener._set_pending_result(req_id, {"result": {"ok": True}})

    listener._send_json = fake_send

    res = listener.call_service("domain", "do", {"a": 1}, timeout=0.5)
    assert isinstance(res, dict)
    assert res.get("result", {}).get("ok") is True
