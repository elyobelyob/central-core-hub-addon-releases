"""Phones and location never leave the home.

Entities on mobile_app devices (or from the mobile_app platform), device
trackers, people, zones, geocoded location sensors and anything carrying
coordinates are left out of sensors/poll, sensors/set, the websocket and
REST publishes and the inventory, using one set of rules (privacy.py). When
the hub cannot read Home Assistant's registries it cannot tell which entities
are on phones, so it sends no sensors at all.
"""

import importlib
import json
import types

import pytest

import ha_client
import inventory
import privacy

pytestmark = pytest.mark.phone_guard

DEVICES = [
    {"id": "phone", "identifiers": [["mobile_app", "abc"]]},
    {"id": "plug", "identifiers": [["zha", "00:12:4b:00:00:00:00:02"]]},
]
ENTITIES = [
    {"ei": "sensor.pixel_battery_level", "di": "phone"},
    {"ei": "sensor.pixel_wifi_ssid", "di": "phone"},
    {"ei": "sensor.loose_phone_sensor", "di": None, "pl": "mobile_app"},
    {"ei": "sensor.plug_power", "di": "plug"},
]


class FakeListener:
    def __init__(self, connected=True, answer=True):
        self.connected, self.answer, self.calls = connected, answer, []

    def is_connected(self):
        return self.connected

    def request(self, payload, timeout=15.0):
        self.calls.append(payload["type"])
        if not self.answer:
            return None
        result = {"config/device_registry/list": DEVICES,
                  "config/entity_registry/list_for_display": {"entities": ENTITIES}}[payload["type"]]
        return {"success": True, "result": result}


def _state(eid, state="1", **attrs):
    return {"entity_id": eid, "state": state, "attributes": dict({"device_class": "power"}, **attrs)}


STATES = [_state("sensor.plug_power"), _state("sensor.pixel_battery_level"), _state("sensor.pixel_wifi_ssid"),
          _state("sensor.loose_phone_sensor"), _state("sensor.pixel_geocoded_location", "1 High St"),
          _state("sensor.car_position", "x", latitude=51.5, longitude=-0.1)]


# --- the rules ------------------------------------------------------------

@pytest.mark.parametrize("eid,attrs,expected", [
    ("device_tracker.pixel", None, True),
    ("person.nick", None, True),
    ("zone.home", None, True),
    ("sensor.pixel_geocoded_location", None, True),
    ("sensor.geocoded_location", None, True),
    ("sensor.car", {"latitude": 1.0}, True),
    ("sensor.car", {"longitude": 1.0}, True),
    ("sensor.hall_temperature", {"device_class": "temperature"}, False),
    ("binary_sensor.door", None, False),
    ("sensor.relocation_count", None, False),
    (None, None, True),
])
def test_location_entities(eid, attrs, expected):
    assert privacy.is_location_entity(eid, attrs) is expected


def test_phone_entities_by_device_and_platform():
    assert privacy.phone_entities(DEVICES, ENTITIES) == {
        "sensor.pixel_battery_level", "sensor.pixel_wifi_ssid", "sensor.loose_phone_sensor"}


def test_leaves_home_needs_a_known_phone_set():
    assert not privacy.leaves_home("sensor.plug_power", None, None)
    assert privacy.leaves_home("sensor.plug_power", None, frozenset())
    assert not privacy.leaves_home("sensor.pixel_wifi_ssid", None, frozenset({"sensor.pixel_wifi_ssid"}))


# --- the guard ------------------------------------------------------------

class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_guard_without_listener_knows_nothing():
    assert privacy.PhoneGuard(lambda: None).excluded() is None


def test_guard_does_not_wait_on_an_unconnected_socket():
    listener = FakeListener(connected=False)
    assert privacy.PhoneGuard(lambda: listener).excluded() is None
    assert listener.calls == []


def test_guard_reads_caches_and_refreshes():
    clock, listener = Clock(), FakeListener()
    guard = privacy.PhoneGuard(lambda: listener, ttl=300, clock=clock)
    assert "sensor.pixel_wifi_ssid" in guard.excluded()
    assert len(listener.calls) == 2
    guard.excluded()
    assert len(listener.calls) == 2  # cached
    clock.t += 301
    guard.excluded()
    assert len(listener.calls) == 4  # refreshed


