import importlib.util
import pathlib
import json
import sys
import os
import types


def _load_handlers():
    base = pathlib.Path(__file__).parents[2]
    src = base / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load handlers spec")
    spec.loader.exec_module(mod)
    return mod


handlers = _load_handlers()


class FakeClient:
    def __init__(self, client_id="cid"):
        self.client_id = client_id
        self.publishes = []

    def _publish(self, topic, payload, qos=0):
        self.publishes.append((topic, payload, qos))

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"


def test_registry_set_writes_local_when_mqtt_missing(tmp_path):
    # ensure mqtt_client is not importable by replacing it with a dummy
    orig = sys.modules.get("mqtt_client", None)
    sys.modules["mqtt_client"] = types.SimpleNamespace()
    # ensure no registry token is present in the env to avoid auth failures
    orig_env = os.environ.pop("REGISTRY_TOKEN", None)
    try:
        msg = type("M", (), {"topic": "hubs/cid/v1/cmd/registry/set"})
        payload_obj = {"entries": [{"a": 1}]}
        payload = {"command_id": "rnm1", "payload": payload_obj}

        handlers.handle_message(FakeClient(), msg, json.dumps(payload), None, None, None)

        # file should be written next to handlers.py
        target = pathlib.Path(__file__).parents[2] / "SENSOR_REGISTRY_from_mqtt.json"
        assert target.exists()
        data = json.loads(target.read_text())
        assert data.get("entries") == payload_obj.get("entries")
    finally:
        # cleanup file and restore module
        try:
            target.unlink()
        except Exception:
            pass
        if orig is not None:
            sys.modules["mqtt_client"] = orig
        else:
            sys.modules.pop("mqtt_client", None)
        if orig_env is not None:
            os.environ["REGISTRY_TOKEN"] = orig_env
