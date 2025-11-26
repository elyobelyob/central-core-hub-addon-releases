import json
import importlib.util
from pathlib import Path


def _load_modules():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    mc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mc)

    # handlers.py
    hsrc = repo_root / "central-core-hub" / "handlers.py"
    hspec = importlib.util.spec_from_file_location("handlers", str(hsrc))
    hmod = importlib.util.module_from_spec(hspec)
    hspec.loader.exec_module(hmod)

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


def test_poll_updates_selected_and_publishes_reminder(monkeypatch):
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
    monkeypatch.setattr(mc, "fetch_sensors", lambda url, token: sample)

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
    msg = DummyMsg(
        f"hubs/{c.client_id}/v1/cmd/sensors/poll", json.dumps(cmd).encode("utf-8")
    )

    # call through the client's on_message handler which loads handlers
    c.on_message(None, None, msg)

    # selected_sensors should have been stored on the client
    assert getattr(c, "selected_sensors", None) == ["sensor.temp", "sensor.hum"]

    # ensure a reminder was published to the vault topic
    vault_msgs = [p for p in dummy.published if p["topic"] == c.vault_topic]
    assert vault_msgs, "no reminder published to vault topic"
    payload = json.loads(vault_msgs[-1]["payload"])
    assert payload.get("selected_sensors") == ["sensor.temp", "sensor.hum"]


def test_set_publishes_reminder_prefers_client_selected(monkeypatch):
    mc, handlers = _load_modules()
    CentralCoreClient = mc.CentralCoreClient

    # fake requests.post/get to succeed
    posts = []

    class FakeResp:
        def __init__(self, data=None):
            self._data = data or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    def fake_post(url, headers=None, json=None, timeout=10):
        posts.append({"url": url, "json": json})
        return FakeResp()

    def fake_get(url, headers=None, timeout=10):
        # return a readback matching posted values for test
        return FakeResp({"state": "22.0", "attributes": {}})

    monkeypatch.setattr(
        mc,
        "requests",
        type("R", (), {"post": staticmethod(fake_post), "get": staticmethod(fake_get)}),
    )

    options = {
        "client_id": "unit-hub",
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
        "ha_readback_after_set": True,
    }
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    c.vault_topic = "vault/unit"
    # Pretend Vault previously told us the authoritative selection
    c.selected_sensors = ["sensor.temp"]

    command = {
        "command_id": "set123",
        "action": "sensors/set",
        "payload": {"sensors": [{"entity_id": "sensor.temp", "state": "22.0"}]},
    }
    msg = DummyMsg(
        f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(command).encode("utf-8")
    )

    c.on_message(None, None, msg)

    # ensure we attempted to call HA
    assert posts, "expected HA POST calls"

    # ensure the reminder favored client.selected_sensors
    vault_msgs = [p for p in dummy.published if p["topic"] == c.vault_topic]
    assert vault_msgs, "no reminder published to vault topic"
    payload = json.loads(vault_msgs[-1]["payload"])
    assert payload.get("selected_sensors") == ["sensor.temp"]
