import json
import types
from pathlib import Path
import importlib.util


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


def test_set_dict_refused_and_list_selects():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    req = _RecordingRequests()

    cmd = {"command_id": "cmd1", "payload": {"sensors": {"sensor.x": "42"}}}
    msg = types.SimpleNamespace(topic=topic, payload=json.dumps(cmd).encode("utf-8"))
    handlers.handle_message(
        c,
        msg,
        json.dumps(cmd),
        fetch_sensors=lambda a, b: [],
        build_telemetry=mqtt_mod.build_telemetry,
        build_vault_payload=mqtt_mod.build_vault_payload,
        requests=req,
    )
    assert req.calls == []
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/cmd1"
    acks = [json.loads(p["payload"]) for p in c.published if p["topic"] == ack_topic]
    assert acks[-1]["status"] == "failed" and acks[-1]["result"]["reason"] == "invalid_payload"
    assert not any(p["topic"] == c.preferred_sensors_topic for p in c.published)

    cmd2 = {"command_id": "cmd2", "payload": {"sensors": ["sensor.x"]}}
    handlers.handle_message(
        c,
        types.SimpleNamespace(topic=topic),
        json.dumps(cmd2),
        fetch_sensors=lambda a, b: [{"entity_id": "sensor.x", "state": "42", "attributes": {"friendly_name": "X"}}],
        build_telemetry=mqtt_mod.build_telemetry,
        build_vault_payload=mqtt_mod.build_vault_payload,
        requests=req,
    )
    assert req.calls == []
    comp = _secure_final_ack(c.published)
    assert comp["status"] == "completed"
    assert comp["result"]["data"] == {"sensor.x": "42"}
    assert comp["result"]["names"] == {"sensor.x": "X"}


def test_set_with_readback_disabled():
    mqtt_mod, handlers = _load_modules()
    c = DummyClient()
    c.ha_readback_after_set = False
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    cmd = {"command_id": "cmd2", "payload": {"sensors": {"sensor.y": "on"}}}
    msg_payload = json.dumps(cmd)

    def post(url, headers=None, json_body=None, timeout=10):
        payload = json_body or {}
        return Resp({"state": payload.get("state")})

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


# --- helpers for the secure sensors/set and registry/set behaviour ---------


def _secure_final_ack(records):
    """Last non-"acknowledged" ACK body among recorded publishes (any record shape)."""
    last = None
    for r in records:
        topic, payload = (r["topic"], r["payload"]) if isinstance(r, dict) else (r[0], r[1])
        if "/ack/" not in topic:
            continue
        body = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        if isinstance(body, dict) and body.get("status") != "acknowledged":
            last = body
    return last


class _RecordingRequests:
    """A `requests` stand-in that records calls and refuses every one."""

    def __init__(self):
        self.calls = []

    def post(self, url, *a, **k):
        self.calls.append(("POST", url))
        raise AssertionError(f"hub must not POST to Home Assistant: {url}")

    def get(self, url, *a, **k):
        self.calls.append(("GET", url))
        raise AssertionError(f"sensors/set must not call Home Assistant per entity: {url}")
