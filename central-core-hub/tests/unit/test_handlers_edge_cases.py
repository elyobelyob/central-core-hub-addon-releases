import json
import importlib.util
from pathlib import Path


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


class DummyClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class DummyMsg:
    def __init__(self, topic, payload_bytes=b""):
        self.topic = topic
        self.payload = payload_bytes


def test_poll_malformed_payload_no_ack(monkeypatch):
    mc = _load_client_module()
    CentralCoreClient = mc.CentralCoreClient

    # fetch_sensors returns something so handler publishes telemetry
    monkeypatch.setattr(
        mc,
        "fetch_sensors",
        lambda url, token, safe_classes=None: [{"entity_id": "sensor.x", "state": "1", "attributes": {}}],
    )

    options = {
        "client_id": "unit-hub",
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
    }
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    c.vault_topic = ""

    # payload_str is invalid JSON -> handler should treat as {} and not ack
    msg = DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/poll", b"not-a-json")

    # on_message will decode payload into '<binary>' unless provided; call handlers via on_message
    c.on_message(None, None, msg)

    # ensure no ack topic published (no command_id in payload)
    topics = [p["topic"] for p in dummy.published]
    assert not any("/cmd/" in t and t.endswith("/response") for t in topics)
    # also no telemetry since payload is malformed (no vault request with sensors list)


def test_set_with_sensors_as_dict_is_refused(monkeypatch):
    mc = _load_client_module()
    CentralCoreClient = mc.CentralCoreClient
    req = _RecordingRequests()
    monkeypatch.setattr(mc, "requests", req)

    c = CentralCoreClient(
        {"client_id": "unit-hub", "ha_api_url": "http://ha", "ha_api_token": "tok", "ha_readback_after_set": True}
    )
    dummy = DummyClient()
    c._client = dummy
    c.vault_topic = "vault/unit"
    c.selected_sensors = ["sensor.keep"]

    payload = {"sensors": {"sensor.a": "10", "sensor.b": "20"}}
    cmd = {"command_id": "cid", "action": "sensors/set", "payload": payload}
    c.on_message(None, None, DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(cmd).encode("utf-8")))

    assert req.calls == []
    comp = _secure_final_ack(dummy.published)
    assert comp["status"] == "failed" and comp["result"]["reason"] == "invalid_payload"
    topics = [p["topic"] for p in dummy.published]
    # nothing but the command's own ACKs: no telemetry, no vault reminder
    assert c.preferred_sensors_topic not in topics
    assert c.vault_topic not in topics
    assert c.selected_sensors == ["sensor.keep"]


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
