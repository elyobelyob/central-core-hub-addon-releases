"""Test suite for telemetry_helpers.py to achieve 100% coverage."""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the parent directory to the path to import telemetry_helpers
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import telemetry_helpers


def _utc(ts_str):
    """Parse a normalized timestamp and return its UTC equivalent datetime."""
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_attach_ha_timestamps_with_plus_timezone():
    """Test timestamp normalization: +00:00 input → valid tz-aware ISO string."""
    sensor = {
        "last_changed": "2025-01-01T00:00:00+00:00",
        "last_updated": "2025-01-01T00:00:01+00:00",
    }
    attrs = {}
    result = telemetry_helpers.attach_ha_timestamps(attrs, sensor)

    assert _utc(result["last_changed"]) == datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert _utc(result["last_updated"]) == datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc)


def test_attach_ha_timestamps_with_z_format():
    """Test timestamps that are already in Z format."""
    sensor = {
        "last_changed": "2025-01-01T00:00:00Z",
        "last_updated": "2025-01-01T00:00:01Z",
    }
    attrs = {}
    result = telemetry_helpers.attach_ha_timestamps(attrs, sensor)

    assert _utc(result["last_changed"]) == datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert _utc(result["last_updated"]) == datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc)


def test_attach_ha_timestamps_with_none_values():
    """Test handling of None timestamp values."""
    sensor = {
        "last_changed": None,
        "last_updated": None,
    }
    attrs = {}
    result = telemetry_helpers.attach_ha_timestamps(attrs, sensor)

    # When timestamps are None, they should not be added to attrs
    assert "last_changed" not in result
    assert "last_updated" not in result


def test_attach_ha_timestamps_missing_keys():
    """Test handling when timestamp keys are missing."""
    sensor = {}
    attrs = {}
    result = telemetry_helpers.attach_ha_timestamps(attrs, sensor)

    assert "last_changed" not in result
    assert "last_updated" not in result


def test_attach_ha_timestamps_only_last_changed():
    """Test when only last_changed is present."""
    sensor = {
        "last_changed": "2025-01-01T00:00:00+00:00",
    }
    attrs = {}
    result = telemetry_helpers.attach_ha_timestamps(attrs, sensor)

    assert _utc(result["last_changed"]) == datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert "last_updated" not in result


def test_attach_ha_timestamps_only_last_updated():
    """Test when only last_updated is present."""
    sensor = {
        "last_updated": "2025-01-01T00:00:01+00:00",
    }
    attrs = {}
    result = telemetry_helpers.attach_ha_timestamps(attrs, sensor)

    assert "last_changed" not in result
    assert _utc(result["last_updated"]) == datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc)


def test_attach_ha_timestamps_non_string_values():
    """Test handling of non-string timestamp values."""
    sensor = {
        "last_changed": 12345,  # Non-string value
        "last_updated": 67890,
    }
    attrs = {}
    result = telemetry_helpers.attach_ha_timestamps(attrs, sensor)

    # Non-string values should be added as-is
    assert result["last_changed"] == 12345
    assert result["last_updated"] == 67890


def test_normalize_timestamp_various_formats():
    """Test _normalize_timestamp with various input formats."""
    utc = timezone.utc
    # Test +00:00 format — point-in-time must be preserved
    assert _utc(telemetry_helpers._normalize_timestamp("2025-01-01T00:00:00+00:00")) == datetime(
        2025, 1, 1, 0, 0, 0, tzinfo=utc
    )
    # Test Z format
    assert _utc(telemetry_helpers._normalize_timestamp("2025-01-01T00:00:00Z")) == datetime(
        2025, 1, 1, 0, 0, 0, tzinfo=utc
    )
    # Test naive timestamp — treated as local time; result must be a tz-aware ISO string
    result = telemetry_helpers._normalize_timestamp("2025-01-01T00:00:00")
    assert isinstance(result, str)
    dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
    assert dt.tzinfo is not None
    # Test -05:00 timezone — UTC equivalent must be +5h
    assert _utc(telemetry_helpers._normalize_timestamp("2025-01-01T00:00:00-05:00")) == datetime(
        2025, 1, 1, 5, 0, 0, tzinfo=utc
    )
    # Test None
    assert telemetry_helpers._normalize_timestamp(None) is None
    # Test invalid string
    assert telemetry_helpers._normalize_timestamp("invalid") == "invalid"


def test_build_sensor_maps_basic():
    """Test building sensor maps from a list of sensors."""
    sensors = [
        {
            "entity_id": "sensor.temp",
            "state": "22.5",
            "attributes": {
                "friendly_name": "Temperature",
                "unit": "°C",
            },
            "last_changed": "2025-01-01T00:00:00+00:00",
        },
        {
            "entity_id": "sensor.humidity",
            "state": "55",
            "attributes": {
                "friendly_name": "Humidity",
                "unit": "%",
            },
            "last_updated": "2025-01-01T00:00:01+00:00",
        },
    ]

    data_map, names_map, enabled_map, attrs_map = telemetry_helpers.build_sensor_maps(sensors)

    assert data_map["sensor.temp"] == "22.5"
    assert data_map["sensor.humidity"] == "55"
    assert names_map["sensor.temp"] == "Temperature"
    assert names_map["sensor.humidity"] == "Humidity"
    assert enabled_map["sensor.temp"] is True
    assert enabled_map["sensor.humidity"] is True
    assert attrs_map["sensor.temp"]["unit"] == "°C"
    assert attrs_map["sensor.humidity"]["unit"] == "%"


