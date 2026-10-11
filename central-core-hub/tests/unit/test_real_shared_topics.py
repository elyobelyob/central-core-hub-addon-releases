"""Every topic the add-on builds, built with the REAL central_core_mqtt_shared.

The conftest replaces the package with a lenient stand-in, which once hid a
break: a newer release refused the "+" the add-on passed to build_topic. These
tests load the real topics module from wherever Python finds the package: the
release pinned in requirements.txt by default, or a checkout put first on the
path:

    PYTHONPATH=/path/to/central-core-mqtt-shared pytest tests/unit/test_real_shared_topics.py
"""

import importlib
from importlib.machinery import PathFinder

import pytest

HUB = "demo-home-001"
COMMAND_ID = "Ab-_9xYz0123456789abcd"  # what the vault's secrets.token_urlsafe(16) looks like
ACTIONS = ("config/update", "config/check_update", "inventory/get", "sensors/poll", "sensors/set", "registry/set")


@pytest.fixture
def mc():
    return importlib.import_module("mqtt_client")


@pytest.fixture
def real_topics(mc):
    spec = PathFinder.find_spec("central_core_mqtt_shared")
    assert spec is not None, "central_core_mqtt_shared is not installed: pip install -r requirements.txt"
    module = mc._load_topics_file(spec)
    assert module is not None, f"no topics.py in {spec.submodule_search_locations}"
    return module


@pytest.fixture
def hub(mc, real_topics, monkeypatch, tmp_path):
    monkeypatch.setattr(mc, "topics", real_topics)
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    client = mc.CentralCoreClient({"client_id": HUB, "mqtt_host": "broker"})
    yield client
    client.close()


def test_every_subscription_and_publish_topic_builds(hub):
    assert hub.telemetry_topic == f"hubs/{HUB}/v1/telemetry/system"
    assert hub.preferred_sensors_topic == f"hubs/{HUB}/v1/telemetry/sensors"
    assert hub.sensors_topic == hub.preferred_sensors_topic
    assert hub.cmd_sub_topic == f"hubs/{HUB}/v1/cmd/+/+"
    assert hub.status_offline_topic == f"hubs/{HUB}/v1/status/offline"
    assert hub.batch_topic == f"hubs/{HUB}/v1/telemetry/batch"
    assert hub.store_ack_topic == f"hubs/{HUB}/v1/ack"


@pytest.mark.parametrize("action", ACTIONS)
def test_every_acknowledgement_topic_builds(hub, action):
    key = action.replace("/", ".")
    assert hub.build_ack_topic(action, COMMAND_ID) == f"hubs/{HUB}/v1/ack/{key}/{COMMAND_ID}"


@pytest.mark.parametrize("command_id", ["a/b", "+", "#", "", "x" * 65, None])
def test_an_unsafe_command_id_never_reaches_the_shared_builder(hub, command_id):
    with pytest.raises(ValueError):
        hub.build_ack_topic("sensors/poll", command_id)


def test_the_command_subscription_never_widens_to_other_hubs(mc, real_topics, monkeypatch, tmp_path):
    monkeypatch.setattr(mc, "topics", real_topics)
    monkeypatch.setattr(mc, "_log", lambda m, file=None: None)
    with pytest.raises(mc.InvalidClientId):
        mc.CentralCoreClient({"client_id": "+", "mqtt_host": "broker"})
    sub = getattr(real_topics, "build_subscription", None)
    if sub is None:
        pytest.skip("this central_core_mqtt_shared has no build_subscription (before v1.2.0)")
    with pytest.raises(ValueError):
        sub(real_topics.CMD_GENERIC, wildcards=("domain", "action"), hub_id="+", version=1)


def test_the_built_in_templates_match_the_package(mc, real_topics):
    for name in ("TELEMETRY_SYSTEM", "TELEMETRY_SENSORS", "CMD_GENERIC", "ACK_GENERIC", "STATUS_OFFLINE",
                 "TELEMETRY_BATCH", "STORE_ACK"):
        if hasattr(real_topics, name):  # TELEMETRY_BATCH and STORE_ACK arrived in v1.1.0
            assert getattr(mc._FallbackTopics, name) == getattr(real_topics, name), name
