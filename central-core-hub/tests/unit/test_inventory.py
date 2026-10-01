"""cmd/inventory/get: a paged, read-only device inventory for the vault's floor plans."""
import json

import inventory as inv

FLOORS = [{"floor_id": "ground", "name": "Ground", "level": 0, "aliases": ["x"]}]
AREAS = [{"area_id": "hallway", "name": "Hallway", "floor_id": "ground", "picture": "/x.png"}]
DEVICES = [
    {"id": "d1", "name": "Hallway Plug", "name_by_user": None, "manufacturer": "_TZ3000", "model": "TS011F",
     "area_id": "hallway", "identifiers": [["zha", "00:12:4b:00:00:00:00:02"]], "disabled_by": None,
     "entry_type": None},
    {"id": "d2", "name": "Lounge Motion", "name_by_user": "Lounge PIR", "manufacturer": "Aqara", "model": "RTCGQ11LM",
     "area_id": None, "identifiers": [["mqtt", "zigbee2mqtt_0x00124b0000000003"]], "disabled_by": None,
     "entry_type": None},
    {"id": "d3", "name": "Pixel", "manufacturer": "Google", "model": "Pixel", "area_id": None,
     "identifiers": [["mobile_app", "abc"]], "disabled_by": None, "entry_type": None},
    {"id": "d4", "name": "Sun", "manufacturer": None, "model": None, "area_id": None,
     "identifiers": [["sun", "x"]], "disabled_by": None, "entry_type": "service"},
    {"id": "d5", "name": "Hive", "manufacturer": "Hive", "model": "SLT6", "area_id": None,
     "identifiers": [["hive", "y"]], "disabled_by": None, "entry_type": None},
]
ENTITIES = [
    {"ei": "switch.hallway_plug", "di": "d1"},
    {"ei": "sensor.hallway_plug_power", "di": "d1", "ai": "kitchen"},
    {"ei": "binary_sensor.lounge_motion", "di": "d2"},
    {"ei": "sensor.lounge_motion_battery", "di": "d2", "hb": True},
    {"ei": "device_tracker.pixel", "di": "d3"},
    {"ei": "sensor.pixel_battery", "di": "d3"},
    {"ei": "sensor.sun_next_dawn", "di": "d4"},
    {"ei": "climate.hive", "di": "d5"},
    {"ei": "light.hive_bulb", "di": "d5"},
]
ZHA = [
    {"ieee": "00:12:4b:00:00:00:00:01", "device_type": "Coordinator", "lqi": None, "rssi": 0, "available": True,
     "last_seen": "2026-10-01T01:00:00", "neighbors": [{"ieee": "00:12:4b:00:00:00:00:02", "lqi": "30",
                                                         "relationship": "Sibling"}], "device_reg_id": "d0"},
    {"ieee": "00:12:4b:00:00:00:00:02", "device_type": "Router", "lqi": 20, "rssi": -95, "available": True,
     "last_seen": "2026-10-01T01:00:00", "neighbors": [], "device_reg_id": "d1"},
]


class FakeListener:
    def __init__(self, deny=(), missing=()):
        self.deny, self.missing, self.sent = set(deny), set(missing), []

    def request(self, payload, timeout=15.0):
        self.sent.append(payload["type"])
        kind = payload["type"]
        if kind in self.deny:
            return {"success": False, "error": {"code": "unauthorized"}}
        if kind in self.missing:
            return {"success": False, "error": {"code": "unknown_command"}}
        result = {"config/floor_registry/list": FLOORS, "config/area_registry/list": AREAS,
                  "config/device_registry/list": DEVICES,
                  "config/entity_registry/list_for_display": {"entities": ENTITIES},
                  "zha/devices": ZHA}[kind]
        return {"success": True, "result": result}


def _report(**kw):
    return inv.collect(FakeListener(**kw), addon_version="2.2.0", ha_version="2026.9.4", now="2026-10-01T02:00:00Z")


def test_should_send_five_domains_when_listing_entities():
    devices = {d["name"]: d for d in _report()["devices"]}
    assert devices["Hallway Plug"]["entities"] == ["sensor.hallway_plug_power", "switch.hallway_plug"]
    assert devices["Hive"]["entities"] == ["climate.hive"]


def test_should_drop_phones_services_and_empty_devices():
    names = {d["name"] for d in _report()["devices"]}
    assert "Pixel" not in names and "Sun" not in names


def test_should_use_names_area_and_stack_when_building_devices():
    devices = {d["ha_id"]: d for d in _report()["devices"]}
    assert devices["d1"] == {"ha_id": "d1", "name": "Hallway Plug", "manufacturer": "_TZ3000", "model": "TS011F",
                             "area": "hallway", "stack": "zha", "ieee": "00124b0000000002",
                             "entities": ["sensor.hallway_plug_power", "switch.hallway_plug"]}
    assert devices["d2"]["name"] == "Lounge PIR" and devices["d2"]["stack"] == "z2m"
    assert devices["d2"]["ieee"] == "00124b0000000003"


