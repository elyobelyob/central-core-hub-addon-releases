"""Perf #13: SENSOR_REGISTRY.yaml is parsed once per change, not on every fetch."""

import importlib
import json
import types

import pytest


@pytest.fixture
def mc(monkeypatch, tmp_path):
    mod = importlib.import_module("mqtt_client")
    reg = tmp_path / "SENSOR_REGISTRY.yaml"
    reg.write_text(
        json.dumps(
            {
                "registry_mode": "deny",
                "entries": [
                    {"entity_id": "sensor.private_*", "provide": False},
                    {"entity_id": "sensor.plain", "provide": True, "device_class": "power"},
                ],
            }
        )
    )
    monkeypatch.setattr(mod, "SENSOR_REGISTRY", reg)
    mod.reload_sensor_registry()
    yield mod, reg
    mod.reload_sensor_registry()


def _states():
    class _R:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"entity_id": "sensor.private_x", "state": "1", "attributes": {"device_class": "power"}},
                {"entity_id": "sensor.plain", "state": "2", "attributes": {}},
                {"entity_id": "sensor.ok", "state": "3", "attributes": {"device_class": "power"}},
            ]

    return types.SimpleNamespace(get=lambda *a, **k: _R())


def test_fetch_sensors_parses_the_registry_once(mc, monkeypatch):
    mod, reg = mc
    yaml = importlib.import_module("yaml")
    real = yaml.safe_load
    parses = []
    monkeypatch.setattr(yaml, "safe_load", lambda f: parses.append(1) or real(f))
    monkeypatch.setattr(mod, "requests", _states())
    mod.reload_sensor_registry()  # parses once
    for _ in range(3):
        out = mod.fetch_sensors("http://ha", "tok")
        assert [s["entity_id"] for s in out] == ["sensor.plain", "sensor.ok"]
        assert out[0]["device_class"] == "power"
        assert mod.is_entity_allowed("sensor.private_y") is False
    assert len(parses) == 1


def test_reload_rereads_both_views(mc):
    mod, reg = mc
    assert mod.is_entity_allowed("sensor.private_y") is False
    assert mod.list_monitored_sensors() == ["sensor.plain"]
    reg.write_text(json.dumps({"registry_mode": "deny", "entries": []}))
    mod.reload_sensor_registry()
    assert mod.is_entity_allowed("sensor.private_y") is True
    assert mod.list_monitored_sensors() == []
