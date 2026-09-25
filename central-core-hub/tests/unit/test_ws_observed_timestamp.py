"""The websocket change message's `observed` time is Home Assistant's last_changed.

last_changed is a top-level field of a state, not an attribute; reading it from
attributes meant `observed` was always "now".
"""

import importlib
import json
from datetime import datetime

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    c = mc.CentralCoreClient({"client_id": "hub1"})
    sent = []
    monkeypatch.setattr(c, "_publish", lambda topic, payload, qos=0: sent.append(json.loads(payload)))
    c.selected_sensors = ["binary_sensor.door"]
    return c, sent


def _same_instant(a, b):
    return datetime.fromisoformat(a.replace("Z", "+00:00")) == datetime.fromisoformat(b.replace("Z", "+00:00"))


def test_observed_uses_top_level_last_changed(client):
    c, sent = client
    c._on_ha_state_event(
        "binary_sensor.door",
        {
            "entity_id": "binary_sensor.door",
            "state": "on",
            "attributes": {"device_class": "door"},
            "last_changed": "2026-01-02T03:04:05.123456+00:00",
            "last_updated": "2026-01-02T03:04:09+00:00",
        },
    )
    observed = sent[-1]["observed"]["binary_sensor.door"]
    assert _same_instant(observed, "2026-01-02T03:04:05.123456+00:00")


def test_observed_falls_back_to_last_updated_then_now(client):
    c, sent = client
    c._on_ha_state_event("binary_sensor.door", {"state": "on", "attributes": {}, "last_updated": "2026-01-02T00:00:00Z"})
    assert _same_instant(sent[-1]["observed"]["binary_sensor.door"], "2026-01-02T00:00:00+00:00")
    c._on_ha_state_event("binary_sensor.door", {"state": "off", "attributes": {}})
    assert sent[-1]["observed"]["binary_sensor.door"]
