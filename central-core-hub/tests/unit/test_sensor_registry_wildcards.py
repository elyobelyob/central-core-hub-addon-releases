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


def test_registry_deny_multiple_patterns(tmp_path, monkeypatch):
    mc = _load_module("mqtt_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"entity_id": "sensor.keep", "state": "1", "attributes": {}},
                {"entity_id": "sensor.excluded1", "state": "2", "attributes": {}},
                {"entity_id": "sensor.excluded2", "state": "3", "attributes": {}},
                {"entity_id": "binary_sensor.bs1", "state": "on", "attributes": {}},
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    cast(Any, mc).requests = RClient()

    reg = {
        "apply_registry": True,
        "registry_mode": "deny",
        "entries": [
            {"entity_id": "sensor.excluded*", "provide": False},
            {"entity_id": "binary_sensor.*", "provide": False},
        ],
    }
    p = tmp_path / "reg.yaml"
    p.write_text(json.dumps(reg))
    monkeypatch.setattr(mc, "SENSOR_REGISTRY", p)

    sensors = mc.fetch_sensors("http://ha", "tok")
    ids = [s["entity_id"] for s in sensors]
    assert "sensor.keep" in ids
    assert "sensor.excluded1" not in ids
    assert "sensor.excluded2" not in ids
    assert "binary_sensor.bs1" not in ids


def test_registry_allow_prefix(tmp_path, monkeypatch):
    mc = _load_module("mqtt_client.py")

    class Resp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"entity_id": "sensor.a1", "state": "1", "attributes": {}},
                {"entity_id": "sensor.a2", "state": "2", "attributes": {}},
                {"entity_id": "sensor.b1", "state": "3", "attributes": {}},
            ]

    class RClient:
        def get(self, url, headers=None, timeout=None):
            return Resp()

    cast(Any, mc).requests = RClient()

    reg = {
        "apply_registry": True,
        "registry_mode": "allow",
        "entries": [
            {"entity_id": "sensor.a*", "provide": True},
        ],
    }
    p = tmp_path / "reg2.yaml"
    p.write_text(json.dumps(reg))
    monkeypatch.setattr(mc, "SENSOR_REGISTRY", p)

    sensors = mc.fetch_sensors("http://ha", "tok")
    ids = [s["entity_id"] for s in sensors]
    assert "sensor.a1" in ids
    assert "sensor.a2" in ids
    assert "sensor.b1" not in ids