def test_build_sensor_maps_disabled_sensor():
    """Test building maps with a disabled sensor."""
    sensors = [
        {
            "entity_id": "sensor.disabled",
            "state": "value",
            "attributes": {
                "friendly_name": "Disabled Sensor",
                "disabled_by": "user",
            },
        },
    ]

    data_map, names_map, enabled_map, attrs_map = telemetry_helpers.build_sensor_maps(sensors)

    assert enabled_map["sensor.disabled"] is False


def test_build_sensor_maps_no_entity_id():
    """Test handling sensors without entity_id."""
    sensors = [
        {
            "state": "value",
            "attributes": {"friendly_name": "No ID"},
        },
    ]

    data_map, names_map, enabled_map, attrs_map = telemetry_helpers.build_sensor_maps(sensors)

    # Sensor without entity_id should be skipped
    assert len(data_map) == 0


def test_build_sensor_maps_empty_entity_id():
    """Test handling sensors with empty entity_id."""
    sensors = [
        {
            "entity_id": "",
            "state": "value",
            "attributes": {"friendly_name": "Empty ID"},
        },
    ]

    data_map, names_map, enabled_map, attrs_map = telemetry_helpers.build_sensor_maps(sensors)

    # Sensor with empty entity_id should be skipped
    assert len(data_map) == 0


def test_build_sensor_maps_none_attributes():
    """Test handling sensors with None attributes."""
    sensors = [
        {
            "entity_id": "sensor.test",
            "state": "value",
            "attributes": None,
        },
    ]

    data_map, names_map, enabled_map, attrs_map = telemetry_helpers.build_sensor_maps(sensors)

    assert data_map["sensor.test"] == "value"
    # None attributes should be converted to empty dict
    assert attrs_map["sensor.test"] == {}


def test_build_sensor_maps_missing_attributes():
    """Test handling sensors without attributes key."""
    sensors = [
        {
            "entity_id": "sensor.test",
            "state": "value",
        },
    ]

    data_map, names_map, enabled_map, attrs_map = telemetry_helpers.build_sensor_maps(sensors)

    assert data_map["sensor.test"] == "value"
    assert attrs_map["sensor.test"] == {}


def test_build_sensor_maps_name_fallbacks():
    """Test friendly name fallback logic."""
    sensors = [
        {
            "entity_id": "sensor.no_friendly",
            "state": "value",
            "name": "Name Field",
            "attributes": {},
        },
        {
            "entity_id": "sensor.no_name_at_all",
            "state": "value",
            "attributes": {},
        },
    ]

    data_map, names_map, enabled_map, attrs_map = telemetry_helpers.build_sensor_maps(sensors)

    # Should fall back to "name" field
    assert names_map["sensor.no_friendly"] == "Name Field"
    # Should fall back to entity_id
    assert names_map["sensor.no_name_at_all"] == "sensor.no_name_at_all"


def test_build_sensor_maps_timestamps_normalized():
    """Test that timestamps in attributes are normalized."""
    sensors = [
        {
            "entity_id": "sensor.test",
            "state": "value",
            "attributes": {},
            "last_changed": "2025-01-01T00:00:00+00:00",
            "last_updated": "2025-01-01T00:00:01+00:00",
        },
    ]

    data_map, names_map, enabled_map, attrs_map = telemetry_helpers.build_sensor_maps(sensors)

    assert _utc(attrs_map["sensor.test"]["last_changed"]) == datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert _utc(attrs_map["sensor.test"]["last_updated"]) == datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc)


def test_build_sensor_event_payload():
    """Test building a sensor event payload."""
    import json

    entity_id = "sensor.temp"
    attrs = {
        "friendly_name": "Temperature",
        "unit": "°C",
    }
    state_value = "22.5"

    payload_json = telemetry_helpers.build_sensor_event_payload(entity_id, attrs, state_value)
    payload = json.loads(payload_json)

    assert payload["data"][entity_id] == state_value
    assert payload["names"][entity_id] == "Temperature"
    assert payload["enabled"][entity_id] is True
    assert payload["attributes"][entity_id] == attrs
    assert "timestamp" in payload
    # Verify timestamp is in Z format (not +00:00)
    assert payload["timestamp"].endswith("Z")
    assert "+00:00" not in payload["timestamp"]


def test_build_sensor_event_payload_disabled_sensor():
    """Test event payload for a disabled sensor."""
    import json

    entity_id = "sensor.disabled"
    attrs = {
        "friendly_name": "Disabled Sensor",
        "disabled_by": "user",
    }
    state_value = "value"

    payload_json = telemetry_helpers.build_sensor_event_payload(entity_id, attrs, state_value)
    payload = json.loads(payload_json)

    assert payload["enabled"][entity_id] is False


def test_build_sensor_event_payload_no_friendly_name():
    """Test event payload when friendly_name is missing."""
    import json

    entity_id = "sensor.test"
    attrs = {}
    state_value = "value"

    payload_json = telemetry_helpers.build_sensor_event_payload(entity_id, attrs, state_value)
    payload = json.loads(payload_json)

    # Should fall back to entity_id
    assert payload["names"][entity_id] == entity_id
