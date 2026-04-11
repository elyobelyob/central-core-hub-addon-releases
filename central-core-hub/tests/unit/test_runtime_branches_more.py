import builtins
import importlib.util
from pathlib import Path


def _load_module_with_import_hook(hook):
    """Load mqtt_client under a fresh name while applying an import hook.

    The provided `hook` should accept the original import function as
    the first parameter followed by the normal import args. This helper
    patches `builtins.__import__` to call through to the hook which can
    delegate to the original importer as needed.
    """
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    name = f"mqtt_client_hook_{id(hook)}"
    spec = importlib.util.spec_from_file_location(name, str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    orig_import = builtins.__import__

    def wrapper(*args, **kwargs):
        return hook(orig_import, *args, **kwargs)

    try:
        builtins.__import__ = wrapper
        loader.exec_module(mod)
    finally:
        builtins.__import__ = orig_import
    return mod


def test_import_with_no_paho():
    # make import raise for paho packages
    def hook(orig, name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("paho"):
            raise ImportError("no paho")
        return orig(name, globals, locals, fromlist, level)

    mod = _load_module_with_import_hook(hook)
    # mqtt attribute should be None when paho import fails
    assert getattr(mod, "mqtt", None) is None


def test_client_shim_created_when_runtime_helper_missing(monkeypatch):
    # force import of mqtt_runtime to fail during CentralCoreClient.__init__
    def hook(orig, name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mqtt_runtime":
            raise ImportError("no runtime")
        return orig(name, globals, locals, fromlist, level)

    mod = _load_module_with_import_hook(hook)
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "unit-x"})
    # shim should provide publish method
    assert hasattr(c._client, "publish")
    r = c._client.publish("t", "p")
    # paho-like response object with rc attribute expected
    assert hasattr(r, "rc")


def test_on_connect_subscription_failure_and_publish_sensors_exception(monkeypatch):
    # load normal module
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_normal", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "unit-y"})

    class BadClient:
        def subscribe(self, topic, qos=0):
            raise RuntimeError("sub fail")

    # patch publish_sensors to raise so the on_connect path hits its exception
    def ps():
        raise RuntimeError("publish sensors fail")

    c.publish_sensors = ps
    # call on_connect with client whose subscribe raises
    c.on_connect(BadClient(), None, None, rc=0)
    # connected flag should still be True
    assert c._connected is True


def test_connect_retry_path(monkeypatch):
    # exercise connect loop where first wait_for_connected times out then succeeds
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_conn", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "unit-z"})

    seq = {"connect_once": [True, True], "wait": [False, True], "called": 0}

    def connect_once():
        return seq["connect_once"].pop(0)

    def wait_for_connected(timeout=5):
        return seq["wait"].pop(0)

    c.connect_once = connect_once
    c.wait_for_connected = wait_for_connected

    # avoid sleeping delays from _stop_event.wait(timeout=5)
    monkeypatch.setattr(c._stop_event, "wait", lambda timeout=None: None)

    assert c.connect() is True
