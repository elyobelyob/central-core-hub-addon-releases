import json
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


def test_fetch_ha_info_parses_config_like_response(tmp_path):
    # Prepare a fake requests-like module with a get() that returns an object
    class Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeReqs:
        def __init__(self, payload):
            self.payload = payload

        def get(self, url, headers=None, timeout=None):
            return Resp(self.payload)

    repo_root = Path(__file__).resolve().parents[3]
    ha_path = repo_root / "central-core-hub" / "ha_client.py"
    ha = _load_module(ha_path, "ha_client_testmod")

    payload = {
        "version": "2025.11.3",
        "supervisor": {"version": "2025.11.5"},
        "os_name": "Home Assistant OS",
        "os_version": "16.3",
        "frontend_version": "20251105.1",
    }

    info = ha.fetch_ha_info("http://ha", "token", requests_mod=FakeReqs(payload))
    assert info is not None
    assert info.get("core") == "2025.11.3"
    assert info.get("supervisor") == "2025.11.5"
    # operating_system may be provided as name or name+version; accept either
    os_info = info.get("operating_system") or ""
    assert "Home Assistant OS" in os_info or "16.3" in os_info


def test_fetch_ha_info_handles_non_dict_and_errors(tmp_path):
    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return [1, 2, 3]

    class FakeReqs:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    repo_root = Path(__file__).resolve().parents[3]
    ha_path = repo_root / "central-core-hub" / "ha_client.py"
    ha = _load_module(ha_path, "ha_client_testmod2")

    info = ha.fetch_ha_info("http://ha", "token", requests_mod=FakeReqs())
    assert info is None


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


def test_publish_telemetry_includes_home_assistant(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    mqtt_path = repo_root / "central-core-hub" / "mqtt_client.py"
    mqtt = _load_module(mqtt_path, "mqtt_client_testmod")
    ha_path = repo_root / "central-core-hub" / "ha_client.py"
    ha = _load_module(ha_path, "ha_client_testmod3")
    # Ensure mqtt_client's `from ha_client import fetch_ha_info` finds our
    # test-loaded module by inserting it into sys.modules under the expected
    # name.
    import sys

    sys.modules["ha_client"] = ha

    # Create a dummy client with minimal options
    opts = {"client_id": "test-hub", "ha_api_url": "http://ha", "ha_api_token": "tok"}
    c = mqtt.CentralCoreClient(opts)

    # Monkeypatch fetch_ha_info to return a known dict
    monkeypatch.setattr(ha, "fetch_ha_info", lambda url, token: {"core": "2025.11.3"})

    captured = {}

    def fake_publish(topic, payload, qos=0):
        captured["topic"] = topic
        captured["payload"] = payload

        class R:
            rc = 0

        return R()

    # Replace the instance _publish to capture what would be sent
    monkeypatch.setattr(c, "_publish", fake_publish)

    # Call publish_telemetry and ensure payload contains home_assistant
    # To test that `home_assistant` is passed through, monkeypatch the
    # module-level `build_telemetry` used by mqtt_client to capture kwargs
    # and ensure `home_assistant` is present. This avoids interacting with
    # the shared pydantic model which may filter unknown fields.
    import json as _json

    def fake_bt(client_id, **kwargs):
        # return a JSON payload that includes the kwargs for assertion
        return _json.dumps({"client_id": client_id, **kwargs})

    monkeypatch.setattr(mqtt, "build_telemetry", fake_bt)

    # Ensure ha_client import used by mqtt resolves to our test module
    import sys
    sys.modules["ha_client"] = ha

    c.publish_telemetry()
    assert "payload" in captured
    data = json.loads(captured["payload"])
    assert data.get("home_assistant") and data["home_assistant"].get("core") == "2025.11.3"
