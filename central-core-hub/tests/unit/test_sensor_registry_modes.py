import importlib.util
from pathlib import Path
import json
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


def test_registry_deny_binary_sensor(tmp_path, monkeypatch):
    mc = _load_module("mqtt_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"entity_id": "sensor.x", "state": "12", "attributes": {"device_class": "motion"}},
                {
                    "entity_id": "binary_sensor.y",
                    "state": "on",
                    "attributes": {"device_class": "motion"},
                },
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    cast(Any, mc).requests = RClient()

    # write a temporary registry that denies binary_sensor.*
    reg = {
        "apply_registry": True,
        "registry_mode": "deny",
        "entries": [
            {"entity_id": "binary_sensor.*", "provide": False},
        ],
    }
    p = tmp_path / "reg.yaml"
    p.write_text(json.dumps(reg))
    # monkeypatch the module constant to point at our temp file
    monkeypatch.setattr(mc, "SENSOR_REGISTRY", p)

    sensors = mc.fetch_sensors("http://ha", "tok")
    assert isinstance(sensors, list)
    assert any(s["entity_id"] == "sensor.x" for s in sensors)
    assert not any(s["entity_id"] == "binary_sensor.y" for s in sensors)


def test_registry_allow_only_sensor_x(tmp_path, monkeypatch):
    mc = _load_module("mqtt_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"entity_id": "sensor.x", "state": "12", "attributes": {"device_class": "motion"}},
                {"entity_id": "sensor.z", "state": "3", "attributes": {"device_class": "motion"}},
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    cast(Any, mc).requests = RClient()

    reg = {
        "apply_registry": True,
        "registry_mode": "allow",
        "entries": [
            {"entity_id": "sensor.x", "provide": True},
        ],
    }
    p = tmp_path / "reg2.yaml"
    p.write_text(json.dumps(reg))
    monkeypatch.setattr(mc, "SENSOR_REGISTRY", p)

    sensors = mc.fetch_sensors("http://ha", "tok")
    assert isinstance(sensors, list)
    assert any(s["entity_id"] == "sensor.x" for s in sensors)
    assert not any(s["entity_id"] == "sensor.z" for s in sensors)
