import importlib.util
from pathlib import Path
import types
import json


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_on_message_handler_import_failure(monkeypatch):
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "impfail"})

    class M:
        def __init__(self):
            self.topic = f"hubs/{c.client_id}/cmd/sensors/poll"
            self.payload = b"{}"

    # Ensure a normal import would fail by placing a blocker in builtins
    import builtins

    orig_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "handlers":
            raise ModuleNotFoundError("no handlers")
        return orig_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Also make the file-loader fallback raise by monkeypatching importlib.util.spec_from_file_location
    import importlib.util as ilu

    def fake_spec(name, path):
        raise RuntimeError("spec fail")

    monkeypatch.setattr(ilu, "spec_from_file_location", fake_spec)

    # on_message should not raise even if handlers import fails
    m = M()
    c._client = types.SimpleNamespace()
    c.on_message(None, None, m)


def test_connect_retries_until_success(monkeypatch):
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "retry"})

    calls = {"n": 0}

    def seq_connect_once():
        calls["n"] += 1
        # first call fails, second succeeds
        return calls["n"] >= 2

    monkeypatch.setattr(c, "connect_once", seq_connect_once)
    monkeypatch.setattr(c, "wait_for_connected", lambda timeout=5: True)
    # avoid sleeping delays
    monkeypatch.setattr("time.sleep", lambda s: None)

    ok = c.connect()
    assert ok is True
    assert calls["n"] >= 2


def test_handler_ack_publish_raises_but_handler_continues(monkeypatch):
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    # load handlers directly
    handlers_spec = Path(mod.__file__).parent / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", handlers_spec)
    handlers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(handlers)

    c = CentralCoreClient(
        {"client_id": "ackerr", "ha_api_url": "http://ha", "ha_api_token": "t"}
    )

    # make _publish raise to simulate publish failures
    def bad_publish(topic, payload, qos=0):
        raise RuntimeError("pubfail")

    c._publish = bad_publish

    # create a set command message
    cmd = {"command_id": "c1", "payload": {"sensors": {"sensor.z": "1"}}}
    m = types.SimpleNamespace(
        topic=f"hubs/{c.client_id}/cmd/sensors/set",
        payload=json.dumps(cmd).encode("utf-8"),
    )

    # should not raise even though _publish raises internally
    handlers.handle_message(
        c,
        m,
        json.dumps(cmd),
        fetch_sensors=lambda a, b: [],
        build_telemetry=mod.build_telemetry,
        build_vault_payload=mod.build_vault_payload,
        requests=types.SimpleNamespace(
            post=lambda *a, **k: types.SimpleNamespace(
                raise_for_status=lambda: None, json=lambda: {"state": "1"}
            ),
            get=lambda *a, **k: types.SimpleNamespace(
                raise_for_status=lambda: None, json=lambda: {"state": "1"}
            ),
        ),
    )


def test_mqtt_runtime_tls_set_raises(monkeypatch):
    rt_src = (
        Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_runtime.py"
    )
    spec = importlib.util.spec_from_file_location("mqtt_runtime", str(rt_src))
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)

    class Ctx:
        def __init__(self):
            self.client_id = "ctx1"
            self.mqtt_username = ""
            self.mqtt_password = ""
            self.mqtt_tls = True
            self.mqtt_ca = ""
            self.mqtt_cert = ""
            self.mqtt_key = ""

    ctx = Ctx()

    class FakeClient:
        def __init__(self, client_id=None, clean_session=None):
            pass

        def tls_set(self, **kw):
            raise RuntimeError("tlsboom")

    fake_mqtt = types.SimpleNamespace(Client=FakeClient)
    # Should not raise when tls_set raises
    rt.setup_mqtt_client(ctx, fake_mqtt)
    assert hasattr(ctx, "_client")


def test_publish_telemetry_vault_transform_raises(monkeypatch):
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "vt-ex"})
    dummy = types.SimpleNamespace()
    published = []

    def pub(topic, payload, qos=0):
        published.append((topic, payload))

        class R:
            rc = 0

        return R()

    dummy.publish = pub
    c._client = dummy
    mod.build_telemetry = lambda cid: "raw"

    def bad_vault(raw):
        raise RuntimeError("vault-err")

    mod.build_vault_payload = bad_vault
    # should not raise; primary telemetry should be published
    c.publish_telemetry()
    assert any(t[0] == c.telemetry_topic for t in published)
