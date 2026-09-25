"""F6: when TLS is on and cannot be set up, the hub must not connect in plaintext."""

import types

import mqtt_runtime


class _FakeClient:
    def __init__(self, *a, **k):
        self.connected_to = None
        self.tls_calls = 0

    def username_pw_set(self, u, p=None):
        pass

    def tls_set(self, **kw):
        self.tls_calls += 1
        raise FileNotFoundError("no such CA file")

    def connect(self, host, port, keepalive=60):
        self.connected_to = (host, port)
        return 0


def _ctx(tls=True):
    return types.SimpleNamespace(
        client_id="hub1",
        mqtt_username="u",
        mqtt_password="p",
        mqtt_tls=tls,
        mqtt_ca="/nonexistent/ca.crt",
        mqtt_cert="",
        mqtt_key="",
        on_connect=None,
        on_disconnect=None,
        on_message=None,
    )


def test_tls_setup_failure_is_recorded():
    ctx = _ctx()
    mod = types.SimpleNamespace(Client=_FakeClient)
    mqtt_runtime.setup_mqtt_client(ctx, mod)
    assert ctx._client.tls_calls == 1
    assert ctx._tls_error


def test_no_tls_error_when_tls_is_off():
    ctx = _ctx(tls=False)
    mqtt_runtime.setup_mqtt_client(ctx, types.SimpleNamespace(Client=_FakeClient))
    assert getattr(ctx, "_tls_error", None) is None


def test_client_refuses_to_connect_after_tls_failure(monkeypatch, tmp_path):
    import importlib

    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    monkeypatch.setattr(mc, "mqtt", types.SimpleNamespace(Client=_FakeClient))
    c = mc.CentralCoreClient(
        {"client_id": "hub1", "mqtt_host": "broker.example", "mqtt_port": 8883, "mqtt_tls": True,
         "mqtt_cert_bundle": "/nonexistent/bundle.pem"}
    )
    assert c._tls_error
    assert c.connect_once() is False
    assert c._client.connected_to is None