def test_guard_backs_off_after_failure_and_drops_stale_sets():
    clock, listener = Clock(), FakeListener()
    guard = privacy.PhoneGuard(lambda: listener, ttl=300, max_stale=3600, retry=30, clock=clock)
    assert guard.excluded()
    listener.answer = False
    clock.t += 301
    assert guard.excluded()  # refresh failed: the last set is still used
    calls = len(listener.calls)
    clock.t += 10
    guard.excluded()
    assert len(listener.calls) == calls  # backing off
    clock.t += 3600
    assert guard.excluded() is None  # too old to trust
    assert guard.cached() is None


def test_guard_update_records_registries_read_elsewhere():
    guard = privacy.PhoneGuard(lambda: None)
    guard.update(DEVICES, ENTITIES)
    assert "sensor.pixel_battery_level" in guard.cached()


# --- the hub --------------------------------------------------------------

@pytest.fixture
def hub(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    monkeypatch.setattr(mc, "SENSOR_REGISTRY", tmp_path / "none.yaml")
    mc.reload_sensor_registry()
    c = mc.CentralCoreClient({"client_id": "hub1", "mqtt_host": "localhost"})
    c.ha_api_url, c.ha_api_token = "http://localhost:8123", "tok"
    sent = []
    monkeypatch.setattr(c, "_publish", lambda topic, payload, qos=0, persist=None: sent.append((topic, json.loads(payload))))
    c._ha_ws_listener = FakeListener()
    c._lines = lines
    return c, sent, mc


def _cmd(c, action, body, fetch):
    handlers = importlib.import_module("handlers")
    msg = types.SimpleNamespace(topic=f"hubs/hub1/v1/cmd/{action}", retain=False)
    handlers.handle_message(c, msg, json.dumps(body), fetch, None, None, None)


def _telemetry(c, sent):
    return [p for t, p in sent if t == c.preferred_sensors_topic]


def test_poll_leaves_out_phones_and_location(hub):
    c, sent, _ = hub
    _cmd(c, "sensors/poll", {"command_id": "p1", "payload": {"sensors": ["power"]}}, lambda u, t: list(STATES))
    assert list(_telemetry(c, sent)[-1]["data"]) == ["sensor.plug_power"]


def test_poll_sends_nothing_when_phones_cannot_be_told(hub):
    c, sent, _ = hub
    c._ha_ws_listener = FakeListener(answer=False)
    _cmd(c, "sensors/poll", {"command_id": "p1", "payload": {"sensors": ["power"]}}, lambda u, t: list(STATES))
    assert _telemetry(c, sent)[-1]["data"] == {}
    assert any("exclude phones" in m for m in c._lines)


def test_set_refuses_phone_and_location_entities(hub):
    c, sent, _ = hub
    wanted = ["sensor.plug_power", "sensor.pixel_wifi_ssid", "sensor.pixel_geocoded_location"]
    _cmd(c, "sensors/set", {"command_id": "s1", "payload": {"sensors": wanted}}, lambda u, t: list(STATES))
    assert c.selected_sensors == ["sensor.plug_power"]
    done = [p for t, p in sent if p.get("status") == "completed"][-1]
    assert sorted(done["result"]["rejected"]) == ["sensor.pixel_geocoded_location", "sensor.pixel_wifi_ssid"]
    assert list(done["result"]["data"]) == ["sensor.plug_power"]


def test_set_keeps_the_old_selection_when_phones_cannot_be_told(hub):
    c, sent, _ = hub
    c.selected_sensors = ["sensor.plug_power"]
    c._ha_ws_listener = FakeListener(answer=False)
    _cmd(c, "sensors/set", {"command_id": "s1", "payload": {"sensors": ["sensor.pixel_wifi_ssid"]}},
         lambda u, t: list(STATES))
    assert c.selected_sensors == ["sensor.plug_power"]
    final = [p for t, p in sent if p.get("status") == "failed"][-1]
    assert final["result"]["reason"] == "ha_registry_unavailable"


def test_websocket_paths_use_the_known_set_only(hub):
    c, sent, _ = hub
    c.selected_sensors = ["sensor.plug_power", "sensor.pixel_wifi_ssid", "sensor.car_position"]
    # nothing known yet, and the websocket thread must not ask: nothing sent
    c._on_ha_state_event("sensor.plug_power", _state("sensor.plug_power"))
    assert sent == [] and c._ha_ws_listener.calls == []
    c.phones.excluded()  # learnt on another thread
    c._on_ha_state_event("sensor.pixel_wifi_ssid", _state("sensor.pixel_wifi_ssid", "HomeWifi"))
    c._on_ha_state_event("sensor.car_position", _state("sensor.car_position", "x", latitude=1.0))
    assert sent == []
    c._on_ha_state_event("sensor.plug_power", _state("sensor.plug_power"))
    assert list(_telemetry(c, sent)[-1]["data"]) == ["sensor.plug_power"]
    sent.clear()
    c._on_ha_snapshot([_state("sensor.pixel_wifi_ssid", "Other"), _state("sensor.plug_power", "2")])
    assert list(_telemetry(c, sent)[-1]["data"]) == ["sensor.plug_power"]


def test_startup_and_hourly_publishes_leave_out_phones(hub, monkeypatch):
    c, sent, mc = hub
    monkeypatch.setattr(mc, "fetch_sensors", lambda u, t: [dict(s) for s in STATES])
    c.safe_device_classes = []
    c.publish_sensors_with_default_filter()
    assert list(_telemetry(c, sent)[-1]["data"]) == ["sensor.plug_power"]
    c.publish_sensors()
    assert [s["entity_id"] for s in _telemetry(c, sent)[-1]["sensors"]] == ["sensor.plug_power"]


def test_fetch_functions_drop_location_before_stripping_coordinates(hub, monkeypatch):
    c, sent, mc = hub

    class R:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self.body

    monkeypatch.setattr(mc, "requests", types.SimpleNamespace(get=lambda *a, **k: R([dict(s) for s in STATES])))
    ids = [s["entity_id"] for s in mc.fetch_sensors("http://localhost:8123", "tok")]
    assert "sensor.pixel_geocoded_location" not in ids and "sensor.car_position" not in ids
    by_id = {s["entity_id"]: s for s in STATES}
    req = types.SimpleNamespace(get=lambda url, **k: R(by_id[url.rsplit("/", 1)[1]]))
    out = ha_client.fetch_sensors_by_ids("http://localhost:8123", "tok",
                                         ["sensor.car_position", "sensor.plug_power"], requests_mod=req)
    assert [s["entity_id"] for s in out] == ["sensor.plug_power"]


def test_inventory_uses_the_same_rules():
    class L:
        def request(self, payload, timeout=15.0):
            result = {"config/device_registry/list": DEVICES + [
                          {"id": "car", "identifiers": [["tesla", "x"]]}],
                      "config/entity_registry/list_for_display": {"entities": ENTITIES + [
                          {"ei": "sensor.car_geocoded_location", "di": "car"},
                          {"ei": "sensor.car_battery", "di": "car"},
                          {"ei": "sensor.phone_extra", "di": "plug", "pl": "mobile_app"}]},
                      }.get(payload["type"], [])
            return {"success": True, "result": result}

    report = inventory.collect(L(), "2.2.1", None, "now")
    entities = {e for d in report["devices"] for e in d["entities"]}
    assert entities == {"sensor.plug_power", "sensor.car_battery"}


def test_stand_in_client_without_guard_still_drops_location():
    handlers = importlib.import_module("handlers")
    c = types.SimpleNamespace(client_id="hub1", ha_api_url="http://localhost:8123", ha_api_token="tok")
    assert [s["entity_id"] for s in handlers._privacy_filter(c, list(STATES))] == [
        "sensor.plug_power", "sensor.pixel_battery_level", "sensor.pixel_wifi_ssid", "sensor.loose_phone_sensor"]


def test_main_loop_keeps_the_phone_set_for_the_websocket_thread(hub, monkeypatch):
    c, sent, _ = hub
    for name in ("publish_telemetry", "publish_selected_sensor_changes", "_flush_outbox", "publish_sensors"):
        monkeypatch.setattr(c, name, lambda *a, **k: None)
    c._connected = True
    assert c.phones.cached() is None
    c.run_iteration()
    assert "sensor.pixel_wifi_ssid" in c.phones.cached()
    c.selected_sensors = ["sensor.plug_power"]
    c._on_ha_state_event("sensor.plug_power", _state("sensor.plug_power"))
    assert list(_telemetry(c, sent)[-1]["data"]) == ["sensor.plug_power"]
