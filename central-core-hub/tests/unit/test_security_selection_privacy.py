"""F4: the selection covers sensors only, and sensitive attributes never leave the hub."""

import json
import types

import pytest

import ha_client
import handlers


def _mc():
    """The mqtt_client module handlers will import right now (tests may swap it)."""
    import importlib

    return importlib.import_module("mqtt_client")


SECRET_ATTRS = {
    "friendly_name": "Front",
    "device_class": "door",
    "unit_of_measurement": "%",
    "access_token": "abc123",
    "entity_picture": "/api/camera_proxy/camera.front?token=abc123",
    "entity_picture_local": "/api/image_proxy/x?token=abc",
    "latitude": 51.5,
    "longitude": -0.12,
    "gps_accuracy": 5,
    "altitude": 20,
    "api_key": "k",
    "refresh_token_id": "r",
    "password": "p",
}
SAFE_KEYS = {"friendly_name", "device_class", "unit_of_measurement"}


def test_sanitize_attributes_strips_secrets_and_location():
    out = ha_client.sanitize_attributes(SECRET_ATTRS)
    assert set(out) == SAFE_KEYS
    # the input is not modified
    assert "access_token" in SECRET_ATTRS


@pytest.mark.parametrize("value", [None, [], "x", 3])
def test_sanitize_attributes_tolerates_non_dicts(value):
    assert ha_client.sanitize_attributes(value) == {}


@pytest.mark.parametrize(
    "ent,ok",
    [
        ("sensor.temp", True),
        ("binary_sensor.door", True),
        ("camera.front_door", False),
        ("device_tracker.phone", False),
        ("person.me", False),
        ("lock.front", False),
        ("../services/x", False),
    ],
)
def test_is_selectable_entity(ent, ok):
    assert ha_client.is_selectable_entity(ent) is ok


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(_mc(), "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    published = []
    c = types.SimpleNamespace(client_id="hub1", ha_api_url="http://ha", ha_api_token="tok", selected_sensors=[])
    c.build_ack_topic = lambda action, cid: f"hubs/hub1/v1/ack/{action.replace('/', '.')}/{cid}"
    c._publish = lambda topic, payload, qos=0: published.append((topic, json.loads(payload)))
    return c, published


def test_sensors_set_refuses_non_sensor_domains(tmp_path, monkeypatch):
    c, published = _client(tmp_path, monkeypatch)
    msg = types.SimpleNamespace(topic="hubs/hub1/v1/cmd/sensors/set", retain=False)
    body = json.dumps(
        {
            "command_id": "c1",
            "payload": {"sensors": ["sensor.a", "camera.front_door", "device_tracker.phone", "binary_sensor.b"]},
        }
    )
    handlers.handle_message(c, msg, body, lambda u, t: [], None, None, None)
    assert c.selected_sensors == ["sensor.a", "binary_sensor.b"]
    done = [p for t, p in published if p.get("status") == "completed"][-1]
    assert done["result"]["rejected"] == ["camera.front_door", "device_tracker.phone"]


def test_sensors_set_ack_has_no_secret_attributes(tmp_path, monkeypatch):
    c, published = _client(tmp_path, monkeypatch)
    msg = types.SimpleNamespace(topic="hubs/hub1/v1/cmd/sensors/set", retain=False)
    body = json.dumps({"command_id": "c1", "payload": {"sensors": ["sensor.a"]}})

    def fetch(url, token):
        return [{"entity_id": "sensor.a", "state": "1", "attributes": dict(SECRET_ATTRS)}]

    handlers.handle_message(c, msg, body, fetch, None, None, None)
    done = [p for t, p in published if p.get("status") == "completed"][-1]
    assert set(done["result"]["attributes"]["sensor.a"]) == SAFE_KEYS


def test_sensors_poll_publishes_no_secret_attributes():
    published = []
    c = types.SimpleNamespace(
        client_id="hub1",
        ha_api_url="http://ha",
        ha_api_token="tok",
        selected_sensors=["sensor.a"],
        preferred_sensors_topic="hubs/hub1/v1/telemetry/sensors",
    )
    c.build_ack_topic = lambda action, cid: f"hubs/hub1/v1/ack/{action.replace('/', '.')}/{cid}"
    c._publish = lambda topic, payload, qos=0: published.append((topic, json.loads(payload)))
    msg = types.SimpleNamespace(topic="hubs/hub1/v1/cmd/sensors/poll", retain=False)
    body = json.dumps({"command_id": "p1", "payload": {"sensors": ["door"]}})

    def fetch(url, token):
        return [{"entity_id": "sensor.a", "state": "1", "attributes": dict(SECRET_ATTRS)}]

    handlers.handle_message(c, msg, body, fetch, None, None, None)
    tele = [p for t, p in published if t == c.preferred_sensors_topic][-1]
    assert set(tele["attributes"]["sensor.a"]) == SAFE_KEYS


def _real_client(monkeypatch, tmp_path):
    monkeypatch.setattr(_mc(), "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    c = _mc().CentralCoreClient({"client_id": "hub1", "mqtt_host": "localhost"})
    sent = []
    monkeypatch.setattr(c, "_publish", lambda topic, payload, qos=0: sent.append((topic, json.loads(payload))))
    return c, sent


def test_websocket_change_publishes_no_secret_attributes(monkeypatch, tmp_path):
    c, sent = _real_client(monkeypatch, tmp_path)
    c.selected_sensors = ["sensor.a"]
    c._on_ha_state_event("sensor.a", {"entity_id": "sensor.a", "state": "on", "attributes": dict(SECRET_ATTRS)})
    assert sent
    assert set(sent[-1][1]["attributes"]["sensor.a"]) == SAFE_KEYS


def test_websocket_change_ignores_non_sensor_entities(monkeypatch, tmp_path):
    c, sent = _real_client(monkeypatch, tmp_path)
    # e.g. an old persisted selection that still names a camera
    c.selected_sensors = ["camera.front_door"]
    c._on_ha_state_event("camera.front_door", {"state": "idle", "attributes": dict(SECRET_ATTRS)})
    assert sent == []


def test_fetch_sensors_sanitizes_attributes(monkeypatch):
    class _R:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"entity_id": "sensor.a", "state": "1", "attributes": dict(SECRET_ATTRS)},
                {"entity_id": "camera.front", "state": "idle", "attributes": dict(SECRET_ATTRS)},
            ]

    monkeypatch.setattr(_mc(), "requests", types.SimpleNamespace(get=lambda *a, **k: _R()))
    out = _mc().fetch_sensors("http://ha", "tok")
    assert [s["entity_id"] for s in out] == ["sensor.a"]
    assert set(out[0]["attributes"]) == SAFE_KEYS


def test_fetch_by_ids_sanitizes_attributes():
    class _R:
        def raise_for_status(self):
            return None

        def json(self):
            return {"entity_id": "sensor.a", "state": "1", "attributes": dict(SECRET_ATTRS)}

    req = types.SimpleNamespace(get=lambda *a, **k: _R())
    out = ha_client.fetch_sensors_by_ids("http://ha", "tok", ["sensor.a"], requests_mod=req)
    assert set(out[0]["attributes"]) == SAFE_KEYS
