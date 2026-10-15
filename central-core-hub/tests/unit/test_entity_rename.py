import json

import pytest

import entity_rename
import handlers


class FakeListener:
    def __init__(self, reply):
        self.reply, self.sent = reply, []

    def request(self, payload, timeout=15.0):
        self.sent.append(payload)
        return self.reply


def allow_all(_eid):
    return True


def test_renames_through_the_entity_registry():
    listener = FakeListener({"success": True, "result": {"entity_entry": {}}})
    out = entity_rename.rename(listener, "binary_sensor.door_a", "  Larkspur Door  ", allow_all)
    assert out == {"entity_id": "binary_sensor.door_a", "name": "Larkspur Door"}
    assert listener.sent == [
        {"type": "config/entity_registry/update", "entity_id": "binary_sensor.door_a", "name": "Larkspur Door"}
    ]


@pytest.mark.parametrize("name", ["", "   ", "x" * 81, "line\nbreak", "tab\there"])
def test_bad_names_are_refused_before_asking_ha(name):
    listener = FakeListener({"success": True})
    with pytest.raises(entity_rename.RenameError) as exc:
        entity_rename.rename(listener, "binary_sensor.door_a", name, allow_all)
    assert exc.value.reason == "bad_name" and listener.sent == []


@pytest.mark.parametrize("eid", ["", "door_a", "Binary_Sensor.X", "light.lamp", "binary_sensor.a b"])
def test_bad_or_unsupported_entities_are_refused(eid):
    listener = FakeListener({"success": True})
    with pytest.raises(entity_rename.RenameError) as exc:
        entity_rename.rename(listener, eid, "Name", allow_all)
    assert exc.value.reason == "bad_entity" and listener.sent == []


def test_privacy_registry_can_refuse():
    listener = FakeListener({"success": True})
    with pytest.raises(entity_rename.RenameError) as exc:
        entity_rename.rename(listener, "binary_sensor.door_a", "Name", lambda _e: False)
    assert exc.value.reason == "not_allowed" and listener.sent == []


@pytest.mark.parametrize(
    "reply,reason",
    [
        (None, "ha_unreachable"),
        ({"success": False, "error": {"code": "unauthorized"}}, "token_not_admin"),
        ({"success": False, "error": {"code": "not_found"}}, "not_found"),
        ({"success": False, "error": {"code": "weird"}}, "failed"),
    ],
)
def test_home_assistant_errors_map_to_reasons(reply, reason):
    with pytest.raises(entity_rename.RenameError) as exc:
        entity_rename.rename(FakeListener(reply), "binary_sensor.door_a", "Name", allow_all)
    assert exc.value.reason == reason


# --- handler ---


class FakeClient:
    client_id = "demo-home-001"

    def __init__(self, listener):
        self._ha_ws_listener = listener
        self.published = []

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"

    def _publish(self, topic, payload, qos=0, **kw):
        self.published.append((topic, json.loads(payload)))


def _cmd(entity="binary_sensor.door_a", name="Larkspur Door"):
    return json.dumps(
        {"command_id": "c1", "timestamp": handlers._utc_now_iso(), "payload": {"entity_id": entity, "name": name}}
    )


def test_handler_acks_then_completes(monkeypatch):
    monkeypatch.setattr(handlers, "_registry_allows", lambda: (lambda _e: True))
    client = FakeClient(FakeListener({"success": True, "result": {}}))
    handlers._handle_entity_rename(client, _cmd())
    statuses = [p["status"] for _t, p in client.published]
    assert statuses == ["acknowledged", "completed"]
    assert client.published[-1][1]["result"] == {"entity_id": "binary_sensor.door_a", "name": "Larkspur Door"}


def test_handler_fails_with_a_reason(monkeypatch):
    monkeypatch.setattr(handlers, "_registry_allows", lambda: (lambda _e: True))
    client = FakeClient(FakeListener(None))
    handlers._handle_entity_rename(client, _cmd())
    last = client.published[-1][1]
    assert last["status"] == "failed" and last["result"] == {"reason": "ha_unreachable"}


def test_handler_without_a_listener_fails_cleanly(monkeypatch):
    monkeypatch.setattr(handlers, "_registry_allows", lambda: (lambda _e: True))
    client = FakeClient(None)
    handlers._handle_entity_rename(client, _cmd())
    assert client.published[-1][1]["result"] == {"reason": "ha_unreachable"}
