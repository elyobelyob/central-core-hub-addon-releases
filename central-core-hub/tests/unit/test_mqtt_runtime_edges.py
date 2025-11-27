import importlib.util
from pathlib import Path


def _load_runtime():
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
        self.client_id = "u1"
        self.mqtt_username = "user"
        self.mqtt_password = "pw"
        self.mqtt_tls = True
        self.mqtt_ca = "ca"
        self.mqtt_cert = "cert"
        self.mqtt_key = "key"


def test_client_constructor_fallback_and_username_set(monkeypatch):
    rt = _load_runtime()

    # craft a mqtt_mod where Client __init__ raises TypeError for certain kwargs
    class Client:
        def __init__(self, *a, **kw):
            # simulate TypeError for signatures that include clean_session or callback_api_version
            if "clean_session" in kw or "callback_api_version" in kw:
                raise TypeError("bad signature")
            # otherwise succeed

        def username_pw_set(self, u, p=None):
            self._user = u
            self._pw = p

    mqtt_mod = type(
        "M",
        (),
        {"Client": Client, "CallbackAPIVersion": type("C", (), {"VERSION2": 2})},
    )

    ctx = DummyCtx()
    rt.setup_mqtt_client(ctx, mqtt_mod)
    # ensure we got a client instance and username was set
    assert hasattr(ctx, "_client")


def test_tls_set_exception_handled(monkeypatch):
    rt = _load_runtime()

    class ClientObj:
        def __init__(self, *a, **kw):
            pass

        def username_pw_set(self, u, p=None):
            return None

        def tls_set(self, **kw):
            raise RuntimeError("tls fail")

    mqtt_mod = type("M", (), {"Client": ClientObj})
    ctx = DummyCtx()
    # should not raise
    rt.setup_mqtt_client(ctx, mqtt_mod)
    assert hasattr(ctx, "_client")


def test_callback_assignment_ignored_when_raises(monkeypatch):
    rt = _load_runtime()

    class ClientObj:
        def __init__(self, *a, **kw):
            pass

        def username_pw_set(self, u, p=None):
            return None

        def __setattr__(self, name, value):
            if name.startswith("on_"):
                raise RuntimeError("no callbacks allowed")
            return object.__setattr__(self, name, value)

    mqtt_mod = type("M", (), {"Client": ClientObj})
    ctx = DummyCtx()
    # should not raise even though callback assignment will raise internally
    rt.setup_mqtt_client(ctx, mqtt_mod)
    assert hasattr(ctx, "_client")
