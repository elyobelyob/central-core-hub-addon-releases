import json
from pathlib import Path
import importlib.util


def _load_modules():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    mqtt_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mqtt_mod)

    src2 = repo_root / "central-core-hub" / "handlers.py"
    spec2 = importlib.util.spec_from_file_location("handlers", str(src2))
    handlers_mod = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(handlers_mod)
    return mqtt_mod, handlers_mod


class DummyMsg:
    def __init__(self, topic, payload_bytes):
        self.topic = topic
        self.payload = payload_bytes


class DummyClient:
    def __init__(self):
        self.published = []
        self.client_id = "unit-hub"
        self.ha_api_url = ""
        self.ha_api_token = ""
        self.ha_readback_after_set = True
        self.preferred_sensors_topic = f"hubs/{self.client_id}/telemetry/sensors"

    def _publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


def test_handle_sensors_poll_no_ha():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/cmd/sensors/poll"
    msg = DummyMsg(topic, b"{}")
    # fetch_sensors is expected to be provided; pass a stub that returns empty
    handlers.handle_message(
        c,
        msg,
        "{}",
        fetch_sensors=lambda a, b: [],
        build_telemetry=mqtt_mod.build_telemetry,
        build_vault_payload=mqtt_mod.build_vault_payload,
        requests=None,
    )
    # should publish telemetry (even if empty)
    assert any(p["topic"] == c.preferred_sensors_topic for p in c.published)


def test_handle_sensors_set_no_ha_fails():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/cmd/sensors/set"
    cmd = {"command_id": "cmd1", "payload": {"sensors": {"sensor.x": "on"}}}
    msg = DummyMsg(topic, json.dumps(cmd).encode("utf-8"))
    handlers.handle_message(
        c,
        msg,
        json.dumps(cmd),
        fetch_sensors=lambda a, b: [],
        build_telemetry=mqtt_mod.build_telemetry,
        build_vault_payload=mqtt_mod.build_vault_payload,
        requests=None,
    )
    # completion response should be published to the command response topic
    resp_topic = f"hubs/{c.client_id}/cmd/cmd1/response"
    assert any(p["topic"] == resp_topic for p in c.published)
