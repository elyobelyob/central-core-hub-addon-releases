"""inventory: later pages, refused page numbers, device caps, odd identifiers."""

import json

import pytest

import inventory as inv


class _Listener:
    def __init__(self, devices, entities, zha=()):
        self.result = {
            "config/device_registry/list": devices,
            "config/entity_registry/list_for_display": {"entities": entities},
            "config/floor_registry/list": [],
            "config/area_registry/list": [],
            "zha/devices": list(zha),
        }

    def request(self, payload, timeout=15.0):
        return {"success": True, "result": self.result[payload["type"]]}


def _device(i, **kw):
    d = {"id": f"d{i}", "name": f"Sensor {i}", "manufacturer": "M", "model": "X", "area_id": None,
         "identifiers": [["zha", f"00:00:00:00:00:00:{i // 256:02x}:{i % 256:02x}"]],
         "disabled_by": None, "entry_type": None}
    d.update(kw)
    return d


def test_stack_skips_malformed_identifiers_and_unknown_integrations():
    assert inv._stack([[], ["zha"], None, ["hue", "x"], ["mqtt", "not-z2m"]]) == (None, None)
    assert inv._stack([["zha"], ["zha", "AA:BB:CC:DD:EE:FF:00:11"]]) == ("zha", "aabbccddeeff0011")


def test_device_with_no_kept_entities_is_left_out_unless_coordinator():
    devices = [
        _device(1, identifiers=[["zha", "00:00:00:00:00:00:00:01"]]),  # no entities, not coordinator
        _device(2, identifiers=[["zha", "00:00:00:00:00:00:00:02"]]),  # no entities, coordinator
        _device(3),
    ]
    entities = [{"ei": "binary_sensor.door_3", "di": "d3"}, {"ei": "light.lamp", "di": "d1"}]
    zha = [{"ieee": "00:00:00:00:00:00:00:02", "device_type": "Coordinator"}]
    report = inv.collect(_Listener(devices, entities, zha), "1", "2026.1", "now")
    assert [d["ha_id"] for d in report["devices"]] == ["d2", "d3"]


def test_device_list_is_capped(monkeypatch):
    monkeypatch.setattr(inv, "MAX_DEVICES", 3)
    devices = [_device(i) for i in range(10)]
    entities = [{"ei": f"sensor.s{i}", "di": f"d{i}"} for i in range(10)]
    report = inv.collect(_Listener(devices, entities), "1", "2026.1", "now")
    assert [d["ha_id"] for d in report["devices"]] == ["d0", "d1", "d2"]


def _big_listener(n=600):
    devices = [_device(i, name="N" * 80, manufacturer="M" * 80, model="X" * 80) for i in range(n)]
    entities = [{"ei": f"sensor.{'s' * 60}_{i}", "di": f"d{i}"} for i in range(n)]
    return _Listener(devices, entities)


def test_later_pages_come_from_the_stored_run(monkeypatch):
    monkeypatch.setattr(inv, "PAGE_CHARS", 4096)
    runs = inv.RunStore()
    listener = _big_listener(60)
    first = inv.answer({"command_id": "c9", "payload": {"part": 1}}, listener, "1", "2026.1", "now", runs=runs)
    assert first["part"] == 1 and first["parts"] > 1

    pieces = [first["data"]]
    for part in range(2, first["parts"] + 1):
        # listener None: later pages never go back to Home Assistant
        res = inv.answer({"command_id": f"x{part}", "payload": {"part": part, "run": "c9"}},
                         None, "1", "2026.1", "now", runs=runs)
        assert (res["run"], res["part"], res["parts"]) == ("c9", part, first["parts"])
        pieces.append(res["data"])
    report = json.loads("".join(pieces))
    assert len(report["devices"]) == 60


def test_page_past_the_end_is_refused(monkeypatch):
    runs = inv.RunStore()
    runs.put("r1", ["only"])
    with pytest.raises(inv.InventoryError, match="no_such_part"):
        inv.answer({"payload": {"part": 2, "run": "r1"}}, None, "1", "2026.1", "now", runs=runs)


def test_page_for_unknown_run_is_refused():
    with pytest.raises(inv.InventoryError, match="run_expired"):
        inv.answer({"payload": {"part": 2, "run": "gone"}}, None, "1", "2026.1", "now", runs=inv.RunStore())


def test_report_too_large_is_refused_and_slot_freed(monkeypatch):
    monkeypatch.setattr(inv, "PAGE_CHARS", 1024)
    monkeypatch.setattr(inv, "MAX_PARTS", 2)
    runs = inv.RunStore()
    with pytest.raises(inv.InventoryError, match="too_large"):
        inv.answer({"command_id": "c1", "payload": {"part": 1}}, _big_listener(40), "1", "2026.1", "now", runs=runs)
    assert runs.get("c1") is None
    assert runs.begin("") is not None  # the collection slot was released
