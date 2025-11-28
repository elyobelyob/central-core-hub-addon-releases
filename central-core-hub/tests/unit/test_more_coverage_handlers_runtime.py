import json
import importlib.util
import os
import sys
import types


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    loader = spec.loader
    assert loader is not None
    loader.exec_module(m)
    return m


HANDLERS_P = os.path.join(os.path.dirname(__file__), "../../handlers.py")
RUNTIME_P = os.path.join(os.path.dirname(__file__), "../../mqtt_runtime.py")
TELE_P = os.path.join(os.path.dirname(__file__), "../../telemetry.py")
HELP_P = os.path.join(os.path.dirname(__file__), "../../helpers.py")


def test_handle_message_poll_invalid_and_missing_entity(monkeypatch):
    handlers = load_module(HANDLERS_P, "handlers_test_mod")

    class FakeClient:
        def __init__(self):
            self.client_id = "cid"
            self.ha_api_url = None
            self.ha_api_token = None
            self.preferred_sensors_topic = "topic"
            self.pubs = []

        def _publish(self, topic, payload, qos=0):
            self.pubs.append((topic, payload, qos))
            if "response" in topic or topic == self.preferred_sensors_topic:
                raise Exception("publish fail")

    c = FakeClient()

    # payload is valid JSON with command_id to cover ack
    msg = types.SimpleNamespace(topic=f"hubs/{c.client_id}/v1/cmd/sensors/poll")

    # fetch_sensors returns a sensor with no entity_id and one normal sensor
    def fetch_sensors(url, token):
        return [
            {"entity_id": None, "state": "on", "attributes": {}},
            {
                "entity_id": "sensor.foo",
                "state": "123",
                "attributes": {"friendly_name": "Foo"},
            },
        ]

    handlers.handle_message(
        c,
        msg,
        '{"command_id": "poll_cmd"}',
        fetch_sensors,
        lambda *a, **k: None,
        lambda x: x,
        None,
    )

    # Should have published ack, telemetry despite exceptions
    ack_pubs = [p for p in c.pubs if "/v1/ack/" in p[0] and '"acknowledged"' in p[1]]
    tele_pubs = [p for p in c.pubs if p[0] == c.preferred_sensors_topic]
    assert len(ack_pubs) == 1
    assert len(tele_pubs) == 1


def test_handle_message_set_no_ha_and_request_exceptions(monkeypatch):
    handlers = load_module(HANDLERS_P, "handlers_test_mod2")

    class FakeClient:
        def __init__(self):
            self.client_id = "cid2"
            self.ha_api_url = None
            self.ha_api_token = None
            self.preferred_sensors_topic = "topic2"
            self.ha_readback_after_set = True
            self.pubs = []

        def _publish(self, topic, payload, qos=0):
            self.pubs.append((topic, payload, qos))

    c = FakeClient()
    msg = types.SimpleNamespace(topic=f"hubs/{c.client_id}/v1/cmd/sensors/set")

    # payload sets two sensors; with no HA config, results should go to failed
    payload = json.dumps(
        {"command_id": "x", "payload": {"sensors": {"a": "on", "b": "3"}}}
    )

    handlers.handle_message(
        c, msg, payload, lambda *a, **k: [], lambda *a, **k: None, lambda x: x, None
    )

    # Completed response should have been published (command_id present)
    assert any("/v1/ack/" in p[0] for p in c.pubs)


def test_setup_mqtt_client_tls_and_callback_exceptions(monkeypatch, capsys):
    rt = load_module(RUNTIME_P, "runtime_test_mod")

    class Ctx:
        def __init__(self):
            self.client_id = "ctx1"
            self.mqtt_tls = True
            self.mqtt_ca = "/nonexistent/ca"
            self.mqtt_cert = None
            self.mqtt_key = None

    ctx = Ctx()

    # Make a mqtt_mod with a Client whose tls_set raises
    class BadClient:
        def __init__(self, *a, **k):
            pass

        def username_pw_set(self, u, p=None):
            return None

        def tls_set(self, **kw):
            raise RuntimeError("tls fail")

    class MqttMod:
        Client = BadClient

    rt.setup_mqtt_client(ctx, MqttMod)

    # Should not raise; errors are printed to stderr possibly
    # Either stderr contains TLS failure or not, but call should complete
    assert hasattr(ctx, "_client")

    # Now create a client that raises on attribute set to trigger traceback path
    class BrokenClient:
        def __init__(self, *a, **k):
            pass

        def __setattr__(self, n, v):
            if n == "on_connect":
                raise RuntimeError("nope")
            object.__setattr__(self, n, v)

    class M2:
        Client = BrokenClient

    # Should not raise
    rt.setup_mqtt_client(ctx, M2)


