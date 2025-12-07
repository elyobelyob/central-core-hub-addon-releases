import sys
import json
import importlib.util
import types
import pathlib


def load_telemetry():
    base = pathlib.Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("telemetry", str(base / "telemetry.py"))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    return mod


def test_external_get_cpu_percent_override():
    t = load_telemetry()
    t._external_get_cpu_percent = lambda: 12.5
    try:
        val = t._get_cpu_percent()
        assert val == 12.5
    finally:
        try:
            delattr(t, "_external_get_cpu_percent")
        except Exception:
            pass


def test_build_telemetry_with_home_assistant_dict_and_string():
    t = load_telemetry()
    raw = t.build_telemetry("cid-dict", home_assistant={"core": "2025.11.3"})
    data = json.loads(raw)
    assert data.get("ha_version") == "2025.11.3"

    t2 = load_telemetry()
    raw2 = t2.build_telemetry("cid-str", home_assistant="2025.12.1")
    data2 = json.loads(raw2)
    assert data2.get("ha_version") == "2025.12.1"


def test_build_telemetry_uses_shared_schema_when_available():
    class FakeModel:
        def __init__(self, **kwargs):
            self._payload = kwargs

        def json(self):
            return json.dumps({"from": "fake-model", "id": self._payload.get("client_id")})

    fake_schemas = types.ModuleType("central_core_mqtt_shared.schemas")
    setattr(fake_schemas, "SystemTelemetry", FakeModel)
    fake_pkg = types.ModuleType("central_core_mqtt_shared")
    setattr(fake_pkg, "schemas", fake_schemas)
    sys.modules["central_core_mqtt_shared"] = fake_pkg
    sys.modules["central_core_mqtt_shared.schemas"] = fake_schemas
    try:
        t = load_telemetry()
        out = t.build_telemetry("cid-schema")
        assert isinstance(out, str)
        j = json.loads(out)
        assert j.get("from") == "fake-model"
        assert j.get("id") == "cid-schema"
    finally:
        sys.modules.pop("central_core_mqtt_shared.schemas", None)
        sys.modules.pop("central_core_mqtt_shared", None)


def test_build_vault_payload_includes_ha_version():
    t = load_telemetry()
    raw = t.build_telemetry("cid-vault", home_assistant={"core": "2026.1.2"})
    vault = t.build_vault_payload(raw)
    assert vault is not None
    v = json.loads(vault)
    assert v.get("ha_version") == "2026.1.2"
