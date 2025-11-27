import importlib.util
from pathlib import Path


def _load_runtime_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_runtime.py"
    spec = importlib.util.spec_from_file_location("mqtt_runtime", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


class DummyCtx:
    def __init__(self):
        self.client_id = "cid"
        self.mqtt_username = "u"
        self.mqtt_password = "p"
        self.mqtt_tls = True
        self.mqtt_ca = "/tmp/ca"
        self.mqtt_cert = "/tmp/cert"
        self.mqtt_key = "/tmp/key"
        self._client = None


def test_setup_shim_when_no_mqtt():
    rt = _load_runtime_module()
    ctx = DummyCtx()
    # when mqtt_mod is None, a shim should be assigned
    rt.setup_mqtt_client(ctx, None)
    assert hasattr(ctx, "_client")
    # shim should provide publish/subscribe/connect
    assert hasattr(ctx._client, "publish")
    assert hasattr(ctx._client, "subscribe")


def test_setup_with_fake_mqtt_module(monkeypatch):
    rt = _load_runtime_module()
    ctx = DummyCtx()

    class FakeClientObj:
        def __init__(self, client_id=None, clean_session=None):
            self.client_id = client_id
            self.clean_session = clean_session
            self.tls_kwargs = None

        def username_pw_set(self, u, p=None):
            self.user = u
            self.pw = p

        def tls_set(self, **kw):
            self.tls_kwargs = kw

    class FakeMQTTMod:
        Client = FakeClientObj

    rt.setup_mqtt_client(ctx, FakeMQTTMod)
    # should attach ctx._client of type FakeClientObj
    assert isinstance(ctx._client, FakeClientObj)
    # username should be set
    assert getattr(ctx._client, "user", None) == "u"
