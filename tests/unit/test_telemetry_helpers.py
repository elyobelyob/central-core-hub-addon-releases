"""Tests for central-core-hub/telemetry_helpers.py.

Written test-first: each test specifies a behaviour, then we verify the
implementation satisfies it.
"""

import importlib.util
import json
import pathlib
from datetime import datetime, timezone


def _load_module():
    base = pathlib.Path(__file__).resolve().parents[2] / "central-core-hub"
    spec = importlib.util.spec_from_file_location("telemetry_helpers", str(base / "telemetry_helpers.py"))
    if spec is None or spec.loader is None:
        raise ImportError("could not load telemetry_helpers")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


th = _load_module()


# ---------------------------------------------------------------------------
# _normalize_timestamp
# ---------------------------------------------------------------------------


class TestNormalizeTimestamp:
    def test_non_string_returns_unchanged(self):
        assert th._normalize_timestamp(None) is None
        assert th._normalize_timestamp(42) == 42
        assert th._normalize_timestamp(3.14) == 3.14

    def test_invalid_string_returns_unchanged(self):
        assert th._normalize_timestamp("not-a-date") == "not-a-date"
        assert th._normalize_timestamp("") == ""

    def test_utc_z_suffix_is_parsed(self):
        result = th._normalize_timestamp("2024-01-15T10:30:00Z")
        # Must be a valid ISO string
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert dt.tzinfo is not None
        # The underlying point-in-time must match the input
        expected_utc = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert dt.astimezone(timezone.utc) == expected_utc

    def test_utc_plus00_offset_is_parsed(self):
        result = th._normalize_timestamp("2024-06-01T12:00:00+00:00")
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        expected_utc = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert dt.astimezone(timezone.utc) == expected_utc

    def test_non_utc_aware_timestamp_preserves_point_in_time(self):
        # +05:30 (IST)
        result = th._normalize_timestamp("2024-03-10T08:00:00+05:30")
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        expected_utc = datetime(2024, 3, 10, 2, 30, 0, tzinfo=timezone.utc)
        assert dt.astimezone(timezone.utc) == expected_utc

    def test_naive_timestamp_is_treated_as_local_tz(self):
        naive = "2024-01-01T00:00:00"
        result = th._normalize_timestamp(naive)
        # Should produce a valid ISO string (with tz info)
        # The exact offset depends on the local timezone, but it must be parseable
        assert isinstance(result, str)
        # Result should differ from the input (tz info is added)
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert dt.tzinfo is not None

    def test_output_is_string(self):
        result = th._normalize_timestamp("2024-01-15T10:30:00Z")
        assert isinstance(result, str)

    def test_output_has_explicit_timezone_info(self):
        """Output must always include timezone info, parseable without Z substitution."""
        result = th._normalize_timestamp("2024-01-15T10:30:00Z")
        # Must be parseable directly by fromisoformat (handles +HH:MM natively)
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# attach_ha_timestamps
# ---------------------------------------------------------------------------


class TestAttachHaTimestamps:
    def test_both_timestamps_attached(self):
        sensor = {"last_changed": "2024-01-01T00:00:00Z", "last_updated": "2024-01-01T00:01:00Z"}
        attrs = {}
        result = th.attach_ha_timestamps(attrs, sensor)
        assert "last_changed" in result
        assert "last_updated" in result

    def test_returns_attrs_dict(self):
        sensor = {"last_changed": "2024-01-01T00:00:00Z"}
        attrs = {"friendly_name": "My Sensor"}
        result = th.attach_ha_timestamps(attrs, sensor)
        assert result is attrs  # mutates and returns same dict
        assert result["friendly_name"] == "My Sensor"

    def test_missing_last_changed_not_added(self):
        sensor = {"last_updated": "2024-01-01T00:00:00Z"}
        attrs = {}
        result = th.attach_ha_timestamps(attrs, sensor)
        assert "last_changed" not in result
        assert "last_updated" in result

    def test_missing_last_updated_not_added(self):
        sensor = {"last_changed": "2024-01-01T00:00:00Z"}
        attrs = {}
        result = th.attach_ha_timestamps(attrs, sensor)
        assert "last_updated" not in result
        assert "last_changed" in result

    def test_neither_timestamp_leaves_attrs_unchanged(self):
        sensor = {"state": "on"}
        attrs = {"x": 1}
        result = th.attach_ha_timestamps(attrs, sensor)
        assert result == {"x": 1}

    def test_none_timestamp_not_added(self):
        sensor = {"last_changed": None, "last_updated": None}
        attrs = {}
        result = th.attach_ha_timestamps(attrs, sensor)
        assert "last_changed" not in result
        assert "last_updated" not in result


# ---------------------------------------------------------------------------
# build_sensor_maps
# ---------------------------------------------------------------------------


