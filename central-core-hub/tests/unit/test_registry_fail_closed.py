"""The privacy registry fails closed.

- no registry file, or one not opted in: everything is allowed (unchanged);
- `registry_mode: all` (new) / `deny`: everything except `provide: false`;
- `registry_mode: allow`: only `provide: true` entries; none allows nothing
  (it used to allow everything) and says so in the log;
- unreadable file, non-mapping document, unknown mode: nothing is allowed.
"""

import importlib
import json
import sys
import types

import pytest

import privacy


@pytest.mark.parametrize("doc", [None, {}, {"entries": [{"entity_id": "sensor.a", "provide": False}]}])
def test_no_registry_or_not_opted_in_allows_everything(doc):
    allowed, problem = privacy.registry_rule(doc)
    assert allowed("sensor.a") and allowed("binary_sensor.b") and problem is None


@pytest.mark.parametrize("mode", ["all", "ALL", "deny", None])
def test_all_and_deny_allow_everything_but_denied(mode):
    doc = {"apply_registry": True, "registry_mode": mode,
           "entries": [{"entity_id": "sensor.secret*", "provide": False}, {"entity_id": "sensor.x", "provide": True}]}
    allowed, problem = privacy.registry_rule(doc)
    assert problem is None
    assert allowed("sensor.x") and allowed("sensor.other")
    assert not allowed("sensor.secret_one")


def test_allow_mode_allows_only_listed():
    allowed, problem = privacy.registry_rule(
        {"registry_mode": "allow", "entries": [{"entity_id": "sensor.t_*", "provide": True}]})
    assert problem is None
    assert allowed("sensor.t_hall") and not allowed("sensor.other")


@pytest.mark.parametrize("entries", [[], [{"entity_id": "sensor.a", "provide": False}], None])
def test_allow_mode_with_empty_list_allows_nothing(entries):
    allowed, problem = privacy.registry_rule({"registry_mode": "allow", "entries": entries})
    assert not allowed("sensor.a") and not allowed("sensor.b")
    assert "registry_mode: all" in problem


@pytest.mark.parametrize("doc", [
    {"registry_mode": "permit"},
    {"registry_mode": 3},
    {"registry_mode": "deny", "entries": "sensor.*"},
    ["not", "a", "mapping"],
])
def test_bad_documents_allow_nothing(doc):
    allowed, problem = privacy.registry_rule(doc)
    assert not allowed("sensor.a") and problem


@pytest.fixture
def mc(monkeypatch, tmp_path):
    mod = importlib.import_module("mqtt_client")
    lines = []
    monkeypatch.setattr(mod, "_log", lambda m, file=None: lines.append(m))
    monkeypatch.setattr(mod, "_REGISTRY_PROBLEM_LOGGED", None)
    mod.reload_sensor_registry()
    path = tmp_path / "SENSOR_REGISTRY.yaml"
    monkeypatch.setattr(mod, "SENSOR_REGISTRY", path)
    mod._lines, mod._path = lines, path
    yield mod
    mod.reload_sensor_registry()


def _write(mc, text):
    mc._path.write_text(text)
    mc.reload_sensor_registry()


def test_missing_registry_allows(mc):
    assert mc.is_entity_allowed("sensor.a")


def test_malformed_registry_denies_and_logs(mc):
    _write(mc, "registry_mode: [unclosed\n")
    assert not mc.is_entity_allowed("sensor.a")
    assert any("cannot be read" in m for m in mc._lines)


def test_non_mapping_registry_denies(mc):
    _write(mc, "- a\n- b\n")
    assert not mc.is_entity_allowed("sensor.a")


def test_allow_mode_with_no_entries_denies_and_points_to_all(mc):
    _write(mc, json.dumps({"registry_mode": "allow", "entries": []}))
    assert not mc.is_entity_allowed("sensor.a")
    assert sum("registry_mode: all" in m for m in mc._lines) == 1
    assert not mc.is_entity_allowed("sensor.b")
    assert sum("registry_mode: all" in m for m in mc._lines) == 1  # logged once, not per entity


def test_all_mode_allows_everything_but_denied(mc):
    _write(mc, json.dumps({"registry_mode": "all", "entries": [{"entity_id": "sensor.b", "provide": False}]}))
    assert mc.is_entity_allowed("sensor.a") and not mc.is_entity_allowed("sensor.b")


def test_fetch_sensors_sends_nothing_when_registry_unreadable(mc, monkeypatch):
    class Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"entity_id": "sensor.a", "state": "1", "attributes": {"device_class": "temperature"}}]

    monkeypatch.setattr(mc, "requests", types.SimpleNamespace(get=lambda *a, **k: Resp()))
    assert mc.fetch_sensors("http://localhost:8123", "tok") == [
        {"entity_id": "sensor.a", "state": "1", "name": "sensor.a", "attributes": {"device_class": "temperature"},
         "device_class": "temperature", "last_changed": None, "last_updated": None}]
    _write(mc, "{bad yaml")
    assert mc.fetch_sensors("http://localhost:8123", "tok") == []


def test_inventory_registry_test_denies_on_error(monkeypatch):
    handlers = importlib.import_module("handlers")
    fake = types.SimpleNamespace(registry_predicate=lambda: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setitem(sys.modules, "mqtt_client", fake)
    allowed = handlers._registry_allows()
    assert allowed("sensor.a") is False


def test_registry_set_accepts_all_mode():
    handlers = importlib.import_module("handlers")
    assert handlers._valid_registry_doc({"registry_mode": "all", "entries": []})
    assert not handlers._valid_registry_doc({"registry_mode": "everything", "entries": []})
