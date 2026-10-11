import time
import json
import importlib.util
from pathlib import Path


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

    src2 = repo_root / "central-core-hub" / "handlers.py"
    spec2 = importlib.util.spec_from_file_location("handlers", str(src2))
    if spec2 is None or getattr(spec2, "loader", None) is None:
        raise ImportError("could not load spec")
    handlers_mod = importlib.util.module_from_spec(spec2)
    hloader = spec2.loader
    assert hloader is not None
    hloader.exec_module(handlers_mod)
    return mqtt_mod, handlers_mod


class DummyClient:
    def __init__(self):
        self.published = []
        self.client_id = "unit-hub"
        # Intentionally do NOT set ha_api_url/ha_api_token to force no_ha_config
        self.ha_readback_after_set = True
        self.preferred_sensors_topic = f"hubs/{self.client_id}/v1/telemetry/sensors"

    def build_ack_topic(self, action, command_id):
        raise RuntimeError("boom")

    def _publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class Msg:
    def __init__(self, topic):
        self.topic = topic
        self.payload = b""


def test_sensors_set_sends_no_ack_when_build_ack_fails():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    cmd = {"command_id": "s1", "timestamp": time.time(), "payload": {"sensors": [{"entity_id": "sensor.x", "state": "on"}]}}
    payload = json.dumps(cmd)
    msg = Msg(topic)

    handlers.handle_message(c, msg, payload, None, None, None)

    # build_ack_topic failed: nothing is acknowledged on a guessed topic
    assert not any("/ack/" in str(p["topic"]) for p in c.published), c.published
