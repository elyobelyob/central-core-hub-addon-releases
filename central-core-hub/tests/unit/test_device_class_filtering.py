import importlib.util
from pathlib import Path
from typing import Any, cast


def _load_module(name):
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_ha_client_filters_by_device_class():
    """Test that ha_client.fetch_sensors filters sensors by device_class."""
    ha_client = _load_module("ha_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "entity_id": "sensor.motion1",
                    "state": "on",
                    "attributes": {"device_class": "motion", "friendly_name": "Motion 1"},
                },
                {
                    "entity_id": "sensor.door1",
                    "state": "off",
                    "attributes": {"device_class": "door", "friendly_name": "Door 1"},
                },
                {
                    "entity_id": "sensor.presence1",
                    "state": "on",
                    "attributes": {"device_class": "presence", "friendly_name": "Presence 1"},
                },
                {
                    "entity_id": "sensor.temperature",
                    "state": "22.5",
                    "attributes": {"device_class": "temperature", "friendly_name": "Temperature"},
                },
                {
                    "entity_id": "sensor.no_device_class",
                    "state": "42",
                    "attributes": {"friendly_name": "No Class"},
                },
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    sensors = ha_client.fetch_sensors("http://ha", "tok", requests_mod=RClient())
    assert isinstance(sensors, list)
    
    # Check that motion, door, and presence sensors are included
    entity_ids = [s["entity_id"] for s in sensors]
    assert "sensor.motion1" in entity_ids
    assert "sensor.door1" in entity_ids
    assert "sensor.presence1" in entity_ids
    
    # Check that sensors without device_class are included
    assert "sensor.no_device_class" in entity_ids
    
    # Check that temperature sensor (non-allowed device_class) is excluded
    assert "sensor.temperature" not in entity_ids


def test_mqtt_client_filters_by_device_class():
    """Test that mqtt_client.fetch_sensors filters sensors by device_class."""
    mc = _load_module("mqtt_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "entity_id": "sensor.motion2",
                    "state": "on",
                    "attributes": {"device_class": "motion", "friendly_name": "Motion 2"},
                },
                {
                    "entity_id": "binary_sensor.door2",
                    "state": "off",
                    "attributes": {"device_class": "door", "friendly_name": "Door 2"},
                },
                {
                    "entity_id": "binary_sensor.presence2",
                    "state": "on",
                    "attributes": {"device_class": "presence", "friendly_name": "Presence 2"},
                },
                {
                    "entity_id": "sensor.humidity",
                    "state": "65",
                    "attributes": {"device_class": "humidity", "friendly_name": "Humidity"},
                },
                {
                    "entity_id": "sensor.plain",
                    "state": "value",
                    "attributes": {"friendly_name": "Plain"},
                },
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    cast(Any, mc).requests = RClient()
    sensors = mc.fetch_sensors("http://ha", "tok")
    assert isinstance(sensors, list)
    
    # Check that motion, door, and presence sensors are included
    entity_ids = [s["entity_id"] for s in sensors]
    assert "sensor.motion2" in entity_ids
    assert "binary_sensor.door2" in entity_ids
    assert "binary_sensor.presence2" in entity_ids
    
    # Check that sensors without device_class are included
    assert "sensor.plain" in entity_ids
    
    # Check that humidity sensor (non-allowed device_class) is excluded
    assert "sensor.humidity" not in entity_ids


def test_device_class_none_value_included():
    """Test that sensors with device_class explicitly set to None are included."""
    ha_client = _load_module("ha_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "entity_id": "sensor.explicit_none",
                    "state": "test",
                    "attributes": {"device_class": None, "friendly_name": "Explicit None"},
                },
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    sensors = ha_client.fetch_sensors("http://ha", "tok", requests_mod=RClient())
    assert isinstance(sensors, list)
    assert len(sensors) == 1
    assert sensors[0]["entity_id"] == "sensor.explicit_none"


def test_device_class_mixed_with_registry():
    """Test that device_class filtering works together with registry filtering."""
    mc = _load_module("mqtt_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "entity_id": "sensor.motion_allowed",
                    "state": "on",
                    "attributes": {"device_class": "motion"},
                },
                {
                    "entity_id": "sensor.temp_excluded",
                    "state": "20",
                    "attributes": {"device_class": "temperature"},
                },
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    cast(Any, mc).requests = RClient()
    sensors = mc.fetch_sensors("http://ha", "tok")
    
    # Even without registry filtering, device_class should work
    entity_ids = [s["entity_id"] for s in sensors]
    assert "sensor.motion_allowed" in entity_ids
    # temperature device_class should be filtered out
    assert "sensor.temp_excluded" not in entity_ids
