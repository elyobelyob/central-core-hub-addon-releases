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


def test_fetch_sensors_filters_by_safe_device_class():
    """Test that fetch_sensors only includes sensors with safe device_class values."""
    mc = _load_module("mqtt_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "entity_id": "sensor.temp_living_room",
                    "state": "22.5",
                    "attributes": {"friendly_name": "Living Room Temperature", "device_class": "temperature"},
                },
                {
                    "entity_id": "binary_sensor.front_door",
                    "state": "off",
                    "attributes": {"friendly_name": "Front Door", "device_class": "door"},
                },
                {
                    "entity_id": "binary_sensor.motion_kitchen",
                    "state": "off",
                    "attributes": {"friendly_name": "Kitchen Motion", "device_class": "motion"},
                },
                {
                    "entity_id": "sensor.battery_phone",
                    "state": "85",
                    "attributes": {"friendly_name": "Phone Battery", "device_class": "battery"},
                },
                {
                    "entity_id": "sensor.energy_meter",
                    "state": "1250",
                    "attributes": {"friendly_name": "Energy Meter", "device_class": "energy"},
                },
                {
                    "entity_id": "binary_sensor.occupancy_bedroom",
                    "state": "on",
                    "attributes": {"friendly_name": "Bedroom Occupancy", "device_class": "occupancy"},
                },
                {
                    "entity_id": "binary_sensor.presence_home",
                    "state": "on",
                    "attributes": {"friendly_name": "Home Presence", "device_class": "presence"},
                },
                {
                    "entity_id": "binary_sensor.window_living_room",
                    "state": "off",
                    "attributes": {"friendly_name": "Living Room Window", "device_class": "opening"},
                },
                {
                    "entity_id": "sensor.air_quality",
                    "state": "42",
                    "attributes": {"friendly_name": "Air Quality", "device_class": "aqi"},
                },
                # Unsafe sensors that should be filtered out
                {
                    "entity_id": "sensor.password_field",
                    "state": "secret123",
                    "attributes": {"friendly_name": "Password", "device_class": "password"},
                },
                {
                    "entity_id": "sensor.credit_card",
                    "state": "1234-5678-9012-3456",
                    "attributes": {"friendly_name": "Credit Card", "device_class": "payment"},
                },
                {
                    "entity_id": "sensor.no_device_class",
                    "state": "some_value",
                    "attributes": {"friendly_name": "No Device Class"},
                },
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    cast(Any, mc).requests = RClient()
    sensors = mc.fetch_sensors("http://ha", "tok")
    assert isinstance(sensors, list)
    
    # Verify safe sensors are included
    assert any(s["entity_id"] == "sensor.temp_living_room" for s in sensors), "Temperature sensor should be included"
    assert any(s["entity_id"] == "binary_sensor.front_door" for s in sensors), "Door sensor should be included"
    assert any(s["entity_id"] == "binary_sensor.motion_kitchen" for s in sensors), "Motion sensor should be included"
    assert any(s["entity_id"] == "sensor.battery_phone" for s in sensors), "Battery sensor should be included"
    assert any(s["entity_id"] == "sensor.energy_meter" for s in sensors), "Energy sensor should be included"
    assert any(s["entity_id"] == "binary_sensor.occupancy_bedroom" for s in sensors), "Occupancy sensor should be included"
    assert any(s["entity_id"] == "binary_sensor.presence_home" for s in sensors), "Presence sensor should be included"
    assert any(s["entity_id"] == "binary_sensor.window_living_room" for s in sensors), "Opening sensor should be included"
    assert any(s["entity_id"] == "sensor.air_quality" for s in sensors), "AQI sensor should be included"
    
    # Verify unsafe sensors are filtered out
    assert not any(s["entity_id"] == "sensor.password_field" for s in sensors), "Password sensor should be filtered out"
    assert not any(s["entity_id"] == "sensor.credit_card" for s in sensors), "Credit card sensor should be filtered out"
    assert not any(s["entity_id"] == "sensor.no_device_class" for s in sensors), "Sensor without device_class should be filtered out"
    
    # Verify total count
    assert len(sensors) == 9, f"Expected 9 safe sensors, got {len(sensors)}"


def test_ha_client_fetch_sensors_filters_by_device_class():
    """Test that ha_client.fetch_sensors also filters by device_class."""
    ha = _load_module("ha_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "entity_id": "sensor.temp_1",
                    "state": "20",
                    "attributes": {"device_class": "temperature"},
                },
                {
                    "entity_id": "sensor.humidity_1",
                    "state": "65",
                    "attributes": {"device_class": "humidity"},
                },
                {
                    "entity_id": "sensor.battery_1",
                    "state": "90",
                    "attributes": {"device_class": "battery"},
                },
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    sensors = ha.fetch_sensors("http://ha", "tok", requests_mod=RClient())
    assert isinstance(sensors, list)
    
    # Only temperature and battery should be included (safe device classes)
    assert any(s["entity_id"] == "sensor.temp_1" for s in sensors), "Temperature sensor should be included"
    assert any(s["entity_id"] == "sensor.battery_1" for s in sensors), "Battery sensor should be included"
    assert not any(s["entity_id"] == "sensor.humidity_1" for s in sensors), "Humidity sensor should be filtered out"
    assert len(sensors) == 2, f"Expected 2 safe sensors, got {len(sensors)}"
