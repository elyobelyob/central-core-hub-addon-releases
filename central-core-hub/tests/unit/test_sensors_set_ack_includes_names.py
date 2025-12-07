import json
import importlib.util
import pathlib


def _load_handlers():
    base = pathlib.Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("handlers", str(base / "handlers.py"))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load handlers spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    return mod


# load handlers implementation dynamically so tests work from any CWD
_handlers = _load_handlers()
handle_message = getattr(_handlers, "handle_message")


class Msg:
    def __init__(self, topic):
        self.topic = topic


class DummyClient:
    def __init__(self):
        self.client_id = "test-hub"
        self.preferred_sensors_topic = f"hubs/{self.client_id}/v1/telemetry/sensors"
        self.vault_topic = None
        # attributes used by handlers
        self.ha_api_url = None
        self.ha_api_token = None
        self.ha_readback_after_set = False
        self.published = []

    def _publish(self, topic, payload, qos=0):
        entry = {"topic": topic, "payload": payload, "qos": qos}
        self.published.append(entry)
        return True

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"


def fetch_sensors_dummy(ha_api_url, ha_api_token):
    return [
        {
            "entity_id": "sensor.x",
            "state": "1",
            "attributes": {"friendly_name": "X"},
            "last_changed": "2025-12-07T11:00:00Z",
        },
        {
            "entity_id": "sensor.y",
            "state": "off",
            "attributes": {"friendly_name": "Y"},
            "last_updated": "2025-12-07T11:00:05Z",
        },
    ]


def test_ack_includes_names(tmp_path):
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    selected = ["sensor.x", "sensor.y"]
    cmd = {"command_id": "cmd-xyz", "payload": {"sensors": selected}}
    msg = Msg(topic)

    # Ensure no pre-existing file
    target = pathlib.Path(__file__).parent.parent / "SELECTED_SENSORS.json"
    if target.exists():
        try:
            target.unlink()
        except Exception:
            pass

    handle_message(c, msg, json.dumps(cmd), fetch_sensors_dummy, None, None, None)

    # completion ack was published
    ack_topics = [p for p in c.published if "/v1/ack/" in p["topic"]]
    assert ack_topics, f"no ack published, published: {c.published}"

    comp = None
    for p in ack_topics:
        try:
            obj = json.loads(p["payload"])
        except Exception:
            continue
        if obj.get("status") == "completed":
            comp = obj
            break
    assert comp is not None, f"no completed ack found in {ack_topics}"
    result = comp.get("result") or {}

    # ensure selected sensors echoed back
    assert result.get("selected") == selected

    # ensure friendly names map present and correct
    names = result.get("names") or {}
    assert names.get("sensor.x") == "X"
    assert names.get("sensor.y") == "Y"

    # cleanup
    if target.exists():
        try:
            target.unlink()
        except Exception:
            pass
