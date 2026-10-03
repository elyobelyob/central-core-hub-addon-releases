"""handlers: a failure in one step is reported to the vault, and never stops
the steps after it or crashes the MQTT thread."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import handlers
import inventory


class _Client:
    client_id = "hub-x"

    def __init__(self, fail_topics=(), updater=None):
        self.fail_topics = tuple(fail_topics)
        self.published = []
        self._updater = updater
        self.preferred_sensors_topic = "hubs/hub-x/v1/telemetry/sensors"
        self.vault_topic = "hubs/hub-x/v1/vault"
        self.ha_api_url, self.ha_api_token = "http://ha", "tok"

    def addon_updater(self):
        return self._updater

    def build_ack_topic(self, action, command_id):
        return f"hubs/hub-x/v1/ack/{action.replace('/', '.')}/{command_id}"

    def _publish(self, topic, payload, qos=0, persist=None):
        if any(topic.startswith(t) for t in self.fail_topics):
            raise ConnectionError("broker gone")
        self.published.append((topic, json.loads(payload)))

    def acks(self, cid):
        return [p for t, p in self.published if t.endswith("/" + cid)]


def _send(client, action, body, fetch=None):
    msg = SimpleNamespace(topic=f"hubs/hub-x/v1/cmd/{action}", retain=False)
    handlers.handle_message(client, msg, json.dumps(body), fetch, None, None, requests=None)


# --- update commands --------------------------------------------------------


class _ExplodingUpdater:
    def update(self, expected_version=None, before_install=None):
        raise RuntimeError("supervisor said no")

    def check(self):
        raise RuntimeError("supervisor said no")


@pytest.mark.parametrize("action", ["config/update", "config/check_update"])
def test_updater_crash_is_reported_as_failed_with_its_message(action):
    client = _Client(updater=_ExplodingUpdater())
    _send(client, action, {"command_id": "u1"})
    handlers.wait_for_update_worker(timeout=5)
    final = client.acks("u1")[-1]
    assert final["status"] == "failed"
    assert final["result"]["reason"] == "supervisor said no"


def test_check_update_without_ack_topic_still_runs():
    class Checker:
        def check(self):
            return {"outcome": "checked", "installed": "1", "latest": "2", "auto_update": False, "reason": None}

    client = _Client(updater=Checker(), fail_topics=())
    # build_ack_topic failing for the "acknowledged" ack must not stop the check
    calls = {"n": 0}
    real = client.build_ack_topic

    def flaky(action, cid):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("bad id")
        return real(action, cid)

    client.build_ack_topic = flaky
    _send(client, "config/check_update", {"command_id": "k1"})
    handlers.wait_for_update_worker(timeout=5)
    assert [a["status"] for a in client.acks("k1")] == ["completed"]


# --- command age ------------------------------------------------------------


def test_command_age_ignores_booleans_and_blank():
    assert handlers._command_age_seconds(True) is None
    assert handlers._command_age_seconds("") is None
    assert handlers._command_age_seconds(None) is None


def test_command_age_reads_naive_iso_as_utc():
    ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).replace(tzinfo=None).isoformat()
    age = handlers._command_age_seconds(ts)
    assert 115 < age < 180


@pytest.mark.parametrize("bad", ["yesterday", 1e20])
def test_command_age_unreadable_is_none(bad):
    assert handlers._command_age_seconds(bad) is None


# --- sensors/poll ------------------------------------------------------------

STATES = [
    {"entity_id": "binary_sensor.front_door", "state": "on", "attributes": {"device_class": "door"}},
]


def test_poll_keeps_going_when_telemetry_and_reminder_publishes_fail():
    client = _Client(fail_topics=("hubs/hub-x/v1/telemetry", "hubs/hub-x/v1/vault"))
    _send(client, "sensors/poll", {"command_id": "p1", "payload": {"sensors": ["door"]}},
          fetch=lambda url, tok: [dict(s) for s in STATES])
    done = [a for a in client.acks("p1") if a["status"] == "completed"]
    assert done and done[-1]["result"]["sensors_reported"] == ["binary_sensor.front_door"]


def test_poll_survives_a_broker_that_refuses_everything():
    client = _Client(fail_topics=("hubs/",))
    _send(client, "sensors/poll", {"command_id": "p2", "payload": {"sensors": ["door"]}},
          fetch=lambda url, tok: [dict(s) for s in STATES])
    assert client.published == []  # nothing sent, and no exception escaped


# --- inventory ----------------------------------------------------------------


def test_inventory_unexpected_error_is_reported_generically(monkeypatch):
    def boom(*a, **k):
        raise KeyError("secret detail")

    monkeypatch.setattr(inventory, "answer", boom)
    client = _Client()
    handlers._handle_inventory(client, json.dumps({"command_id": "i1"}))
    final = client.acks("i1")[-1]
    assert final["status"] == "failed"
    assert final["result"] == {"reason": "inventory_failed"}  # no internal detail leaks


def test_inventory_without_command_id_sends_no_result(monkeypatch):
    monkeypatch.setattr(inventory, "answer", lambda *a, **k: {"run": "r", "part": 1, "parts": 1, "data": ""})
    client = _Client()
    handlers._handle_inventory(client, json.dumps({"payload": {}}))
    assert client.published == []


@pytest.mark.parametrize("body", ["[1, 2]", "{not json", "<binary>"])
def test_inventory_with_unreadable_body_sends_nothing(body, monkeypatch):
    seen = []
    monkeypatch.setattr(inventory, "answer", lambda cmd, *a, **k: seen.append(cmd) or {})
    client = _Client()
    handlers._handle_inventory(client, body)
    assert seen == [{}]
    assert client.published == []


def test_inventory_publish_failure_is_swallowed(monkeypatch):
    monkeypatch.setattr(inventory, "answer", lambda *a, **k: {"run": "r", "part": 1, "parts": 1, "data": ""})
    client = _Client(fail_topics=("hubs/",))
    handlers._handle_inventory(client, json.dumps({"command_id": "i2"}))
    assert client.published == []
