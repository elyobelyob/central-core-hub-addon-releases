"""Perf #10: one telemetry cycle reads the options file once and does not call
Home Assistant's REST API every time the HA version is still unknown."""

import importlib
import json

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    opts = tmp_path / "options.json"
    opts.write_text(json.dumps({"telemetry_interval": 30}))
    monkeypatch.setenv(mc.MQTT_OPTIONS_ENV, str(opts))
    monkeypatch.setattr(mc, "OPTIONS_PATH", str(opts))
    ha = importlib.import_module("ha_client")
    monkeypatch.setattr(ha, "OPTIONS_PATH", str(opts))
    monkeypatch.setattr(ha, "_HA_VERSION_CACHE", None)
    c = mc.CentralCoreClient({"client_id": "hub1"})
    monkeypatch.setattr(c, "_publish", lambda *a, **k: None)
    return c, mc, opts


def _count_opens(monkeypatch, path):
    import builtins

    real_open = builtins.open
    count = {"n": 0}

    def counting_open(file, *a, **k):
        if str(file) == str(path):
            count["n"] += 1
        return real_open(file, *a, **k)

    monkeypatch.setattr(builtins, "open", counting_open)
    return count


def test_one_cycle_reads_options_once(client, monkeypatch):
    c, mc, opts = client
    c._connected = True
    for name in ("publish_selected_sensor_changes", "publish_sensors"):
        monkeypatch.setattr(c, name, lambda: None)
    monkeypatch.setattr(c, "_fetch_ha_version_from_api", lambda: None)
    c.publish_telemetry()  # warm the add-on version cache
    count = _count_opens(monkeypatch, opts)
    c.run_iteration()
    # run_iteration's interval refresh + the ha_version lookup; nothing else
    assert count["n"] <= 2


def test_addon_version_is_read_once(client, monkeypatch):
    c, mc, opts = client
    calls = []
    monkeypatch.setattr(mc, "get_addon_version", lambda: calls.append(1) or "1.2.3")
    c.publish_telemetry()
    c.publish_telemetry()
    assert calls == [1]


def test_rest_version_lookup_is_throttled(client, monkeypatch):
    c, mc, opts = client
    calls = []
    monkeypatch.setattr(c, "_fetch_ha_version_from_api", lambda: calls.append(1) or None)
    for _ in range(5):
        c._resolve_ha_version()
    assert calls == [1]
