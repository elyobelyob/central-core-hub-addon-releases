"""Tests for central-core-hub/mqtt_topics.py.

Verifies topic templates are present, have correct {client_id} placeholders,
and that the fallback defaults work when the shared package is absent.
"""

import importlib
import importlib.util
import pathlib
import sys


def _load_module(shared_stub=None):
    """Reload the module, optionally injecting a fake shared package."""
    base = pathlib.Path(__file__).resolve().parents[2] / "central-core-hub"
    spec = importlib.util.spec_from_file_location("mqtt_topics_fresh", str(base / "mqtt_topics.py"))
    if spec is None or spec.loader is None:
        raise ImportError("could not load mqtt_topics")

    # Temporarily override the shared package if a stub is provided
    old = sys.modules.pop("central_core_mqtt_shared", None)
    if shared_stub is not None:
        sys.modules["central_core_mqtt_shared"] = shared_stub

    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop("mqtt_topics_fresh", None)
        sys.modules.pop("central_core_mqtt_shared", None)
        if old is not None:
            sys.modules["central_core_mqtt_shared"] = old

    return mod


# Load once with no shared package for the default-fallback tests
_mod = _load_module()


class TestTopicTemplateDefaults:
    """When the shared package is absent, defaults are used."""

    def test_telemetry_topic_tmpl_exists(self):
        assert hasattr(_mod, "TELEMETRY_TOPIC_TMPL")

    def test_preferred_sensors_topic_tmpl_exists(self):
        assert hasattr(_mod, "PREFERRED_SENSORS_TOPIC_TMPL")

    def test_cmd_base_tmpl_exists(self):
        assert hasattr(_mod, "CMD_BASE_TMPL")

    def test_cmd_sub_tmpl_exists(self):
        assert hasattr(_mod, "CMD_SUB_TMPL")

    def test_telemetry_topic_contains_client_id_placeholder(self):
        assert "{client_id}" in _mod.TELEMETRY_TOPIC_TMPL

    def test_preferred_sensors_topic_contains_client_id_placeholder(self):
        assert "{client_id}" in _mod.PREFERRED_SENSORS_TOPIC_TMPL

    def test_cmd_base_contains_client_id_placeholder(self):
        assert "{client_id}" in _mod.CMD_BASE_TMPL

    def test_cmd_sub_contains_client_id_placeholder(self):
        assert "{client_id}" in _mod.CMD_SUB_TMPL

    def test_telemetry_topic_default_value(self):
        assert _mod.TELEMETRY_TOPIC_TMPL == "telemetry/{client_id}"

    def test_preferred_sensors_topic_default_value(self):
        assert _mod.PREFERRED_SENSORS_TOPIC_TMPL == "hubs/{client_id}/telemetry/sensors"

    def test_cmd_base_default_value(self):
        assert _mod.CMD_BASE_TMPL == "hubs/{client_id}/v1/cmd"

    def test_cmd_sub_default_value(self):
        assert _mod.CMD_SUB_TMPL == "hubs/{client_id}/v1/cmd/+"

    def test_all_templates_are_strings(self):
        for attr in ("TELEMETRY_TOPIC_TMPL", "PREFERRED_SENSORS_TOPIC_TMPL", "CMD_BASE_TMPL", "CMD_SUB_TMPL"):
            assert isinstance(getattr(_mod, attr), str), f"{attr} should be a string"

    def test_templates_format_with_client_id(self):
        cid = "my-hub-001"
        for attr in ("TELEMETRY_TOPIC_TMPL", "PREFERRED_SENSORS_TOPIC_TMPL", "CMD_BASE_TMPL", "CMD_SUB_TMPL"):
            tmpl = getattr(_mod, attr)
            result = tmpl.format(client_id=cid)
            assert cid in result, f"{attr}.format() should include client_id"

    def test_all_exported(self):
        for name in ("TELEMETRY_TOPIC_TMPL", "PREFERRED_SENSORS_TOPIC_TMPL", "CMD_BASE_TMPL", "CMD_SUB_TMPL"):
            assert name in _mod.__all__


class TestTopicTemplateFromSharedPackage:
    """When the shared package provides constants, they take priority."""

    def test_telemetry_topic_uses_shared_package_value(self):
        import types
        stub = types.SimpleNamespace(TELEMETRY_TOPIC="shared/telemetry/{client_id}")
        mod = _load_module(shared_stub=stub)
        assert mod.TELEMETRY_TOPIC_TMPL == "shared/telemetry/{client_id}"

    def test_preferred_sensors_topic_uses_shared_package_value(self):
        import types
        stub = types.SimpleNamespace(PREFERRED_SENSORS_TOPIC="shared/sensors/{client_id}")
        mod = _load_module(shared_stub=stub)
        assert mod.PREFERRED_SENSORS_TOPIC_TMPL == "shared/sensors/{client_id}"

    def test_falls_back_to_default_when_shared_attribute_missing(self):
        import types
        stub = types.SimpleNamespace()  # no TELEMETRY_TOPIC attribute
        mod = _load_module(shared_stub=stub)
        assert mod.TELEMETRY_TOPIC_TMPL == "telemetry/{client_id}"
