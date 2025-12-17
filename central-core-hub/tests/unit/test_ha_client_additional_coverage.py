import importlib.util
import pathlib
import json
import time
import pytest


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


def test_set_get_ha_version_ttl():
    # ensure get/set behave and TTL works
    ha_client.set_ha_version("1.2.3", ts=time.time())
    assert ha_client.get_ha_version() == "1.2.3"
    # old timestamp returns None when TTL applied
    ha_client.set_ha_version("9.9.9", ts=time.time() - 1000)
    assert ha_client.get_ha_version(ttl_seconds=1) is None


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_fetch_sensors_and_by_ids():
    # fetch_sensors returns None when inputs missing
    assert ha_client.fetch_sensors(None, None) is None

    # fake list response
    data = [
        {"entity_id": "sensor.foo", "state": "1", "attributes": {"friendly_name": "Foo"}},
        {"entity_id": "light.bar", "state": "on", "attributes": {}},
    ]

    class ReqMod:
        @staticmethod
        def get(url, headers=None, timeout=None):
            return _FakeResp(data)

    sensors = ha_client.fetch_sensors("http://ha", "token", requests_mod=ReqMod)
    assert isinstance(sensors, list)
    assert any(s["entity_id"] == "sensor.foo" for s in sensors)

    # fetch by ids: one good, one raises

    class ReqMod2:
        @staticmethod
        def get(url, headers=None, timeout=None):
            if url.endswith("sensor.good"):
                return _FakeResp({"entity_id": "sensor.good", "state": "ok", "attributes": {"friendly_name": "Good"}})
            raise Exception("net")

    res = ha_client.fetch_sensors_by_ids("http://ha", "token", ["sensor.good", "sensor.bad"], requests_mod=ReqMod2)
    assert isinstance(res, list)
    assert any(r["entity_id"] == "sensor.good" for r in res)


def test_ws_url_variants():
    listener = ha_client.HAWebSocketListener("https://host.local", "t", None)
    assert listener._ws_url().startswith("wss://") and listener._ws_url().endswith("/api/websocket")
    listener = ha_client.HAWebSocketListener("http://host.local/", "t", None)
    assert listener._ws_url().startswith("ws://")
    listener = ha_client.HAWebSocketListener("", "t", None)
    assert listener._ws_url() is None


def test_persist_ha_version_writes(tmp_path):
    # point OPTIONS_PATH to a temp file and ensure persistence and callback
    opts = tmp_path / "opts.json"
    ha_client.OPTIONS_PATH = str(opts)
    called = []

    def cb(v):
        called.append(v)

    listener = ha_client.HAWebSocketListener("http://x", "t", None, on_ha_version=cb)
    ok = listener._persist_ha_version("2.5.1")
    assert ok is True
    # file contains ha_version
    content = json.loads(opts.read_text())
    assert content.get("ha_version") == "2.5.1"
    assert called and called[0] == "2.5.1"


def test_call_service_immediate_result():
    listener = ha_client.HAWebSocketListener("http://x", "t", None)
    # make it appear connected
    listener._ws = object()

    def fake_send(sock, payload):
        # simulate immediate response
        listener._set_pending_result(payload.get("id"), {"ok": True})

    listener._send_json = fake_send
    res = listener.call_service("domain", "svc", {"a": 1}, timeout=1.0)
    assert res == {"ok": True}


def test__load_ha_client_importerror(monkeypatch):
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *a, **k: None)
    with pytest.raises(ImportError):
        _load_ha_client()