def test_should_keep_only_safe_registry_fields():
    r = _report()
    assert r["floors"] == [{"floor_id": "ground", "name": "Ground", "level": 0}]
    assert r["areas"] == [{"area_id": "hallway", "name": "Hallway", "floor_id": "ground"}]


def test_should_read_zha_neighbours_when_zha_loaded():
    nodes = {n["ieee"]: n for n in _report()["zigbee"]["nodes"]}
    coord = nodes["00124b0000000001"]
    assert coord["type"] == "Coordinator" and coord["rssi"] is None
    assert coord["neighbours"] == [{"ieee": "00124b0000000002", "lqi": 30, "relationship": "Sibling"}]


def test_should_note_error_and_carry_on_when_zha_missing():
    r = _report(missing={"zha/devices"})
    assert r["zigbee"]["nodes"] == [] and r["errors"]["zha/devices"] == "unknown_command"
    assert r["devices"]


def test_should_fail_when_registry_refused():
    try:
        _report(deny={"config/device_registry/list"})
    except inv.InventoryError as e:
        assert str(e) == "token_not_admin"
    else:
        raise AssertionError("expected InventoryError")


def test_should_apply_privacy_filter_when_given():
    r = inv.collect(FakeListener(), addon_version="2.2.0", ha_version=None, now="x",
                    allowed=lambda e: not e.startswith("sensor."))
    devices = {d["name"]: d for d in r["devices"]}
    assert devices["Hallway Plug"]["entities"] == ["switch.hallway_plug"]


def test_should_drop_zigbee_nodes_and_links_of_devices_the_registry_hides():
    # every entity of the hallway plug (ieee ...02, device d1) is denied
    r = inv.collect(FakeListener(), addon_version="2.2.0", ha_version=None, now="x",
                    allowed=lambda e: "hallway_plug" not in e)
    assert "Hallway Plug" not in {d["name"] for d in r["devices"]}
    nodes = {n["ieee"]: n for n in r["zigbee"]["nodes"]}
    assert "00124b0000000002" not in nodes
    assert nodes["00124b0000000001"]["neighbours"] == []  # the coordinator's link to it is gone too
    assert "00124b0000000002" not in json.dumps(r)


def test_should_hide_a_zigbee_node_matched_by_ieee_without_device_reg_id():
    zha = [dict(z, device_reg_id=None) for z in ZHA]

    class L(FakeListener):
        def request(self, payload, timeout=15.0):
            reply = super().request(payload, timeout)
            return {"success": True, "result": zha} if payload["type"] == "zha/devices" else reply

    r = inv.collect(L(), addon_version="2.2.0", ha_version=None, now="x", allowed=lambda e: "hallway_plug" not in e)
    assert [n["ieee"] for n in r["zigbee"]["nodes"]] == ["00124b0000000001"]


def test_should_keep_zigbee_nodes_when_some_entities_are_allowed():
    r = inv.collect(FakeListener(), addon_version="2.2.0", ha_version=None, now="x",
                    allowed=lambda e: not e.startswith("sensor."))
    nodes = {n["ieee"]: n for n in r["zigbee"]["nodes"]}
    assert "00124b0000000002" in nodes
    assert nodes["00124b0000000001"]["neighbours"][0]["ieee"] == "00124b0000000002"


def test_should_never_send_location_or_states():
    text = json.dumps(_report())
    for word in ("latitude", "longitude", "state", "attributes", "picture"):
        assert word not in text


def test_should_keep_results_under_256_kib_when_report_is_large():
    big = {"devices": [{"name": "x" * 200, "entities": ["sensor.y" * 20]} for _ in range(3000)]}
    pages = inv.pages(big)
    assert len(pages) > 1
    assert all(len(json.dumps({"run": "r", "part": 1, "parts": len(pages), "data": p})) < 256 * 1024 for p in pages)
    assert json.loads("".join(pages)) == big


def test_should_fail_run_expired_when_run_unknown():
    store = inv.RunStore(ttl=600, clock=lambda: 0.0)
    assert store.get("nope") is None
    store.put("abc", ["a", "b"])
    assert store.get("abc") == ["a", "b"]
    later = inv.RunStore(ttl=600, clock=lambda: 0.0)
    later._runs = store._runs
    later._clock = lambda: 601.0
    assert later.get("abc") is None


class FakeClient:
    client_id = "hub-test"

    def __init__(self, listener):
        self._ha_ws_listener = listener
        self._ha_version_cache = "2026.9.4"
        self.published = []

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"

    def _publish(self, topic, payload, qos=0, persist=None):
        self.published.append((topic, json.loads(payload), persist))


