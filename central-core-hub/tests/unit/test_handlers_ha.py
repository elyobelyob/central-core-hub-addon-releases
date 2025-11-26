import json
import types
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


class DummyClient:
    def __init__(self):
        self.published = []
        self.client_id = "unit-hub"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.ha_readback_after_set = True
        self.preferred_sensors_topic = f"hubs/{self.client_id}/v1/telemetry/sensors"

    def _publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_set_with_ha_readback():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    cmd = {"command_id": "cmd1", "payload": {"sensors": {"sensor.x": "42"}}}
    msg_payload = json.dumps(cmd)

    # requests stub that returns expected responses
    def post(url, headers=None, json=None, timeout=10):
        return Resp({"state": json.get("state")})

    def get(url, headers=None, timeout=10):
        return Resp({"state": "42", "attributes": {"friendly_name": "X"}})

    requests_stub = types.SimpleNamespace(post=post, get=get)

    msg = types.SimpleNamespace(topic=topic, payload=msg_payload.encode("utf-8"))
    handlers.handle_message(
        c,
        msg,
        msg_payload,
        fetch_sensors=lambda a, b: [],
        build_telemetry=mqtt_mod.build_telemetry,
        build_vault_payload=mqtt_mod.build_vault_payload,
        requests=requests_stub,
    )

    # Expect completion response and telemetry publish
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/cmd1"
    assert any(p["topic"] == ack_topic for p in c.published)
    assert any(p["topic"] == c.preferred_sensors_topic for p in c.published)


def test_set_with_readback_disabled():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    c.ha_readback_after_set = False
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    cmd = {"command_id": "cmd2", "payload": {"sensors": {"sensor.y": "on"}}}
    msg_payload = json.dumps(cmd)

    def post(url, headers=None, json=None, timeout=10):
        return Resp({"state": json.get("state")})

    # get should not be called when readback disabled; provide one anyway
    def get(url, headers=None, timeout=10):
        return Resp({"state": "on", "attributes": {}})

    requests_stub = types.SimpleNamespace(post=post, get=get)
    msg = types.SimpleNamespace(topic=topic, payload=msg_payload.encode("utf-8"))
    handlers.handle_message(
        c,
        msg,
        msg_payload,
        fetch_sensors=lambda a, b: [],
        build_telemetry=mqtt_mod.build_telemetry,
        build_vault_payload=mqtt_mod.build_vault_payload,
        requests=requests_stub,
    )

    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/cmd2"
    assert any(p["topic"] == ack_topic for p in c.published)