class TestBuildSensorMaps:
    def test_basic_sensor_produces_all_maps(self):
        sensors = [
            {
                "entity_id": "sensor.temp",
                "state": "22.5",
                "attributes": {"friendly_name": "Temperature", "unit_of_measurement": "°C"},
            }
        ]
        data_map, names_map, enabled_map, attrs_map = th.build_sensor_maps(sensors)
        assert data_map["sensor.temp"] == "22.5"
        assert names_map["sensor.temp"] == "Temperature"
        assert enabled_map["sensor.temp"] is True
        assert attrs_map["sensor.temp"]["unit_of_measurement"] == "°C"

    def test_sensor_without_entity_id_is_skipped(self):
        sensors = [{"state": "on", "attributes": {}}]
        data_map, _, _, _ = th.build_sensor_maps(sensors)
        assert len(data_map) == 0

    def test_disabled_sensor_shows_in_enabled_map_as_false(self):
        sensors = [
            {
                "entity_id": "sensor.off",
                "state": "unavailable",
                "attributes": {"disabled_by": "user"},
            }
        ]
        _, _, enabled_map, _ = th.build_sensor_maps(sensors)
        assert enabled_map["sensor.off"] is False

    def test_no_disabled_by_means_enabled(self):
        sensors = [{"entity_id": "sensor.ok", "state": "1", "attributes": {}}]
        _, _, enabled_map, _ = th.build_sensor_maps(sensors)
        assert enabled_map["sensor.ok"] is True

    def test_name_falls_back_to_entity_id_when_no_friendly_name(self):
        sensors = [{"entity_id": "sensor.raw", "state": "x", "attributes": {}}]
        _, names_map, _, _ = th.build_sensor_maps(sensors)
        assert names_map["sensor.raw"] == "sensor.raw"

    def test_name_uses_top_level_name_when_no_friendly_name(self):
        sensors = [{"entity_id": "sensor.raw", "state": "x", "name": "Raw Sensor", "attributes": {}}]
        _, names_map, _, _ = th.build_sensor_maps(sensors)
        assert names_map["sensor.raw"] == "Raw Sensor"

    def test_missing_attributes_defaults_to_empty_dict(self):
        sensors = [{"entity_id": "sensor.noattrs", "state": "1"}]
        data_map, _, _, attrs_map = th.build_sensor_maps(sensors)
        assert "sensor.noattrs" in data_map
        assert isinstance(attrs_map["sensor.noattrs"], dict)

    def test_none_attributes_defaults_to_empty_dict(self):
        sensors = [{"entity_id": "sensor.nullattrs", "state": "1", "attributes": None}]
        _, _, _, attrs_map = th.build_sensor_maps(sensors)
        assert isinstance(attrs_map["sensor.nullattrs"], dict)

    def test_timestamps_are_attached_to_attrs(self):
        sensors = [
            {
                "entity_id": "sensor.ts",
                "state": "1",
                "last_changed": "2024-01-01T00:00:00Z",
                "attributes": {},
            }
        ]
        _, _, _, attrs_map = th.build_sensor_maps(sensors)
        assert "last_changed" in attrs_map["sensor.ts"]

    def test_multiple_sensors(self):
        sensors = [
            {"entity_id": "sensor.a", "state": "1", "attributes": {"friendly_name": "A"}},
            {"entity_id": "sensor.b", "state": "2", "attributes": {"friendly_name": "B"}},
        ]
        data_map, names_map, _, _ = th.build_sensor_maps(sensors)
        assert len(data_map) == 2
        assert names_map["sensor.a"] == "A"
        assert names_map["sensor.b"] == "B"

    def test_empty_list_returns_empty_maps(self):
        data_map, names_map, enabled_map, attrs_map = th.build_sensor_maps([])
        assert data_map == {}
        assert names_map == {}
        assert enabled_map == {}
        assert attrs_map == {}


# ---------------------------------------------------------------------------
# build_sensor_event_payload
# ---------------------------------------------------------------------------


class TestBuildSensorEventPayload:
    def test_returns_valid_json_string(self):
        payload = th.build_sensor_event_payload("sensor.temp", {"friendly_name": "Temp"}, "22.5")
        obj = json.loads(payload)
        assert isinstance(obj, dict)

    def test_payload_contains_all_required_keys(self):
        payload = th.build_sensor_event_payload("sensor.temp", {"friendly_name": "Temp"}, "22.5")
        obj = json.loads(payload)
        assert "data" in obj
        assert "names" in obj
        assert "enabled" in obj
        assert "attributes" in obj
        assert "timestamp" in obj

    def test_data_contains_entity_state(self):
        payload = th.build_sensor_event_payload("sensor.x", {}, "42")
        obj = json.loads(payload)
        assert obj["data"]["sensor.x"] == "42"

    def test_friendly_name_used_in_names(self):
        payload = th.build_sensor_event_payload("sensor.x", {"friendly_name": "My X"}, "1")
        obj = json.loads(payload)
        assert obj["names"]["sensor.x"] == "My X"

    def test_entity_id_used_as_name_when_no_friendly_name(self):
        payload = th.build_sensor_event_payload("sensor.x", {}, "1")
        obj = json.loads(payload)
        assert obj["names"]["sensor.x"] == "sensor.x"

    def test_enabled_true_when_not_disabled(self):
        payload = th.build_sensor_event_payload("sensor.x", {}, "1")
        obj = json.loads(payload)
        assert obj["enabled"]["sensor.x"] is True

    def test_enabled_false_when_disabled_by_set(self):
        payload = th.build_sensor_event_payload("sensor.x", {"disabled_by": "user"}, "1")
        obj = json.loads(payload)
        assert obj["enabled"]["sensor.x"] is False

    def test_attributes_included(self):
        attrs = {"unit": "°C", "friendly_name": "Temp"}
        payload = th.build_sensor_event_payload("sensor.temp", attrs, "20")
        obj = json.loads(payload)
        assert obj["attributes"]["sensor.temp"]["unit"] == "°C"

    def test_timestamp_is_utc_iso_string(self):
        payload = th.build_sensor_event_payload("sensor.x", {}, "1")
        obj = json.loads(payload)
        ts = obj["timestamp"]
        assert isinstance(ts, str)
        # Must parse as a valid datetime
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert dt.tzinfo is not None
