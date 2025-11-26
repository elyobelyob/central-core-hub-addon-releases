import importlib.util
from pathlib import Path
import types
import json


def _load_module(path_name):
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / path_name
    spec = importlib.util.spec_from_file_location(
        path_name.replace(".py", ""), str(src)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test__get_cpu_percent_prefers_external_override(monkeypatch):
    tele = _load_module("telemetry.py")

    # set external override
    tele._external_get_cpu_percent = lambda: 12.3
    try:
        assert tele._get_cpu_percent() == 12.3
    finally:
        del tele._external_get_cpu_percent


def test__get_cpu_percent_uses_helpers_if_present(monkeypatch):
    tele = _load_module("telemetry.py")

    # create fake helpers module
    fake_helpers = types.ModuleType("helpers")
    fake_helpers.get_cpu_percent = lambda: 7.7
    import sys

    sys.modules["helpers"] = fake_helpers
    try:
        assert tele._get_cpu_percent() == 7.7
    finally:
        del sys.modules["helpers"]


def test_build_telemetry_with_injected_helpers():
    tele = _load_module("telemetry.py")

    payload = tele.build_telemetry(
        "cid-x",
        get_cpu_percent=lambda: 3.3,
        uptime_fn=lambda: 111,
        loadavg_fn=lambda: [0.1, 0.2, 0.3],
        mem_info_fn=lambda: (1024, 512),
        disk_info_fn=lambda: (2048, 1024),
    )
    j = json.loads(payload)
    assert j["client_id"] == "cid-x"
    assert j["cpu_percent"] == 3.3
    assert j["uptime"] == 111


def test_build_vault_payload_with_invalid_json_returns_none():
    tele = _load_module("telemetry.py")
    assert tele.build_vault_payload("notjson") is None


def test_build_vault_payload_extracts_metrics():
    tele = _load_module("telemetry.py")
    raw = json.dumps(
        {
            "client_id": "c1",
            "timestamp": "t",
            "hostname": "h",
            "ip": "1.2.3.4",
            "cpu_count": 1,
            "cpu_percent": 5,
            "uptime": 10,
            "mem_total_kb": 100,
            "mem_free_kb": 50,
            "disk_total_kb": 200,
            "disk_free_kb": 100,
        }
    )
    v = tele.build_vault_payload(raw)
    j = json.loads(v)
    assert j["id"] == "c1"
    assert "metrics" in j and j["metrics"]["cpu_percent"] == 5


def test_handlers_poll_with_disabled_and_names(monkeypatch):
    handlers = _load_module("handlers.py")
    # create fake client to capture publishes
    published = []

    class C:
        def __init__(self):
            self.client_id = "hub1"
            self.preferred_sensors_topic = "hubs/hub1/v1/telemetry/sensors"
            self.ha_api_url = ""
            self.ha_api_token = ""

        def _publish(self, topic, payload, qos=0):
            published.append({"topic": topic, "payload": payload, "qos": qos})

    client = C()

    # sensors with disabled_by attribute and friendly_name
    sensors = [
        {
            "entity_id": "sensor.a",
            "state": "on",
            "name": "A",
            "attributes": {"friendly_name": "Friendly A", "disabled_by": None},
        },
        {
            "entity_id": "sensor.b",
            "state": "0",
            "name": "B",
            "attributes": {"friendly_name": "Friendly B", "disabled_by": "user"},
        },
    ]

    def fetch_sensors(u, t):
        return sensors

    # call handle_message for poll topic
    msg = types.SimpleNamespace(topic="hubs/hub1/v1/cmd/sensors/poll", payload=b"{}")
    handlers.handle_message(
        client, msg, "{}", fetch_sensors, lambda cid: "{}", lambda raw: None, None
    )

    # find the published telemetry payload
    tele_msgs = [p for p in published if p["topic"] == client.preferred_sensors_topic]
    assert tele_msgs
    jd = json.loads(tele_msgs[0]["payload"])
    assert "names" in jd and jd["names"]["sensor.a"] == "Friendly A"
    assert "enabled" in jd and jd["enabled"]["sensor.b"] is False


def test_handlers_set_no_ha_config_causes_failed(monkeypatch):
    handlers = _load_module("handlers.py")
    published = []

    class C:
        def __init__(self):
            self.client_id = "hub2"
            self.preferred_sensors_topic = "hubs/hub2/v1/telemetry/sensors"
            self.ha_api_url = ""
            self.ha_api_token = ""

        def _publish(self, topic, payload, qos=0):
            published.append({"topic": topic, "payload": payload, "qos": qos})

    client = C()

    # build a set command payload with sensors to set
    payload = json.dumps(
        {"command_id": "c1", "payload": {"sensors": {"sensor.x": "1"}}}
    )
    msg = types.SimpleNamespace(
        topic="hubs/hub2/v1/cmd/sensors/set", payload=payload.encode("utf-8")
    )
    # requests is None, so should mark as failed due to no_ha_config
    handlers.handle_message(
        client, msg, payload, lambda u, t: [], lambda cid: "{}", lambda raw: None, None
    )

    # completed response should be published
    comp = [p for p in published if p["qos"] == 1]
    assert comp
