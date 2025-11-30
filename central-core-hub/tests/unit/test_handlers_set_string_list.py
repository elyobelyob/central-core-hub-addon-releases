import json
import importlib.util
from pathlib import Path


def _load_modules():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mc = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mc)

    # handlers.py
    hsrc = repo_root / "central-core-hub" / "handlers.py"
    hspec = importlib.util.spec_from_file_location("handlers", str(hsrc))
    if hspec is None or getattr(hspec, "loader", None) is None:
        raise ImportError("could not load spec")
    hmod = importlib.util.module_from_spec(hspec)
    hloader = hspec.loader
    assert hloader is not None
    hloader.exec_module(hmod)

    return mc, hmod


class DummyClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class DummyMsg:
    def __init__(self, topic, payload_bytes):
        self.topic = topic
        self.payload = payload_bytes


def test_set_accepts_string_list_and_publishes_reminder(monkeypatch):
    mc, handlers = _load_modules()
    CentralCoreClient = mc.CentralCoreClient

    options = {"client_id": "unit-hub"}
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    c.vault_topic = "vault/unit"

    command = {
        "command_id": "set123",
        "action": "sensors/set",
        "payload": {
            "sensors": [
                "sensor.sun_next_dawn",
                "sensor.sun_next_dusk",
            ]
        },
    }
    msg = DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(command).encode("utf-8"))

    c.on_message(None, None, msg)

    # selected_sensors should have been stored on the client
    assert getattr(c, "selected_sensors", None) == [
        "sensor.sun_next_dawn",
        "sensor.sun_next_dusk",
    ]

    # ensure a reminder was published to the vault topic
    vault_msgs = [p for p in dummy.published if p["topic"] == c.vault_topic]
    assert vault_msgs, "no reminder published to vault topic"
    payload = json.loads(vault_msgs[-1]["payload"])
    assert payload.get("selected_sensors") == [
        "sensor.sun_next_dawn",
        "sensor.sun_next_dusk",
    ]
