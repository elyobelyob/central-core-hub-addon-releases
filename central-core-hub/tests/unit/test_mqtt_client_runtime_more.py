import builtins
import importlib.util
from pathlib import Path


def _load_module_with_import_hook(hook):
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    name = f"mqtt_client_hook_runtime_{id(hook)}"
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


def test_import_fallback_loads_file_based_helpers_and_telemetry():
    """Force normal imports to fail so module falls back to loading helpers/telemetry via file-spec."""

    def hook(orig, name, globals=None, locals=None, fromlist=(), level=0):
        # Only block the normal package-style imports for helpers/telemetry
        if name in ("helpers", "telemetry"):
            raise ImportError("simulate missing package")
        return orig(name, globals, locals, fromlist, level)

    mod = _load_module_with_import_hook(hook)
    # After fallback the build_telemetry callable should exist
    assert hasattr(mod, "build_telemetry")
    # calling build_telemetry should return a JSON string
    raw = mod.build_telemetry("unit-fallback")
    assert isinstance(raw, str) and raw.startswith("{")


def test_mqtt_runtime_tls_and_callback_attach_exceptions(monkeypatch):
    # Import mqtt_runtime directly
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_runtime.py"
    spec = importlib.util.spec_from_file_location("mqtt_runtime_test", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    rt = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(rt)

    class Ctx:
        def __init__(self):
            self.client_id = "ctx-1"
            self.mqtt_tls = True
            self.mqtt_ca = "/tmp/ca.pem"
            self.mqtt_cert = "/tmp/cert.pem"
            self.mqtt_key = "/tmp/key.pem"

        def on_connect(self, *a, **k):
            pass

        def on_disconnect(self, *a, **k):
            pass

        def on_message(self, *a, **k):
            pass

    ctx = Ctx()

    # Create a fake mqtt_mod.Client where tls_set raises
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def username_pw_set(self, u, p=None):
            return None

        def tls_set(self, **kw):
            raise RuntimeError("tls fail")

        def publish(self, topic, payload, qos=0):
            class R:
                rc = 0

            return R()

        def subscribe(self, topic, qos=0):
            return (0, 1)

        def connect(self, *a, **k):
            return 0

        def loop_start(self):
            return None

        def loop_stop(self):
            return None

        def disconnect(self):
            return None

    class FakeMod:
        Client = FakeClient

    # Should not raise even though tls_set raises
    rt.setup_mqtt_client(ctx, FakeMod)
    assert hasattr(ctx, "_client")


def test_connect_retry_path(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_conn1", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "unit-retry"})
    # short-circuit connect_once and wait_for_connected
    c.connect_once = lambda: True
    c.wait_for_connected = lambda timeout=5: True
    assert c.connect() is True


def test_connect_loop_handles_connect_failed_and_retries(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_conn2", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "unit-loop1"})

    # make connect_once return False to exercise retry branch
    c.connect_once = lambda: False

    # cause sleep to raise to break out of loop after first iteration
    monkeypatch.setattr(
        mod.time, "sleep", lambda s: (_ for _ in ()).throw(SystemExit())
    )

    try:
        c.connect()
    except SystemExit:
        pass


def test_connect_loop_handles_timed_out_wait(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_conn3", str(src))
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "unit-loop2"})

    # simulate successful connect_once but timed out wait_for_connected
    c.connect_once = lambda: True
    c.wait_for_connected = lambda timeout=5: False

    called = {"stopped": False}

    class FakeClient:
        def loop_stop(self):
            called["stopped"] = True

    c._client = FakeClient()

    monkeypatch.setattr(
        mod.time, "sleep", lambda s: (_ for _ in ()).throw(SystemExit())
    )

    try:
        c.connect()
    except SystemExit:
        pass

    assert called["stopped"] is True


def test_paho_import_absent_sets_mqtt_none():
    # import with hook that raises for paho
    def hook(orig, name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("paho"):
            raise ImportError("no paho")
        return orig(name, globals, locals, fromlist, level)

    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    name = "mqtt_client_no_paho"
    spec = importlib.util.spec_from_file_location(name, str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    orig_import = (
        __builtins__["__import__"]
        if isinstance(__builtins__, dict)
        else __builtins__.__import__
    )
    try:
        __builtins__["__import__"] = lambda *a, **k: hook(orig_import, *a, **k)
        loader = spec.loader
        assert loader is not None
        loader.exec_module(mod)
    finally:
        try:
            __builtins__["__import__"] = orig_import
        except Exception:
            pass

    assert getattr(mod, "mqtt", None) is None


def test_import_with_helpers_present(monkeypatch, tmp_path):
    # Add the central-core-hub directory to sys.path so `from helpers import` works
    repo_root = Path(__file__).resolve().parents[3]
    src_dir = repo_root / "central-core-hub"
    monkeypatch.syspath_prepend(str(src_dir))
    # import mqtt_client under a fresh name so top-level try import runs
    spec = importlib.util.spec_from_file_location(
        "mqtt_client_with_helpers", str(src_dir / "mqtt_client.py")
    )
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    # build_telemetry should be available and callable
    assert hasattr(mod, "build_telemetry")
    raw = mod.build_telemetry("h1")
    assert isinstance(raw, str) and raw.startswith("{")


def test_run_iteration_handles_publish_and_sensors_exceptions(monkeypatch):
    # import normal mqtt_client
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_runit", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "runit"})
    # make the client appear connected so connect path not taken
    c._connected = True

    # publish_telemetry raises
    def bad_telemetry():
        raise RuntimeError("telemetry fail")

    c.publish_telemetry = bad_telemetry

    # publish_sensors will raise when called by run_iteration if last_sensors_sent old
    def bad_sensors():
        raise RuntimeError("sensors fail")

    c.publish_sensors = bad_sensors
    # force sensors to be due
    c._last_sensors_sent = 0

    # Should not raise
    c.run_iteration()


def test_cert_content_handling():
    """Test that certificate content is written to temp files."""
    import os
    from pathlib import Path
    import importlib.util

    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_cert_test", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    CentralCoreClient = mod.CentralCoreClient

    # Mock options with cert content
    ca_content = "-----BEGIN CERTIFICATE-----\nMOCK CA\n-----END CERTIFICATE-----"
    cert_content = "-----BEGIN CERTIFICATE-----\nMOCK CERT\n-----END CERTIFICATE-----"
    key_content = "-----BEGIN PRIVATE KEY-----\nMOCK KEY\n-----END PRIVATE KEY-----"

    options = {
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "mqtt_username": "",
        "mqtt_password": "",
        "mqtt_tls": True,
        "mqtt_cert_bundle": "",
        "client_id": "test-cert-content",
        "telemetry_interval": 30,
    }

    c = CentralCoreClient(options)
    # Set cert content directly (simulating what bundle would do)
    c.mqtt_ca = ca_content
    c.mqtt_cert = cert_content
    c.mqtt_key = key_content
    c._setup_cert_files()  # Re-run to process the content

    # Check that temp files were created
    assert c.mqtt_ca.endswith(".ca.crt")
    assert os.path.exists(c.mqtt_ca)
    with open(c.mqtt_ca, "r") as f:
        assert f.read() == ca_content

    assert c.mqtt_cert.endswith(".client.crt")
    assert os.path.exists(c.mqtt_cert)
    with open(c.mqtt_cert, "r") as f:
        assert f.read() == cert_content

    assert c.mqtt_key.endswith(".client.key")
    assert os.path.exists(c.mqtt_key)
    with open(c.mqtt_key, "r") as f:
        assert f.read() == key_content

    # Cleanup
    os.unlink(c.mqtt_ca)
    os.unlink(c.mqtt_cert)
    os.unlink(c.mqtt_key)


def test_cert_path_handling():
    """Test that certificate paths are used as-is."""
    from pathlib import Path
    import importlib.util

    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location(
        "mqtt_client_cert_path_test", str(src)
    )
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    CentralCoreClient = mod.CentralCoreClient

    options = {
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "mqtt_username": "",
        "mqtt_password": "",
        "mqtt_tls": True,
        "mqtt_cert_bundle": "",
        "client_id": "test-cert-path",
        "telemetry_interval": 30,
    }

    c = CentralCoreClient(options)
    # Set cert paths directly
    c.mqtt_ca = "/path/to/ca.pem"
    c.mqtt_cert = "/path/to/cert.pem"
    c.mqtt_key = "/path/to/key.pem"
    c._setup_cert_files()  # Re-run to process

    # Should remain as paths
    assert c.mqtt_ca == "/path/to/ca.pem"
    assert c.mqtt_cert == "/path/to/cert.pem"
    assert c.mqtt_key == "/path/to/key.pem"


def test_cert_bundle_parsing():
    """Test that certificate bundle is parsed into individual certs."""
    from pathlib import Path
    import importlib.util

    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_bundle_test", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    CentralCoreClient = mod.CentralCoreClient

    bundle_content = """-----BEGIN CERTIFICATE-----
CA CERT CONTENT
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
CLIENT CERT CONTENT
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
PRIVATE KEY CONTENT
-----END PRIVATE KEY-----"""

    options = {
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "mqtt_username": "",
        "mqtt_password": "",
        "mqtt_tls": True,
        "mqtt_ca_cert": "",
        "mqtt_client_cert": "",
        "mqtt_client_key": "",
        "mqtt_cert_bundle": bundle_content,
        "client_id": "test-bundle",
        "telemetry_interval": 30,
    }

    c = CentralCoreClient(options)

    # Check that temp files were created with content
    assert c.mqtt_ca.endswith(".ca.crt")
    with open(c.mqtt_ca, "r") as f:
        assert "CA CERT CONTENT" in f.read()

    assert c.mqtt_cert.endswith(".client.crt")
    with open(c.mqtt_cert, "r") as f:
        assert "CLIENT CERT CONTENT" in f.read()

    assert c.mqtt_key.endswith(".client.key")
    with open(c.mqtt_key, "r") as f:
        assert "PRIVATE KEY CONTENT" in f.read()

    # Cleanup
    import os

    os.unlink(c.mqtt_ca)
    os.unlink(c.mqtt_cert)
    os.unlink(c.mqtt_key)
