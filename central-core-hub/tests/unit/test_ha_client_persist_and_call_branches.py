import importlib.util
import json
import sys
from pathlib import Path


def load_ha_client():
    src = Path(__file__).resolve().parents[2] / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(src))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ha_client"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_persist_ha_version_writes_file_and_calls_callback(tmp_path):
    ha = load_ha_client()

    opts = tmp_path / "options.json"
    # ensure an empty options file exists
    opts.write_text(json.dumps({}))

    ha.OPTIONS_PATH = str(opts)

    called = {}

    def on_version(v):
        called["v"] = v

    listener = ha.HAWebSocketListener("http://ha", "token", on_event=None, on_ha_version=on_version)
    ok = listener._persist_ha_version("2025.12")
    assert ok is True
    # file should contain ha_version
    data = json.loads(opts.read_text())
    assert data.get("ha_version") == "2025.12"
    assert called.get("v") == "2025.12"


def test_call_service_returns_none_without_ws():
    ha = load_ha_client()
    listener = ha.HAWebSocketListener("http://ha", "token", on_event=None)
    # no _ws attached
    assert listener.call_service("domain", "svc") is None
