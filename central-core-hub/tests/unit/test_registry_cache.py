import importlib.util
import pathlib
import builtins


def _load():
    src = pathlib.Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client_rc", str(src))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_is_entity_allowed_reads_yaml_only_once_per_mtime(tmp_path):
    mod = _load()
    registry = tmp_path / "SENSOR_REGISTRY.yaml"
    registry.write_text(
        "registry_mode: allow\napply_registry: true\nentries:\n  - entity_id: sensor.ok\n    provide: true\n"
    )
    mod.SENSOR_REGISTRY = registry
    mod._SENSOR_REGISTRY_DOC_CACHE = None
    mod._SENSOR_REGISTRY_DOC_MTIME = None

    read_count = [0]
    original_open = builtins.open

    def counting_open(path, *a, **kw):
        if str(path) == str(registry):
            read_count[0] += 1
        return original_open(path, *a, **kw)

    builtins.open = counting_open
    try:
        assert mod.is_entity_allowed("sensor.ok") is True
        assert mod.is_entity_allowed("sensor.ok") is True  # second call — cache hit
        assert read_count[0] == 1, f"Expected 1 YAML read, got {read_count[0]}"
    finally:
        builtins.open = original_open


def test_is_entity_allowed_deny_mode(tmp_path):
    mod = _load()
    registry = tmp_path / "SENSOR_REGISTRY.yaml"
    registry.write_text(
        "registry_mode: deny\napply_registry: true\nentries:\n  - entity_id: sensor.blocked\n    provide: false\n"
    )
    mod.SENSOR_REGISTRY = registry
    mod._SENSOR_REGISTRY_DOC_CACHE = None
    mod._SENSOR_REGISTRY_DOC_MTIME = None
    assert mod.is_entity_allowed("sensor.blocked") is False
    assert mod.is_entity_allowed("sensor.other") is True


def test_is_entity_allowed_returns_true_when_no_registry(tmp_path):
    mod = _load()
    mod.SENSOR_REGISTRY = tmp_path / "nonexistent.yaml"
    mod._SENSOR_REGISTRY_DOC_CACHE = None
    mod._SENSOR_REGISTRY_DOC_MTIME = None
    assert mod.is_entity_allowed("sensor.anything") is True