def test_telemetry_cpu_and_vault(monkeypatch):
    tele = load_module(TELE_P, "tele_test_mod")

    # External cpu percent that raises -> should be handled
    monkeypatch.setitem(
        tele.__dict__,
        "_external_get_cpu_percent",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    # Also ensure _get_cpu_percent returns None when helpers absent
    # Temporarily remove helpers if present
    old_helpers = sys.modules.pop("helpers", None)
    try:
        val = tele._get_cpu_percent()
        assert val is None
    finally:
        if old_helpers is not None:
            sys.modules["helpers"] = old_helpers

    # build_vault_payload should return None for invalid JSON
    assert tele.build_vault_payload("not-json") is None


def test_handle_message_set_with_ha_readback(monkeypatch):
    handlers = load_module(HANDLERS_P, "handlers_test_mod3")

    class FakeClient:
        def __init__(self):
            self.client_id = "cid3"
            self.ha_api_url = "http://ha"
            self.ha_api_token = "token"
            self.ha_readback_after_set = True
            self.preferred_sensors_topic = "topic3"
            self.pubs = []

        def _publish(self, topic, payload, qos=0):
            self.pubs.append((topic, payload, qos))
            if "response" in topic or topic == self.preferred_sensors_topic:
                raise Exception("publish fail")

    c = FakeClient()
    msg = types.SimpleNamespace(topic=f"hubs/{c.client_id}/v1/cmd/sensors/set")

    # Mock requests
    class MockResponse:
        def __init__(self, json_data, status=200):
            self.json_data = json_data
            self.status_code = status

        def raise_for_status(self):
            if self.status_code != 200:
                raise Exception("bad status")

        def json(self):
            return self.json_data

    class MockRequests:
        def post(self, url, headers=None, json=None, timeout=None):
            return MockResponse({"state": "new_state"})

        def get(self, url, headers=None, timeout=None):
            return MockResponse(
                {
                    "state": "read_state",
                    "attributes": {"friendly_name": "Read Name", "disabled_by": None},
                }
            )

    requests_mock = MockRequests()

    payload = json.dumps(
        {"command_id": "set_cmd", "payload": {"sensors": {"ent1": "on"}}}
    )

    handlers.handle_message(
        c,
        msg,
        payload,
        lambda *a, **k: [],
        lambda *a, **k: None,
        lambda x: x,
        requests_mock,
    )

    # Should have published ack, completion and telemetry despite exceptions
    ack_pubs = [p for p in c.pubs if "/v1/ack/" in p[0] and '"acknowledged"' in p[1]]
    comp_pubs = [p for p in c.pubs if "/v1/ack/" in p[0] and '"completed"' in p[1]]
    tele_pubs = [p for p in c.pubs if p[0] == c.preferred_sensors_topic]
    assert len(ack_pubs) == 1
    assert len(comp_pubs) == 1
    assert len(tele_pubs) == 1


def test_setup_mqtt_client_full_config(monkeypatch, capsys):
    rt = load_module(RUNTIME_P, "runtime_test_mod2")

    class Ctx:
        def __init__(self):
            self.client_id = "ctx2"
            self.mqtt_username = "user"
            self.mqtt_password = "pass"
            self.mqtt_tls = True
            self.mqtt_ca = "/ca"
            self.mqtt_cert = "/cert"
            self.mqtt_key = "/key"

    ctx = Ctx()

    # Mock client that records calls and raises on tls_set
    calls = []

    class MockClient:
        def __init__(self, *a, **k):
            calls.append(("init", a, k))

        def username_pw_set(self, u, p=None):
            calls.append(("username_pw_set", u, p))

        def tls_set(self, **kw):
            calls.append(("tls_set", kw))
            raise RuntimeError("tls fail")

    class MqttMod:
        Client = MockClient

    rt.setup_mqtt_client(ctx, MqttMod)

    assert len(calls) >= 3  # init, username_pw_set, tls_set

    # Check that the TLS failure was printed to stderr
    captured = capsys.readouterr()
    assert "Failed to configure TLS" in captured.err


def test_telemetry_build_with_failing_helpers(monkeypatch):
    tele = load_module(TELE_P, "tele_test_mod2")

    # Pass functions that raise to cover the except blocks
    def failing_uptime():
        raise RuntimeError("uptime fail")

    def failing_loadavg():
        raise RuntimeError("loadavg fail")

    def failing_mem():
        raise RuntimeError("mem fail")

    def failing_disk():
        raise RuntimeError("disk fail")

    payload = tele.build_telemetry(
        "cid",
        get_cpu_percent=None,
        uptime_fn=failing_uptime,
        loadavg_fn=failing_loadavg,
        mem_info_fn=failing_mem,
        disk_info_fn=failing_disk,
    )

    # Should have None for the failed ones
    data = json.loads(payload)
    assert data["uptime"] is None
    assert data["load_avg"] == []
    assert data["mem_total_kb"] is None
    assert data["mem_free_kb"] is None
    assert data["disk_total_kb"] is None
    assert data["disk_free_kb"] is None
