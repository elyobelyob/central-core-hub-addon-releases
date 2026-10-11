"""F5 / F13: which inbound command messages the hub acts on at all.

- retained messages are ignored (a retained command would re-run on every reconnect);
- a command_id seen before is ignored (replays / QoS 1 redelivery);
- a command without a command_id is ignored (the vault always sends one);
- commands older than MAX_COMMAND_AGE are refused with a failed ACK;
- commands without a readable timestamp are refused with a failed ACK (the vault always sends one);
- command_id must match ^[A-Za-z0-9_.-]{1,64}$ (it becomes part of the ACK topic);
- the ACK topic uses the action from the command topic, not from the payload;
- payloads over MAX_COMMAND_BYTES are ignored.
"""

import json
import time
import types
from datetime import datetime, timedelta, timezone

import pytest

import handlers


def _client():
    published = []
    c = types.SimpleNamespace(client_id="hub1", ha_api_url="", ha_api_token="", selected_sensors=[])
    c.build_ack_topic = lambda action, cid: f"hubs/hub1/v1/ack/{action.replace('/', '.')}/{cid}"
    c._publish = lambda topic, payload, qos=0: published.append((topic, json.loads(payload)))
    return c, published


def _send(c, body, action="sensors/poll", retain=False, fetch=None):
    msg = types.SimpleNamespace(topic=f"hubs/hub1/v1/cmd/{action}", retain=retain)
    raw = body if isinstance(body, str) else json.dumps(body)
    handlers.handle_message(c, msg, raw, fetch or (lambda u, t: []), None, None, None)


def _poll(cid="p1", **extra):
    """A command as the vault sends it: command_id, action, payload and a current timestamp."""
    base = {"command_id": cid, "action": "sensors/poll", "payload": {"sensors": ["door"]}, "timestamp": time.time()}
    return dict(base, **extra)


def test_retained_commands_are_ignored():
    c, published = _client()
    _send(c, _poll(), retain=True)
    assert published == []


def test_duplicate_command_id_is_ignored():
    c, published = _client()
    _send(c, _poll("same"))
    first = len(published)
    assert first > 0
    _send(c, _poll("same"))
    assert len(published) == first
    _send(c, _poll("other"))
    assert len(published) > first


def test_seen_command_ids_are_bounded():
    c, _ = _client()
    for i in range(handlers.SEEN_COMMAND_IDS_MAX + 50):
        _send(c, _poll(f"id{i}"))
    assert len(c._seen_command_ids) == handlers.SEEN_COMMAND_IDS_MAX


@pytest.mark.parametrize(
    "ts",
    [
        (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp(),
    ],
)
def test_stale_commands_are_refused(ts):
    c, published = _client()
    _send(c, _poll(timestamp=ts))
    assert [p["status"] for _, p in published] == ["failed"]
    assert published[0][1]["result"]["reason"] == "stale_command"


@pytest.mark.parametrize(
    "ts",
    [
        datetime.now(timezone.utc).isoformat(),
        (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
        # a hub clock running behind makes vault commands look like they come from the future
        (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        time.time(),
    ],
)
def test_recent_commands_run(ts):
    c, published = _client()
    _send(c, _poll(timestamp=ts))
    assert published and published[0][1]["status"] == "acknowledged"


@pytest.mark.parametrize("ts", ["not-a-timestamp", "", None, True, [], {}, "2026-13-45T99:99:99Z"])
def test_commands_without_a_readable_timestamp_are_refused(ts):
    c, published = _client()
    body = _poll()
    if ts is None:
        del body["timestamp"]
    else:
        body["timestamp"] = ts
    _send(c, body)
    assert [p["status"] for _, p in published] == ["failed"]
    assert published[0][1]["result"]["reason"] == "bad_timestamp"
    assert published[0][0] == "hubs/hub1/v1/ack/sensors.poll/p1"


@pytest.mark.parametrize(
    "action",
    [
        "config/update",
        "config/check_update",
        "inventory/get",
        "sensors/poll",
        "sensors/set",
        "registry/set",
    ],
)
def test_every_action_needs_a_command_id_and_a_timestamp(action):
    c, published = _client()
    # no command_id: dropped silently (there is nothing to acknowledge)
    body = _poll()
    del body["command_id"]
    _send(c, body, action=action)
    assert published == []
    # no timestamp: refused with a failed ack for that action
    body = _poll("nots")
    del body["timestamp"]
    _send(c, body, action=action)
    key = action.replace("/", ".")
    assert [(t, p["status"], p["result"]["reason"]) for t, p in published] == [
        (f"hubs/hub1/v1/ack/{key}/nots", "failed", "bad_timestamp")
    ]


def test_a_refused_command_id_cannot_be_replayed_with_a_fresh_timestamp():
    c, published = _client()
    body = _poll("again")
    del body["timestamp"]
    _send(c, body)
    assert [p["status"] for _, p in published] == ["failed"]
    _send(c, _poll("again"))  # same id, now dated: still a repeat
    assert len(published) == 1


@pytest.mark.parametrize("cid", ["a/b", "+", "#", "x" * 65, "../x", "id with space", 5, ["x"]])
def test_bad_command_ids_are_dropped(cid):
    c, published = _client()
    _send(c, _poll(cid))
    assert published == []


def test_ack_topic_uses_the_topic_action_not_the_payload_action():
    c, published = _client()
    _send(c, _poll("p9", action="../../../evil/+"))
    assert published
    assert {t for t, _ in published} == {"hubs/hub1/v1/ack/sensors.poll/p9"}


def test_oversized_payloads_are_ignored():
    c, published = _client()
    body = _poll()
    body["payload"]["padding"] = "x" * (handlers.MAX_COMMAND_BYTES + 1)
    _send(c, body)
    assert published == []


def test_commands_for_other_hubs_are_ignored():
    c, published = _client()
    msg = types.SimpleNamespace(topic="hubs/other/v1/cmd/sensors/poll", retain=False)
    handlers.handle_message(c, msg, json.dumps(_poll()), lambda u, t: [], None, None, None)
    assert published == []
