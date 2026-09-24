import json
from types import SimpleNamespace

import handlers


class FakeUpdater:
    def __init__(self, update_result=None, check_result=None):
        self.update_result = update_result
        self.check_result = check_result
        self.expected = "unset"

    def update(self, expected_version=None, before_install=None):
        self.expected = expected_version
        if before_install and self.update_result["outcome"] == "started":
            before_install(self.update_result)
        return self.update_result

    def check(self):
        return self.check_result


class FakeClient:
    client_id = "hub-x"

    def __init__(self, updater):
        self._updater = updater
        self.published = []

    def addon_updater(self):
        return self._updater

    def build_ack_topic(self, action, command_id):
        return f"hubs/hub-x/v1/ack/{action.replace('/', '.')}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, json.loads(payload)))


def _send(client, action, payload=None):
    msg = SimpleNamespace(topic=f"hubs/hub-x/v1/cmd/{action}")
    body = json.dumps({"command_id": "c1", "action": action, "payload": payload or {}})
    handlers.handle_message(client, msg, body, None, None, None, requests=None)
    return [p for t, p in client.published if t.endswith("/c1")]


STARTED = {"outcome": "started", "installed": "2.0.43", "latest": "2.0.44", "auto_update": False, "reason": None}


def test_update_sends_started_completion_before_installing():
    client = FakeClient(FakeUpdater(update_result=STARTED))
    acks = _send(client, "config/update", {"version": "2.0.44"})
    assert acks[0]["status"] == "acknowledged"
    completions = [a for a in acks if a["status"] == "completed"]
    assert len(completions) == 1                      # sent once, by the hook, not again afterwards
    assert completions[0]["result"] == STARTED
    assert client._updater.expected == "2.0.44"


def test_update_failure_is_reported():
    failed = dict(STARTED, outcome="failed", reason="token_not_admin")
    acks = _send(FakeClient(FakeUpdater(update_result=failed)), "config/update")
    assert acks[-1]["status"] == "failed" and acks[-1]["result"]["reason"] == "token_not_admin"


def test_up_to_date_is_completed():
    current = dict(STARTED, outcome="up_to_date", latest="2.0.43")
    acks = _send(FakeClient(FakeUpdater(update_result=current)), "config/update")
    assert acks[-1]["status"] == "completed" and acks[-1]["result"]["outcome"] == "up_to_date"


def test_check_update_reports_versions():
    checked = dict(STARTED, outcome="checked")
    acks = _send(FakeClient(FakeUpdater(check_result=checked)), "config/check_update")
    assert acks[-1]["status"] == "completed" and acks[-1]["result"]["outcome"] == "checked"


def test_no_home_assistant_listener():
    acks = _send(FakeClient(None), "config/update")
    assert acks[-1]["status"] == "failed" and acks[-1]["result"]["reason"] == "ha_unreachable"


def test_started_reply_is_delivered_before_the_install_runs():
    # Live on Irongate, Home Assistant stopped the add-on for the install
    # before its "started" reply left the machine.
    events = []

    class Info:
        def wait_for_publish(self, timeout=None):
            events.append(("delivered", timeout))

    class DeliveringClient(FakeClient):
        def _publish(self, topic, payload, qos=0):
            super()._publish(topic, payload, qos)
            return Info()

    class Updater(FakeUpdater):
        def update(self, expected_version=None, before_install=None):
            before_install(self.update_result)
            events.append(("install", None))
            return self.update_result

    _send(DeliveringClient(Updater(update_result=STARTED)), "config/update")
    kinds = [e[0] for e in events]
    assert "delivered" in kinds and kinds.index("delivered") < kinds.index("install")
    assert events[kinds.index("delivered")][1]
