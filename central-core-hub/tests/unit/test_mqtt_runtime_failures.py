import importlib.util
from types import SimpleNamespace
import sys


def load_runtime():
    spec = importlib.util.spec_from_file_location(
        "mqtt_runtime", "./central-core-hub/mqtt_runtime.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_client_constructor_typeerror_chain():
    rt = load_runtime()
    ctx = SimpleNamespace()
    ctx.client_id = "cid"
    ctx.mqtt_username = "u"
    ctx.mqtt_password = "p"

    calls = {"n": 0}

    def Client(*a, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TypeError("bad constructor")

        class C:
            def username_pw_set(self, u, p=None):
                self.auth = (u, p)

        return C()

    mqtt_mod = SimpleNamespace()
    # include CallbackAPIVersion to exercise first-branch
    mqtt_mod.CallbackAPIVersion = SimpleNamespace(VERSION2=2)
    mqtt_mod.Client = Client

    client = rt.setup_mqtt_client(ctx, mqtt_mod)
    # Ensure client created and username_pw_set was called (auth attr set)
    assert hasattr(client, "auth") and client.auth == ("u", "p")


def test_tls_set_failure_logs_to_stderr(capsys):
    rt = load_runtime()
    ctx = SimpleNamespace()
    ctx.client_id = "cid"
    ctx.mqtt_tls = True
    ctx.mqtt_ca = "ca.pem"
    ctx.mqtt_cert = "cert.pem"
    ctx.mqtt_key = "key.pem"

    class C:
        def username_pw_set(self, u, p=None):
            pass

        def tls_set(self, **kw):
            raise RuntimeError("tls boom")

    mqtt_mod = SimpleNamespace()
    mqtt_mod.Client = lambda *a, **k: C()

    rt.setup_mqtt_client(ctx, mqtt_mod)
    captured = capsys.readouterr()
    # The runtime logs an error message to stderr when tls_set fails
    assert "Failed to configure TLS for MQTT" in captured.err


def test_callback_assignment_exception_handled():
    rt = load_runtime()
    ctx = SimpleNamespace()
    ctx.client_id = "cid"
    # provide dummy callbacks that would be assigned
    ctx.on_connect = lambda *a, **k: None
    ctx.on_disconnect = lambda *a, **k: None
    ctx.on_message = lambda *a, **k: None

    class BadClient:
        def __setattr__(self, name, value):
            if name in ("on_connect", "on_disconnect", "on_message"):
                raise RuntimeError("cannot assign callback")
            super().__setattr__(name, value)

    mqtt_mod = SimpleNamespace()
    mqtt_mod.Client = lambda *a, **k: BadClient()

    # Should not raise despite assignment failing
    client = rt.setup_mqtt_client(ctx, mqtt_mod)
    assert client is not None
