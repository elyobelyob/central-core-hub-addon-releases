#!/usr/bin/env python3
"""
Tests for device_class filtering in sensor fetching.
"""

import importlib.util
import sys
import pathlib


def _load_module(name, path):
    """Dynamically load a Python module from a given path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_default_safe_device_classes():
    """Test that DEFAULT_SAFE_DEVICE_CLASSES contains expected values."""
    mqtt_client_path = pathlib.Path(__file__).parent.parent.parent / "mqtt_client.py"
    mqtt = _load_module("mqtt_client_test", str(mqtt_client_path))
    
    assert hasattr(mqtt, "DEFAULT_SAFE_DEVICE_CLASSES")
    safe_classes = mqtt.DEFAULT_SAFE_DEVICE_CLASSES
    
    # Verify default classes
    expected_classes = [
        "temperature",
        "motion",
        "door",
        "battery",
        "occupancy",
        "presence",
        "opening",
        "aqi",
        "energy",
    ]
    
    assert isinstance(safe_classes, list)
    for cls in expected_classes:
        assert cls in safe_classes, f"Expected {cls} to be in default safe device classes"


def test_fetch_sensors_filters_by_device_class():
    """Test that fetch_sensors filters sensors based on device_class."""
    mqtt_client_path = pathlib.Path(__file__).parent.parent.parent / "mqtt_client.py"
    mqtt = _load_module("mqtt_client_filter_test", str(mqtt_client_path))
    
    # Mock requests module
    class MockResponse:
        def __init__(self, json_data):
            self._json_data = json_data
        
        def raise_for_status(self):
            pass
        
        def json(self):
            return self._json_data
    
    class MockRequests:
        @staticmethod
        def get(url, headers=None, timeout=None):
            # Return sensors with various device_classes
            return MockResponse([
                {
                    "entity_id": "sensor.temp_living_room",
                    "state": "22.5",
                    "attributes": {
                        "device_class": "temperature",
                        "friendly_name": "Living Room Temperature"
                    },
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
                {
                    "entity_id": "sensor.motion_hallway",
                    "state": "on",
                    "attributes": {
                        "device_class": "motion",
                        "friendly_name": "Hallway Motion"
                    },
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
                {
                    "entity_id": "sensor.power_usage",
                    "state": "1500",
                    "attributes": {
                        "device_class": "power",
                        "friendly_name": "Power Usage"
                    },
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
                {
                    "entity_id": "sensor.no_device_class",
                    "state": "value",
                    "attributes": {
                        "friendly_name": "No Device Class Sensor"
                    },
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
                {
                    "entity_id": "sensor.battery_level",
                    "state": "85",
                    "attributes": {
                        "device_class": "battery",
                        "friendly_name": "Battery Level"
                    },
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
            ])
    
    # Replace requests in mqtt module
    mqtt.requests = MockRequests()
    
    # Mock _load_sensor_registry to return empty list (no registry filtering)
    mqtt._load_sensor_registry = lambda: []
    
    # Call fetch_sensors with default safe classes
    sensors = mqtt.fetch_sensors("http://test", "token", mqtt.DEFAULT_SAFE_DEVICE_CLASSES)
    
    assert sensors is not None
    # Should include temperature, motion, battery, and no_device_class (sensors without device_class pass through)
    # Should exclude power
    entity_ids = [s["entity_id"] for s in sensors]
    
    assert "sensor.temp_living_room" in entity_ids
    assert "sensor.motion_hallway" in entity_ids
    assert "sensor.battery_level" in entity_ids
    assert "sensor.no_device_class" in entity_ids
    assert "sensor.power_usage" not in entity_ids


def test_fetch_sensors_with_custom_safe_classes():
    """Test fetch_sensors with custom safe device classes."""
    mqtt_client_path = pathlib.Path(__file__).parent.parent.parent / "mqtt_client.py"
    mqtt = _load_module("mqtt_client_custom_test", str(mqtt_client_path))
    
    # Mock requests module
    class MockResponse:
        def __init__(self, json_data):
            self._json_data = json_data
        
        def raise_for_status(self):
            pass
        
        def json(self):
            return self._json_data
    
    class MockRequests:
        @staticmethod
        def get(url, headers=None, timeout=None):
            return MockResponse([
                {
                    "entity_id": "sensor.temp",
                    "state": "22",
                    "attributes": {"device_class": "temperature"},
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
                {
                    "entity_id": "sensor.power",
                    "state": "1500",
                    "attributes": {"device_class": "power"},
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
            ])
    
    mqtt.requests = MockRequests()
    
    # Mock _load_sensor_registry to return empty list (no registry filtering)
    mqtt._load_sensor_registry = lambda: []
    
    # Allow only power
    custom_safe_classes = ["power"]
    sensors = mqtt.fetch_sensors("http://test", "token", custom_safe_classes)
    
    assert sensors is not None
    entity_ids = [s["entity_id"] for s in sensors]
    
    # Only power should be included
    assert "sensor.power" in entity_ids
    assert "sensor.temp" not in entity_ids


def test_fetch_sensors_without_device_class_passes():
    """Test that sensors without device_class attribute are allowed through."""
    mqtt_client_path = pathlib.Path(__file__).parent.parent.parent / "mqtt_client.py"
    mqtt = _load_module("mqtt_client_noclass_test", str(mqtt_client_path))
    
    # Mock requests module
    class MockResponse:
        def __init__(self, json_data):
            self._json_data = json_data
        
        def raise_for_status(self):
            pass
        
        def json(self):
            return self._json_data
    
    class MockRequests:
        @staticmethod
        def get(url, headers=None, timeout=None):
            return MockResponse([
                {
                    "entity_id": "sensor.custom_sensor",
                    "state": "value",
                    "attributes": {"friendly_name": "Custom"},
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
            ])
    
    mqtt.requests = MockRequests()
    
    # Mock _load_sensor_registry to return empty list (no registry filtering)
    mqtt._load_sensor_registry = lambda: []
    
    sensors = mqtt.fetch_sensors("http://test", "token", ["temperature"])
    
    assert sensors is not None
    assert len(sensors) == 1
    assert sensors[0]["entity_id"] == "sensor.custom_sensor"


def test_central_core_client_loads_safe_device_classes():
    """Test that CentralCoreClient loads safe_device_classes from options."""
    mqtt_client_path = pathlib.Path(__file__).parent.parent.parent / "mqtt_client.py"
    mqtt = _load_module("mqtt_client_client_test", str(mqtt_client_path))
    
    # Create options with custom safe_device_classes
    options = {
        "mqtt_host": "test",
        "safe_device_classes": ["temperature", "humidity"],
    }
    
    client = mqtt.CentralCoreClient(options)
    
    assert hasattr(client, "safe_device_classes")
    assert client.safe_device_classes == ["temperature", "humidity"]


def test_central_core_client_uses_default_if_not_provided():
    """Test that CentralCoreClient uses defaults if safe_device_classes not in options."""
    mqtt_client_path = pathlib.Path(__file__).parent.parent.parent / "mqtt_client.py"
    mqtt = _load_module("mqtt_client_default_test", str(mqtt_client_path))
    
    # Create options without safe_device_classes
    options = {
        "mqtt_host": "test",
    }
    
    client = mqtt.CentralCoreClient(options)
    
    assert hasattr(client, "safe_device_classes")
    assert client.safe_device_classes == mqtt.DEFAULT_SAFE_DEVICE_CLASSES


def test_central_core_client_handles_invalid_safe_device_classes():
    """Test that CentralCoreClient handles invalid safe_device_classes gracefully."""
    mqtt_client_path = pathlib.Path(__file__).parent.parent.parent / "mqtt_client.py"
    mqtt = _load_module("mqtt_client_invalid_test", str(mqtt_client_path))
    
    # Create options with invalid safe_device_classes (not a list)
    options = {
        "mqtt_host": "test",
        "safe_device_classes": "not_a_list",
    }
    
    client = mqtt.CentralCoreClient(options)
    
    # Should fall back to defaults
    assert client.safe_device_classes == mqtt.DEFAULT_SAFE_DEVICE_CLASSES


def test_binary_sensors_filtered_by_device_class():
    """Test that binary_sensor entities are also filtered by device_class."""
    mqtt_client_path = pathlib.Path(__file__).parent.parent.parent / "mqtt_client.py"
    mqtt = _load_module("mqtt_client_binary_test", str(mqtt_client_path))
    
    # Mock requests module
    class MockResponse:
        def __init__(self, json_data):
            self._json_data = json_data
        
        def raise_for_status(self):
            pass
        
        def json(self):
            return self._json_data
    
    class MockRequests:
        @staticmethod
        def get(url, headers=None, timeout=None):
            return MockResponse([
                {
                    "entity_id": "binary_sensor.door_front",
                    "state": "on",
                    "attributes": {
                        "device_class": "door",
                        "friendly_name": "Front Door"
                    },
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
                {
                    "entity_id": "binary_sensor.window_bedroom",
                    "state": "off",
                    "attributes": {
                        "device_class": "window",
                        "friendly_name": "Bedroom Window"
                    },
                    "last_changed": "2024-01-01T00:00:00Z",
                    "last_updated": "2024-01-01T00:00:00Z",
                },
            ])
    
    mqtt.requests = MockRequests()
    
    # Mock _load_sensor_registry to return empty list (no registry filtering)
    mqtt._load_sensor_registry = lambda: []
    
    # door is in default safe classes, window is not
    sensors = mqtt.fetch_sensors("http://test", "token", mqtt.DEFAULT_SAFE_DEVICE_CLASSES)
    
    assert sensors is not None
    entity_ids = [s["entity_id"] for s in sensors]
    
    assert "binary_sensor.door_front" in entity_ids
    assert "binary_sensor.window_bedroom" not in entity_ids
