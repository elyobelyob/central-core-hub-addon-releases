"""System telemetry carries the Home Assistant version the hub knows.

publish_telemetry passes home_assistant= to the build_telemetry wrapper, whose
target did not accept it: every call raised TypeError, fell back to
build_telemetry(client_id), and dropped ha_version.
"""

import importlib
import json


def test_ha_version_reaches_system_telemetry(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    c = mc.CentralCoreClient({"client_id": "hub1", "telemetry_interval": 45})
    c._ha_version_cache = "2026.9.1"
    sent = []
    monkeypatch.setattr(c, "_publish", lambda topic, payload, qos=0: sent.append((topic, json.loads(payload))))
    c.publish_telemetry()
    topic, data = sent[-1]
    assert topic == "hubs/hub1/v1/telemetry/system"
    assert data["ha_version"] == "2026.9.1"
    assert data["home_assistant"] == {"core": "2026.9.1"}
    # fields the vault reads are unchanged
    assert data["telemetry_interval"] == 45
    assert "addon_version" in data and "cpu_percent" in data