def test_should_answer_pages_when_command_arrives():
    import handlers
    client = FakeClient(FakeListener())
    handlers._handle_inventory(client, json.dumps({"command_id": "c1", "payload": {"part": 1}}))
    topic, done, persist = client.published[-1]
    assert topic == "hubs/hub-test/v1/ack/inventory.get/c1" and persist is False
    assert done["status"] == "completed" and done["result"]["run"] == "c1"
    report = json.loads(done["result"]["data"]) if done["result"]["parts"] == 1 else None
    assert report and report["devices"]


def test_should_fail_with_reason_when_ha_unreachable():
    import handlers
    client = FakeClient(None)
    handlers._handle_inventory(client, json.dumps({"command_id": "c2", "payload": {}}))
    assert client.published[-1][1] == {"status": "failed", "result": {"reason": "ha_unreachable"},
                                       "timestamp": client.published[-1][1]["timestamp"]}


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_run_store_keeps_at_most_three_runs():
    clock = _Clock()
    store = inv.RunStore(ttl=600, clock=clock)
    for i in range(5):
        clock.t = float(i)
        store.put(f"r{i}", [str(i)])
    assert [store.get(f"r{i}") for i in range(5)] == [None, None, ["2"], ["3"], ["4"]]


def test_run_store_refuses_a_second_collection_for_the_same_hub():
    clock = _Clock()
    store = inv.RunStore(clock=clock)
    first = store.begin("hub1")
    assert first is not None
    assert store.begin("hub1") is None
    assert store.begin("hub2") is not None  # another hub is independent
    clock.t = 59.9
    assert store.begin("hub1") is None
    store.end("hub1", first)
    assert store.begin("hub1") is not None


def test_run_store_lets_a_stuck_collection_be_overtaken():
    clock = _Clock()
    store = inv.RunStore(clock=clock)
    stuck = store.begin("hub1")
    clock.t = 61
    fresh = store.begin("hub1")
    assert fresh is not None
    store.end("hub1", stuck)  # the stuck one finishing does not free the fresh one's slot
    assert store.begin("hub1") is None
    store.end("hub1", fresh)
    assert store.begin("hub1") is not None


def test_answer_refuses_part_one_while_a_collection_is_running():
    store = inv.RunStore()
    store.begin("hub1")
    try:
        inv.answer({"command_id": "c2", "payload": {}}, FakeListener(), "2.2.1", None, "x", runs=store, hub="hub1")
    except inv.InventoryError as e:
        assert str(e) == "busy"
    else:
        raise AssertionError("expected busy")


def test_answer_frees_the_slot_when_collection_fails():
    store = inv.RunStore()
    for _ in range(2):
        try:
            inv.answer({"command_id": "c", "payload": {}}, FakeListener(deny={"config/device_registry/list"}),
                       "2.2.1", None, "x", runs=store, hub="hub1")
        except inv.InventoryError as e:
            assert str(e) == "token_not_admin"


class _SlowListener(FakeListener):
    """Each answer takes `cost` seconds of a fake clock; records the timeouts asked for."""

    def __init__(self, clock, cost, **kw):
        super().__init__(**kw)
        self.clock, self.cost, self.timeouts = clock, cost, []

    def request(self, payload, timeout=15.0):
        self.timeouts.append(timeout)
        if self.cost >= timeout:
            self.clock.t += timeout
            return None
        self.clock.t += self.cost
        return super().request(payload, timeout)


def test_collect_stops_optional_reads_at_the_deadline():
    clock = _Clock()
    listener = _SlowListener(clock, cost=14)
    r = inv.collect(listener, "2.2.1", None, "x", deadline_s=45, clock=clock)
    # 14 + 14 + 14 = 42 s; the fourth read gets the 3 s left and times out; the fifth is not sent
    assert listener.timeouts == [15, 15, 15, 3]
    assert r["errors"] == {"config/area_registry/list": "timeout", "zha/devices": "timeout"}
    assert clock.t <= 45


def test_collect_fails_with_timeout_when_a_required_read_runs_out_of_time():
    clock = _Clock()
    listener = _SlowListener(clock, cost=14)
    try:
        inv.collect(listener, "2.2.1", None, "x", deadline_s=20, clock=clock)
    except inv.InventoryError as e:
        assert str(e) == "timeout"
    else:
        raise AssertionError("expected timeout")
    assert listener.timeouts == [15, 6]  # the entity registry read gets only what is left
    assert clock.t <= 20


def test_collect_reports_unreachable_not_timeout_when_time_is_left():
    try:
        inv.collect(type("L", (), {"request": lambda self, p, timeout=15.0: None})(), "2.2.1", None, "x")
    except inv.InventoryError as e:
        assert str(e) == "ha_unreachable"
