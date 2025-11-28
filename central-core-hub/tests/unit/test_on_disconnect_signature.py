import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_on_disconnect_accepts_extra_args():
    """Ensure on_disconnect handles extra positional and keyword args without raising."""
    mod = _load_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "sig-hub"})

    # Basic call: single rc positional
    c._connected = True
    c.on_disconnect(None, None, 1)
    assert c._connected is False

    # Extra positional args (simulating paho passing extra fields)
    c._connected = True
    c.on_disconnect(None, None, 1, None)
    assert c._connected is False

    c._connected = True
    c.on_disconnect(None, None, 1, None, None)
    assert c._connected is False

    # Keyword args style
    c._connected = True
    c.on_disconnect(None, None, rc=1, properties=None)
    assert c._connected is False
