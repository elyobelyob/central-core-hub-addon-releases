import json
import time
from pathlib import Path
import importlib.util


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_build_telemetry_includes_home_assistant():
    repo_root = Path(__file__).resolve().parents[3]
    tele_path = repo_root / "central-core-hub" / "telemetry.py"
    tele = _load_module(tele_path, "telemetry_testmod")

    ha_info = {
        "installation_method": "Home Assistant OS",
        "core": "2025.11.3",
        "supervisor": "2025.11.5",
        "operating_system": "16.3",
        "frontend": "20251105.1",
    }

    raw = tele.build_telemetry("cid-test", home_assistant=ha_info)
    assert raw is not None
    data = json.loads(raw)
    assert "home_assistant" in data
    assert data["home_assistant"].get("core") == "2025.11.3"


def test_ha_websocket_writes_version_to_options(tmp_path, monkeypatch):
    # Load the ha_client module from the repo
    repo_root = Path(__file__).resolve().parents[3]
    ha_path = repo_root / "central-core-hub" / "ha_client.py"
    ha = _load_module(ha_path, "ha_client_testmod_ws")

    # Redirect OPTIONS_PATH to a temp file so unit test doesn't touch /data
    opts_file = tmp_path / "options.json"
    monkeypatch.setattr(ha, "OPTIONS_PATH", str(opts_file))

    # Fake websocket object that will return the handshake messages and a
    # get_config result containing the version.
    class FakeWS:
        def __init__(self, msgs):
            self._msgs = msgs[:]

        def send(self, data):
            # accept and ignore
            return None

        def recv(self):
            if self._msgs:
                return json.dumps(self._msgs.pop(0))
            time.sleep(0.05)
            return ""

        def close(self):
            return None

    msgs = [
        {"type": "auth_required"},
        {"type": "auth_ok"},
        {"type": "result", "id": 2, "result": {"version": "2025.11.3"}},
    ]

    # Monkeypatch websocket.create_connection to return our FakeWS
    class FakeWSModule:
        def create_connection(self, *args, **kwargs):
            return FakeWS(msgs)

    monkeypatch.setattr(ha, "websocket", FakeWSModule())

    # Start listener; it should write the ha_version into the options file
    listener = ha.HAWebSocketListener("http://ha.local", "tok", on_event=None, log_fn=lambda m: None)
    started = listener.start()
    assert started is True

    # Wait up to 2s for the options file to be written
    deadline = time.time() + 2.0
    while time.time() < deadline and not opts_file.exists():
        time.sleep(0.05)

    # Stop the listener thread
    listener.stop()

    assert opts_file.exists(), "options.json not written by websocket listener"
    data = json.loads(opts_file.read_text())
    assert data.get("ha_version") == "2025.11.3"
    # Ensure in-memory cache was also populated
    assert ha.get_ha_version() == "2025.11.3"


def test_ha_websocket_auth_message_writes_version(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    ha_path = repo_root / "central-core-hub" / "ha_client.py"
    ha = _load_module(ha_path, "ha_client_testmod_ws_auth")

    opts_file = tmp_path / "options.json"
    monkeypatch.setattr(ha, "OPTIONS_PATH", str(opts_file))

    class FakeWS:
        def __init__(self, msgs):
            self._msgs = msgs[:]

        def send(self, data):
            return None

        def recv(self):
            if self._msgs:
                return json.dumps(self._msgs.pop(0))
            time.sleep(0.05)
            return ""

        def close(self):
            return None

    msgs = [
        {"type": "auth_required", "ha_version": "2025.12.1"},
        {"type": "auth_ok"},
    ]

    class FakeWSModule:
        def create_connection(self, *args, **kwargs):
            return FakeWS(msgs)

    monkeypatch.setattr(ha, "websocket", FakeWSModule())

    listener = ha.HAWebSocketListener("http://ha.local", "tok", on_event=None, log_fn=lambda m: None)
    assert listener.start() is True

    deadline = time.time() + 2.0
    while time.time() < deadline and not opts_file.exists():
        time.sleep(0.05)

    listener.stop()
    assert opts_file.exists()
    data = json.loads(opts_file.read_text())
    assert data.get("ha_version") == "2025.12.1"
    assert ha.get_ha_version() == "2025.12.1"
