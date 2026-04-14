import importlib.util
import sys
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_mqtt_topics_default_templates():
    repo_root = Path(__file__).resolve().parents[3]
    mod = _load_module(repo_root / "central-core-hub" / "mqtt_topics.py", "mqtt_topics_test_default")
    assert "telemetry/{client_id}" in mod.TELEMETRY_TOPIC_TMPL
    assert "hubs/{client_id}/telemetry/sensors" in mod.PREFERRED_SENSORS_TOPIC_TMPL
    assert "hubs/{client_id}/v1/cmd" in mod.CMD_BASE_TMPL


def test_mqtt_topics_prefers_shared_module(tmp_path, monkeypatch):
    # Create a fake shared module with custom attributes
    fake = type("M", (), {})()
    fake.TELEMETRY_TOPIC_TMPL = "custom/telemetry/{client_id}"
    fake.PREFERRED_SENSORS_TOPIC_TMPL = "custom/sensors/{client_id}"
    fake.CMD_BASE_TMPL = "custom/cmd/{client_id}"
    # Insert into sys.modules under the expected name and reload mqtt_topics
    monkeypatch.setitem(sys.modules, "central_core_mqtt_shared", fake)
    repo_root = Path(__file__).resolve().parents[3]
    mod = _load_module(repo_root / "central-core-hub" / "mqtt_topics.py", "mqtt_topics_test_shared")
    assert mod.TELEMETRY_TOPIC_TMPL == "custom/telemetry/{client_id}"
    assert mod.PREFERRED_SENSORS_TOPIC_TMPL == "custom/sensors/{client_id}"
    assert mod.CMD_BASE_TMPL == "custom/cmd/{client_id}"


def test_attach_timestamps_and_build_maps_and_event_payload():
    repo_root = Path(__file__).resolve().parents[3]
    mod = _load_module(repo_root / "central-core-hub" / "telemetry_helpers.py", "th_maps")
    sensor = {
        "entity_id": "sensor.temp",
        "state": "22",
        "attributes": {"friendly_name": "Temp", "unit": "C"},
        "last_changed": "2025-01-01T00:00:00Z",
        "last_updated": "2025-01-01T00:00:01Z",
    }
    attrs = {}
    from datetime import datetime, timezone as _tz

    attrs = mod.attach_ha_timestamps(attrs, sensor)

    def _utc(s):
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(_tz.utc)

    assert _utc(attrs["last_changed"]) == datetime(2025, 1, 1, 0, 0, 0, tzinfo=_tz.utc)
    assert _utc(attrs["last_updated"]) == datetime(2025, 1, 1, 0, 0, 1, tzinfo=_tz.utc)

    data_map, names_map, enabled_map, attrs_map = mod.build_sensor_maps([sensor])
    assert data_map["sensor.temp"] == "22"
    assert names_map["sensor.temp"] == "Temp"
    assert enabled_map["sensor.temp"] is True
    assert "unit" in attrs_map["sensor.temp"]

    payload_json = mod.build_sensor_event_payload("sensor.temp", sensor["attributes"], 22)
    assert "sensor.temp" in payload_json
