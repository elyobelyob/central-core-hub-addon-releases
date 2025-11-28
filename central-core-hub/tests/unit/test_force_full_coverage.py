import importlib
import importlib.util
import sys
from pathlib import Path


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    return mod


def test_connect_once_handles_connect_exception():
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "unit"})

    class BadClient:
        def connect(self, *a, **k):
            raise RuntimeError("connect fail")

        def loop_start(self):
            return None

    c._client = BadClient()
    assert c.connect_once() is False


def test_connect_short_circuits_when_connected(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "unit"})

    # short-circuit connect_once and wait_for_connected to avoid loops
    c.connect_once = lambda: True
    c.wait_for_connected = lambda timeout=5: True

    assert c.connect() is True


def test__publish_handles_exceptions():
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "unit"})

    class BadPub:
        def publish(self, topic, payload, qos=0):
            raise RuntimeError("pub fail")

    c._client = BadPub()
    # _publish should swallow exceptions and return None
    assert c._publish("t", "p") is None


def test_on_message_handles_missing_handlers_import(monkeypatch):
    """Ensure on_message does not raise when handlers import and fallback fail."""
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient

    c = CentralCoreClient({"client_id": "unit"})

    class DummyMsg:
        def __init__(self):
            self.topic = "hubs/unit/v1/cmd/other"
            self.payload = b"{}"

    # Force importlib.util.spec_from_file_location to raise so fallback fails
    monkeypatch.setattr(
        importlib.util,
        "spec_from_file_location",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no file")),
    )

    # remove handlers from sys.modules if present
    sys.modules.pop("handlers", None)

    # should not raise
    c.on_message(None, None, DummyMsg())
