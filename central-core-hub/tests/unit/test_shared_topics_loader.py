"""Perf #11: the hub needs only topic strings from central_core_mqtt_shared.

Importing the package runs its __init__, which imports the `ha` discovery
module and with it aiohttp and websockets (~160 ms, ~14 MB). The hub loads
topics.py on its own instead.
"""

import importlib
import sys

import pytest


@pytest.fixture
def fake_pkg(tmp_path, monkeypatch):
    pkg = tmp_path / "central_core_mqtt_shared"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("raise RuntimeError('package __init__ must not run')\n")
    (pkg / "topics.py").write_text(
        'TELEMETRY_SYSTEM = "hubs/{hub_id}/v{version}/telemetry/system"\n'
        'STATUS_OFFLINE = "hubs/{hub_id}/v{version}/status/offline"\n'
        "def build_topic(t, **kw):\n    return t.format(**kw)\n"
    )
    for name in ("central_core_mqtt_shared", "central_core_mqtt_shared.topics", "central_core_mqtt_shared.schemas"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.syspath_prepend(str(tmp_path))
    return pkg


def test_topics_load_without_running_the_package_init(fake_pkg):
    mc = importlib.import_module("mqtt_client")
    topics = mc._load_shared_topics()
    assert topics.build_topic(topics.STATUS_OFFLINE, hub_id="h", version=1) == "hubs/h/v1/status/offline"
    assert "central_core_mqtt_shared" not in sys.modules


def test_fallback_templates_when_the_package_is_missing(monkeypatch):
    mc = importlib.import_module("mqtt_client")
    for name in ("central_core_mqtt_shared", "central_core_mqtt_shared.topics"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    from importlib.machinery import PathFinder

    monkeypatch.setattr(PathFinder, "find_spec", classmethod(lambda cls, name, *a: None))
    topics = mc._load_shared_topics()
    build = topics.build_topic
    assert build(topics.TELEMETRY_SYSTEM, hub_id="h", version=1) == "hubs/h/v1/telemetry/system"
    assert build(topics.TELEMETRY_SENSORS, hub_id="h", version=1) == "hubs/h/v1/telemetry/sensors"
    assert build(topics.CMD_GENERIC, hub_id="h", version=1, domain="+", action="+") == "hubs/h/v1/cmd/+/+"
    assert (
        build(topics.ACK_GENERIC, hub_id="h", version=1, command_name="a.b", command_id="c")
        == "hubs/h/v1/ack/a.b/c"
    )
    assert build(topics.STATUS_OFFLINE, hub_id="h", version=1) == "hubs/h/v1/status/offline"


def test_fallback_matches_the_installed_shared_package():
    """The built-in templates must equal the real package's (when installed)."""
    from importlib.machinery import PathFinder

    spec = PathFinder.find_spec("central_core_mqtt_shared")
    if spec is None or not spec.submodule_search_locations:
        pytest.skip("real central_core_mqtt_shared not importable here")
    mc = importlib.import_module("mqtt_client")
    real = mc._load_topics_file(spec)
    for name in ("TELEMETRY_SYSTEM", "TELEMETRY_SENSORS", "CMD_GENERIC", "ACK_GENERIC", "STATUS_OFFLINE"):
        assert getattr(mc._FallbackTopics, name) == getattr(real, name)
