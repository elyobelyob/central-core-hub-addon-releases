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


def test_poll_keeps_selection_and_publishes_reminder(monkeypatch):
    mc, handlers = _load_modules()
    CentralCoreClient = mc.CentralCoreClient

    # stub fetch_sensors to return sample sensors
    sample = [
        {
            "entity_id": "sensor.temp",
            "state": "21.5",
            "attributes": {"friendly_name": "Temp"},
        },
        {
            "entity_id": "sensor.hum",
            "state": "42",
            "attributes": {"friendly_name": "Humidity"},
        },
    ]
    monkeypatch.setattr(mc, "fetch_sensors", lambda url, token, safe_classes=None: sample)

    options = {
        "client_id": "unit-hub",
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
    }
    c = CentralCoreClient(options)
    dummy = DummyClient()
    # paho shim uses .publish; our handlers call client._publish via CentralCoreClient
    # but test harness sets _client to dummy and CentralCoreClient._publish wraps it.
    c._client = dummy
    c.vault_topic = "vault/unit"

    cmd = {
        "command_id": "abc123",
        "action": "sensors/poll",
        "payload": {"sensors": ["sensor.temp", "sensor.hum"]},
    }
    msg = DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/poll", json.dumps(cmd).encode("utf-8"))

    c.selected_sensors = []

    # call through the client's on_message handler which loads handlers
    c.on_message(None, None, msg)

    # a poll reports sensors; only sensors/set changes the watch list
    assert c.selected_sensors == []

    # ensure a reminder was published to the vault topic (falls back to the
    # reported sensors when nothing is selected)
    vault_msgs = [p for p in dummy.published if p["topic"] == c.vault_topic]
    assert vault_msgs, "no reminder published to vault topic"
    payload = json.loads(vault_msgs[-1]["payload"])
    assert payload.get("selected_sensors") == ["sensor.temp", "sensor.hum"]


def test_set_write_form_refused_and_keeps_client_selection(monkeypatch):
    mc, handlers = _load_modules()
    CentralCoreClient = mc.CentralCoreClient
    req = _RecordingRequests()
    monkeypatch.setattr(mc, "requests", req)

    c = CentralCoreClient(
        {"client_id": "unit-hub", "ha_api_url": "http://ha", "ha_api_token": "tok", "ha_readback_after_set": True}
    )
    dummy = DummyClient()
    c._client = dummy
    c.vault_topic = "vault/unit"
    c.selected_sensors = ["sensor.temp"]

    command = {"command_id": "set123", "action": "sensors/set", "payload": {"sensors": [{"entity_id": "sensor.temp", "state": "22.0"}]}}
    c.on_message(None, None, DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(command).encode("utf-8")))

    assert req.calls == [], "no HA call for a write form"
    assert c.selected_sensors == ["sensor.temp"]
    assert not [p for p in dummy.published if p["topic"] == c.vault_topic]
    comp = _secure_final_ack(dummy.published)
    assert comp["status"] == "failed" and comp["result"]["reason"] == "invalid_payload"

    # the list form replaces the selection and reminds the vault of it
    command = {"command_id": "set124", "action": "sensors/set", "payload": {"sensors": ["sensor.hum"]}}
    c.on_message(None, None, DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(command).encode("utf-8")))
    assert c.selected_sensors == ["sensor.hum"]
    reminder = json.loads([p for p in dummy.published if p["topic"] == c.vault_topic][-1]["payload"])
    assert reminder["selected_sensors"] == ["sensor.hum"]


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
