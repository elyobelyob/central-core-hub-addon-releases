import json
import importlib.util
from pathlib import Path
import pytest


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
    def __init__(self, topic, payload_bytes: object = b""):
        self.topic = topic
        self.payload = payload_bytes


def test_poll_data_type_parsing(monkeypatch):
    mc = _load_client_module()
    CentralCoreClient = mc.CentralCoreClient

    sample = [
        {"entity_id": "sensor.on", "state": "on", "attributes": {"device_class": "temperature"}},
        {"entity_id": "sensor.off", "state": "off", "attributes": {"device_class": "temperature"}},
        {"entity_id": "sensor.int", "state": "42", "attributes": {"device_class": "temperature"}},
        {"entity_id": "sensor.float", "state": "3.14", "attributes": {"device_class": "temperature"}},
        {"entity_id": "sensor.text", "state": "n/a", "attributes": {"device_class": "temperature"}},
    ]
    monkeypatch.setattr(mc, "fetch_sensors", lambda url, token, safe_classes=None: sample)

    options = {
        "client_id": "unit-hub",
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
    }
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    c.vault_topic = ""

    cmd = {"command_id": "cid1", "action": "sensors/poll", "payload": {"sensors": ["temperature"]}}
    msg = DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/poll", json.dumps(cmd).encode("utf-8"))

    c.on_message(None, None, msg)

    tele_payload = json.loads(next(p["payload"] for p in dummy.published if p["topic"] == c.preferred_sensors_topic))
    data = tele_payload.get("data")
    # Preserve raw HA-provided values (no coercion)
    assert data["sensor.on"] == "on"
    assert data["sensor.off"] == "off"
    assert data["sensor.int"] == "42"
    assert data["sensor.float"] == "3.14"
    assert data["sensor.text"] == "n/a"


def test__load_client_module_importerror(monkeypatch):
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *a, **k: None)
    with pytest.raises(ImportError):
        _load_client_module()


def test_on_message_binary_payload_and_set_write_form_refused(monkeypatch):
    mc = _load_client_module()
    CentralCoreClient = mc.CentralCoreClient
    monkeypatch.setattr(
        mc,
        "fetch_sensors",
        lambda url, token, safe_classes=None: [{"entity_id": "sensor.x", "state": "1", "attributes": {}}],
    )
    req = _RecordingRequests()
    monkeypatch.setattr(mc, "requests", req)

    c = CentralCoreClient({"client_id": "unit-hub"})  # no HA config
    dummy = DummyClient()
    c._client = dummy

    class BadPayload:
        def decode(self, *a, **k):
            raise RuntimeError("bad")

    # a payload that cannot be decoded is handled without raising
    c.on_message(None, None, DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/poll", BadPayload()))

    cmd = {"command_id": "cid2", "action": "sensors/set", "payload": {"sensors": [{"entity_id": "sensor.x", "state": "2"}]}}
    c.on_message(None, None, DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(cmd).encode("utf-8")))

    resp_topic = c.build_ack_topic(cmd["action"], cmd["command_id"])
    comps = [json.loads(p["payload"]) for p in dummy.published if p["topic"] == resp_topic]
    assert comps, "completion response not published"
    assert comps[-1]["status"] == "failed"
    assert comps[-1]["result"] == {"reason": "invalid_payload"}
    assert req.calls == []


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
