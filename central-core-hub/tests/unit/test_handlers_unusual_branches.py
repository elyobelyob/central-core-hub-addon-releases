import json
import importlib.util
import os
from pathlib import Path


def _load_handlers():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    return mod


# Load mqtt_client module once for test helpers so tests can compute the
# canonical ACK topic via `CentralCoreClient.build_ack_topic` rather than
# reconstructing the format string. This avoids duplicating the topic
# formatting logic in tests.

# Load mqtt_client module once for test helpers so tests can compute the
# canonical ACK topic via `CentralCoreClient.build_ack_topic` rather than
# reconstructing the format string. Use the existing `importlib.util` import
# from the top of the file.
_mqtt_path = os.path.join(os.path.dirname(__file__), "../../mqtt_client.py")
_spec = importlib.util.spec_from_file_location("mqtt_client_for_tests", _mqtt_path)
if _spec is None or getattr(_spec, "loader", None) is None:
    raise ImportError("could not load mqtt_client spec for tests")

mqtt_mod = importlib.util.module_from_spec(_spec)
loader = getattr(_spec, "loader", None)
assert loader is not None
loader.exec_module(mqtt_mod)


def build_ack_for_client_id(client_id, action, command_id):
    tmp = mqtt_mod.CentralCoreClient({"client_id": client_id})
    return tmp.build_ack_topic(action, command_id)


class RecordingClient:
    def __init__(self):
        self.client_id = "unit-hub"
        self.ha_api_url: str | None = "http://ha"
        self.ha_api_token: str | None = "tok"
        self.preferred_sensors_topic = f"hubs/{self.client_id}/telemetry/sensors"
        self.vault_topic = "vault/unit"
        self.ha_readback_after_set = True
        self.selected_sensors: list[str] | None = None
        self.published = []
        self.raise_on: list[str] | None = None

    def _publish(self, topic, payload, qos=0):
        # allow tests to simulate failure by setting attributes
        to_raise = getattr(self, "raise_on", None)
        if to_raise and topic in to_raise:
            raise RuntimeError("simulated publish failure")
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class DummyMsg:
    def __init__(self, topic, payload_bytes):
        self.topic = topic
        self.payload = payload_bytes


def test_ack_publish_raises_but_processing_continues(monkeypatch):
    handlers = _load_handlers()
    c = RecordingClient()
    # make _publish raise for ack_topic only
    # ack topic will be the v1 ack topic
    cmd = {"command_id": "ack1", "action": "sensors/poll", "payload": {}}
    # ack topic will be the v1 ack topic; compute via shared helper
    cmd = {"command_id": "ack1", "action": "sensors/poll", "payload": {}}
    ack_topic = build_ack_for_client_id(c.client_id, cmd["action"], cmd["command_id"])
    c.raise_on = [ack_topic]

    # fetch_sensors returns one sensor so telemetry publish occurs
    def fetch_sensors(url, token):
        return [{"entity_id": "sensor.a", "state": "1", "attributes": {}}]

    msg = DummyMsg(
        f"hubs/{c.client_id}/v1/cmd/sensors/poll", json.dumps(cmd).encode("utf-8")
    )

    # Should not raise despite _publish raising for ack
    handlers.handle_message(
        c,
        msg,
        msg.payload.decode("utf-8"),
        fetch_sensors,
        None,
        None,
        None,
    )

    # telemetry publish still recorded
    assert any(
        p["topic"] == c.preferred_sensors_topic for p in c.published
    )
    # completion may or may not have been published depending on where the exception occurred


def test_set_no_ha_config_reports_failed(monkeypatch):
    handlers = _load_handlers()
    c = RecordingClient()
    # remove HA config
    c.ha_api_url = None
    c.ha_api_token = None

    cmd = {
        "command_id": "set1",
        "action": "sensors/set",
        "payload": {"sensors": [{"entity_id": "sensor.x", "state": "2"}]},
    }
    msg = DummyMsg(
        f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(cmd).encode("utf-8")
    )

    handlers.handle_message(
        c,
        msg,
        msg.payload.decode("utf-8"),
        lambda u, t: [],
        None,
        None,
        None,
    )

    # completion response should include failed result for no_ha_config
    resp_topic = build_ack_for_client_id(c.client_id, cmd["action"], cmd["command_id"])
    matches = [p for p in c.published if p["topic"] == resp_topic]
    assert matches, "expected completion response"
    comp = json.loads(matches[-1]["payload"])
    assert "result" in comp and comp["result"]["failed"], comp


def test_set_requests_post_raises_results_failed(monkeypatch):
    handlers = _load_handlers()
    c = RecordingClient()

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"state": "2", "attributes": {}}

    def bad_post(url, headers=None, json=None, timeout=10):
        raise RuntimeError("post fail")

    monkeypatch.setattr("builtins.__import__", __import__)
    requests = type(
        "R",
        (),
        {
            "post": staticmethod(bad_post),
            "get": staticmethod(lambda *a, **k: FakeResp()),
        },
    )

    cmd = {
        "command_id": "set2",
        "action": "sensors/set",
        "payload": {"sensors": [{"entity_id": "sensor.y", "state": "3"}]},
    }
    msg = DummyMsg(
        f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(cmd).encode("utf-8")
    )

    handlers.handle_message(
        c, msg, msg.payload.decode("utf-8"), lambda u, t: [], None, None, requests
    )

    # completion should indicate failure for post error
    resp_topic = build_ack_for_client_id(c.client_id, cmd["action"], cmd["command_id"])
    matches = [p for p in c.published if p["topic"] == resp_topic]
    assert matches
    comp = json.loads(matches[-1]["payload"])
    assert comp["result"]["failed"], comp


def test_fetch_sensors_raises_is_caught(monkeypatch):
    handlers = _load_handlers()
    c = RecordingClient()

    def bad_fetch(url, token):
        raise RuntimeError("fetch fail")

    cmd = {"action": "sensors/poll"}
    msg = DummyMsg(
        f"hubs/{c.client_id}/v1/cmd/sensors/poll", json.dumps(cmd).encode("utf-8")
    )

    # Should not raise; handler catches top-level exceptions
    handlers.handle_message(
        c, msg, msg.payload.decode("utf-8"), bad_fetch, None, None, None
    )

    # No publishes should have occurred due to fetch failure
    assert not c.published
