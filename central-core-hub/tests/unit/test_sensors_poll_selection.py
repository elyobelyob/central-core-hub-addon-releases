"""sensors/poll reports sensors; it must not change the watch list.

It used to store its request (device-class names such as "door") as
client.selected_sensors, after which the websocket filter and the change
publisher matched nothing.
"""

import json
import types

import handlers

STATES = [
    {"entity_id": "binary_sensor.front", "state": "off", "attributes": {"device_class": "door"}},
    {"entity_id": "sensor.temp", "state": "21", "attributes": {"device_class": "temperature"}},
    {"entity_id": "sensor.power", "state": "5", "attributes": {}},
]


def _client():
    published = []
    c = types.SimpleNamespace(
        client_id="hub1",
        ha_api_url="http://ha",
        ha_api_token="tok",
        selected_sensors=["sensor.temp", "sensor.battery"],
        preferred_sensors_topic="hubs/hub1/v1/telemetry/sensors",
    )
    c.build_ack_topic = lambda action, cid: f"hubs/hub1/v1/ack/{action.replace('/', '.')}/{cid}"
    c._publish = lambda topic, payload, qos=0: published.append((topic, json.loads(payload)))
    return c, published


def _poll(c, sensors, cid="p1"):
    msg = types.SimpleNamespace(topic="hubs/hub1/v1/cmd/sensors/poll", retain=False)
    body = json.dumps({"command_id": cid, "payload": {"sensors": sensors}})
    handlers.handle_message(c, msg, body, lambda u, t: [dict(s) for s in STATES], None, None, None)


def test_poll_does_not_touch_the_selection():
    c, _ = _client()
    _poll(c, ["door"])
    assert c.selected_sensors == ["sensor.temp", "sensor.battery"]


def test_poll_by_device_class():
    c, published = _client()
    _poll(c, ["Door"])
    tele = [p for t, p in published if t == c.preferred_sensors_topic][-1]
    assert list(tele["data"]) == ["binary_sensor.front"]
    done = [p for t, p in published if p.get("status") == "completed"][-1]
    assert done["result"]["sensors_reported"] == ["binary_sensor.front"]
    assert done["result"]["device_classes"] == {"binary_sensor.front": "door"}


def test_poll_by_entity_id():
    # the vault's admin endpoint documents entity ids ({"sensors": ["sensor1", ...]})
    c, published = _client()
    _poll(c, ["sensor.power", "temperature"])
    tele = [p for t, p in published if t == c.preferred_sensors_topic][-1]
    assert sorted(tele["data"]) == ["sensor.power", "sensor.temp"]
