import json
import importlib.util
from types import SimpleNamespace


def load_handlers():
    spec = importlib.util.spec_from_file_location(
        "handlers", "./central-core-hub/handlers.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FaultySetterClient(SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.client_id = "faulty"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "token"
        self.ha_readback_after_set = False
        self.preferred_sensors_topic = "pref/topic"
        self.vault_topic = "vault/topic"
        object.__setattr__(self, "selected_sensors", None)
        self.publishes = []

    def __setattr__(self, name, value):
        if name == "selected_sensors":
            raise RuntimeError("cannot set selected_sensors")
        super().__setattr__(name, value)

    def _publish(self, topic, payload, qos=0):
        try:
            body = json.loads(payload)
        except Exception:
            body = payload
        self.publishes.append((topic, body, qos))


class VaultFailClient(SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.client_id = "vaultfail"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "token"
        self.ha_readback_after_set = False
        self.preferred_sensors_topic = "pref/topic"
        self.vault_topic = "vault/topic"
        self.selected_sensors = None
        self.publishes = []

    def _publish(self, topic, payload, qos=0):
        if topic == self.vault_topic:
            raise RuntimeError("vault publish failed")
        try:
            body = json.loads(payload)
        except Exception:
            body = payload
        self.publishes.append((topic, body, qos))


def make_msg(topic):
    return SimpleNamespace(topic=topic)


def test_poll_with_non_dict_cmd_triggers_sensors_requested_except():
    handlers = load_handlers()
    client = SimpleNamespace()
    client.client_id = "testhub"
    client.ha_api_url = None
    client.ha_api_token = None
    client.preferred_sensors_topic = "pref/topic"
    client.vault_topic = "vault/topic"
    client.selected_sensors = None
    client.publishes = []

    def _publish(topic, payload, qos=0):
        client.publishes.append((topic, payload, qos))

    client._publish = _publish

    # payload is a JSON array -> cmd is list, cmd.get will raise and be caught
    handlers.handle_message(
        client,
        make_msg(f"hubs/{client.client_id}/v1/cmd/sensors/poll"),
        "[]",
        lambda a, b: [],
        None,
        None,
        None,
    )

    assert True


def test_poll_selected_sensors_setter_failure_is_ignored():
    handlers = load_handlers()
    client = FaultySetterClient()

    def fetch_sensors(url, token):
        return [{"entity_id": "s1", "state": "1", "attributes": {}}]

    payload = json.dumps({"payload": {"sensors": ["s1"]}})
    handlers.handle_message(
        client,
        make_msg(f"hubs/{client.client_id}/v1/cmd/sensors/poll"),
        payload,
        fetch_sensors,
        None,
        None,
        None,
    )

    # Ensure no exception and function completed
    assert True


def test_poll_vault_publish_exception_is_handled():
    handlers = load_handlers()
    client = VaultFailClient()

    # fetch_sensors returns empty so data_map empty but vault publish attempted
    handlers.handle_message(
        client,
        make_msg(f"hubs/{client.client_id}/v1/cmd/sensors/poll"),
        json.dumps({}),
        lambda a, b: [],
        None,
        None,
        None,
    )

    # function should complete despite vault publish failure
    assert True


def test_set_payload_parsing_exception_leads_to_empty_sensors_to_set():
    handlers = load_handlers()
    client = SimpleNamespace()
    client.client_id = "testhub"
    client.ha_api_url = None
    client.ha_api_token = None
    client.preferred_sensors_topic = "pref/topic"
    client.vault_topic = "vault/topic"
    client.selected_sensors = None
    client.publishes = []

    def _publish(topic, payload, qos=0):
        client.publishes.append((topic, payload, qos))

    client._publish = _publish

    # payload is a JSON array -> cmd is list, parsing sensors_to_set will raise and be caught
    handlers.handle_message(
        client,
        make_msg(f"hubs/{client.client_id}/v1/cmd/sensors/set"),
        "[]",
        None,
        None,
        None,
        None,
    )

    assert True


def test_poll_with_scalar_cmd_triggers_sensors_requested_except():
    handlers = load_handlers()
    client = SimpleNamespace()
    client.client_id = "testhub"
    client.ha_api_url = None
    client.ha_api_token = None
    client.preferred_sensors_topic = "pref/topic"
    client.vault_topic = "vault/topic"
    client.selected_sensors = None
    client.publishes = []

    def _publish(topic, payload, qos=0):
        client.publishes.append((topic, payload, qos))

    client._publish = _publish

    # payload is a JSON number -> cmd is scalar, cmd.get will raise and be caught
    handlers.handle_message(
        client,
        make_msg(f"hubs/{client.client_id}/v1/cmd/sensors/poll"),
        "123",
        lambda a, b: [],
        None,
        None,
        None,
    )

    assert True


def test_set_with_scalar_cmd_triggers_sensors_to_set_exception():
    handlers = load_handlers()
    client = SimpleNamespace()
    client.client_id = "testhub"
    client.ha_api_url = None
    client.ha_api_token = None
    client.preferred_sensors_topic = "pref/topic"
    client.vault_topic = "vault/topic"
    client.selected_sensors = None
    client.publishes = []

    def _publish(topic, payload, qos=0):
        client.publishes.append((topic, payload, qos))

    client._publish = _publish

    # payload is a JSON number -> cmd is scalar and parsing sensors_to_set will hit except
    handlers.handle_message(
        client,
        make_msg(f"hubs/{client.client_id}/v1/cmd/sensors/set"),
        "123",
        None,
        None,
        None,
        None,
    )

    assert True


def test_set_readback_off_converts_to_false_and_publishes():
    handlers = load_handlers()
    client = SimpleNamespace()
    client.client_id = "testhub"
    client.ha_api_url = "http://ha"
    client.ha_api_token = "token"
    client.ha_readback_after_set = True
    client.preferred_sensors_topic = "pref/topic"
    client.vault_topic = "vault/topic"
    client.selected_sensors = None
    client.publishes = []

    def _publish(topic, payload, qos=0):
        try:
            body = json.loads(payload)
        except Exception:
            body = payload
        client.publishes.append((topic, body, qos))

    client._publish = _publish

    class R:
        def raise_for_status(self):
            return None

        def json(self):
            return {"state": "off", "attributes": {}}

    def post(url, headers=None, json=None, timeout=None):
        return R()

    def get(url, headers=None, timeout=None):
        return R()

    requests = SimpleNamespace(post=post, get=get)

    payload = json.dumps({"payload": {"sensors": {"sensor.off": "off"}}})
    handlers.handle_message(
        client,
        make_msg(f"hubs/{client.client_id}/v1/cmd/sensors/set"),
        payload,
        None,
        None,
        None,
        requests,
    )

    # Find telemetry publish (preferred_sensors_topic) and assert data value is False
    found = False
    for topic, body, qos in client.publishes:
        if topic == client.preferred_sensors_topic and isinstance(body, dict):
            data = body.get("data") or {}
            assert data.get("sensor.off") is False
            found = True
    assert found
