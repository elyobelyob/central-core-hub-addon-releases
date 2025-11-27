import json
import importlib.util
from pathlib import Path


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_selected_sensor_changes_publish_on_change(monkeypatch):
    mc = _load_client_module()
    c = mc.CentralCoreClient(
        {"client_id": "hub1", "ha_api_url": "http://ha", "ha_api_token": "tok"}
    )
    # Ensure the module-level `requests` symbol is present so the
    # stricter runtime behavior in `publish_selected_sensor_changes`
    # does not early-return during tests. Tests mock `fetch_sensors`
    # directly; providing a dummy `requests` value is sufficient.
    monkeypatch.setattr(mc, "requests", object(), raising=False)
    publishes = []
    monkeypatch.setattr(
        c,
        "_publish",
        lambda topic, payload, qos=0: publishes.append(
            {"topic": topic, "payload": json.loads(payload)}
        ),
    )
    c.selected_sensors = ["sensor.a", "sensor.b"]

    sensors_first = [
        {
            "entity_id": "sensor.a",
            "state": "1",
            "attributes": {"friendly_name": "A"},
        },
        {
            "entity_id": "sensor.b",
            "state": "off",
            "attributes": {"friendly_name": "B", "disabled_by": None},
        },
        {"entity_id": "sensor.c", "state": "99", "attributes": {}},
    ]
    monkeypatch.setattr(mc, "fetch_sensors", lambda url, token: sensors_first)

    c.publish_selected_sensor_changes()
    assert len(publishes) == 1
    payload = publishes[-1]["payload"]
    assert payload["data"] == {"sensor.a": 1, "sensor.b": False}
    assert payload["names"]["sensor.a"] == "A"
    assert payload["enabled"]["sensor.b"] is True
    assert payload["attributes"]["sensor.b"].get("friendly_name") == "B"

    # identical states should not publish again
    c.publish_selected_sensor_changes()
    assert len(publishes) == 1

    sensors_second = [
        {
            "entity_id": "sensor.a",
            "state": "2",
            "attributes": {"friendly_name": "A"},
        },
        {
            "entity_id": "sensor.b",
            "state": "off",
            "attributes": {"friendly_name": "B", "disabled_by": None},
        },
    ]
    monkeypatch.setattr(mc, "fetch_sensors", lambda url, token: sensors_second)
    c.publish_selected_sensor_changes()
    assert len(publishes) == 2
    payload2 = publishes[-1]["payload"]
    assert payload2["data"]["sensor.a"] == 2
    assert payload2["data"]["sensor.b"] is False
