import importlib.util
from pathlib import Path
import json


def _load_modules():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mqtt_mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mqtt_mod)
    # Ensure the dynamically loaded module is available under the import
    # name so `handlers` can `import mqtt_client` and see the same object.
    import sys

    # register under import name but preserve any existing entry so we
    # don't interfere with other tests that manipulate `sys.modules`.
    _orig_mc = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = mqtt_mod

    src2 = repo_root / "central-core-hub" / "handlers.py"
    spec2 = importlib.util.spec_from_file_location("handlers", str(src2))
    if spec2 is None or getattr(spec2, "loader", None) is None:
        raise ImportError("could not load spec")
    handlers_mod = importlib.util.module_from_spec(spec2)
    hloader = spec2.loader
    assert hloader is not None
    hloader.exec_module(handlers_mod)
    return mqtt_mod, handlers_mod, _orig_mc


class DummyClient:
    def __init__(self, tmpdir):
        self.published = []
        self.client_id = "unit-hub"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.preferred_sensors_topic = f"hubs/{self.client_id}/v1/telemetry/sensors"
        self._tmp = tmpdir

    def _publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class Msg:
    def __init__(self, topic, payload_str):
        self.topic = topic
        self.payload = payload_str.encode("utf-8")


def test_registry_set_writes_file_and_reload(tmp_path, monkeypatch):
    mqtt_mod, handlers, _orig_mc = _load_modules()

    # Ensure SENSOR_REGISTRY points to our temp file
    reg_path = tmp_path / "SENSOR_REGISTRY.json"
    monkeypatch.setattr(mqtt_mod, "SENSOR_REGISTRY", reg_path)

    c = DummyClient(tmp_path)
    topic = f"hubs/{c.client_id}/v1/cmd/registry/set"
    payload = {
        "apply_registry": True,
        "registry_mode": "deny",
        "entries": [{"entity_id": "sensor.forbidden*", "provide": False}],
    }
    cmd = {"command_id": "cmd-reg-1", "payload": payload}
    msg_payload = json.dumps(cmd)
    msg = Msg(topic, msg_payload)

    handlers.handle_message(
        c,
        msg,
        msg_payload,
        fetch_sensors=lambda a, b: [],
        build_telemetry=mqtt_mod.build_telemetry,
        build_vault_payload=mqtt_mod.build_vault_payload,
        requests=None,
    )

    # File should exist and contain the payload
    assert reg_path.exists()
    data = json.loads(reg_path.read_text())
    assert data.get("registry_mode") == "deny"
    assert isinstance(data.get("entries"), list)

    # reload_sensor_registry should make the registry visible to is_entity_allowed
    # (the handler already calls reload; assert behavior)
    assert mqtt_mod.is_entity_allowed("sensor.forbidden123") is False
    assert mqtt_mod.is_entity_allowed("sensor.allowed") is True
    # restore original sys.modules entry
    import sys

    if _orig_mc is None:
        try:
            del sys.modules["mqtt_client"]
        except KeyError:
            pass
    else:
        sys.modules["mqtt_client"] = _orig_mc
