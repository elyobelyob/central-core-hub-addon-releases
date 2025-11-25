import importlib.util
from types import SimpleNamespace


def load_runtime():
    spec = importlib.util.spec_from_file_location(
        "mqtt_runtime", "./central-core-hub/mqtt_runtime.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_shim_client_exists_and_methods_work():
    rt = load_runtime()
    ctx = SimpleNamespace()
    ctx.client_id = "cid"
    # use shim by passing None
    client = rt.setup_mqtt_client(ctx, None)
    # exercise some shim methods
    assert hasattr(client, "username_pw_set")
    assert client.username_pw_set("u", "p") is None
    # tls_set should be present and return None
    assert client.tls_set() is None
    r = client.publish("t", "p", qos=1)
    assert hasattr(r, "rc")
    assert client.subscribe("t") == (0, 1)
    assert client.connect() == 0
    client.loop_start(); client.loop_stop(); client.disconnect()


def test_shim_tls_and_callback_assignment_no_errors(capsys):
    rt = load_runtime()
    ctx = SimpleNamespace()
    ctx.client_id = "cid"
    ctx.mqtt_tls = True
    ctx.mqtt_ca = "ca.pem"
    ctx.mqtt_cert = "cert.pem"
    ctx.mqtt_key = "key.pem"
    # provide callbacks
    ctx.on_connect = lambda *a, **k: None
    ctx.on_disconnect = lambda *a, **k: None
    ctx.on_message = lambda *a, **k: None

    client = rt.setup_mqtt_client(ctx, None)
    # shim should accept tls_set and callback assignment without exceptions
    assert client is not None
