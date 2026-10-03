"""AddonUpdater: every way Home Assistant can stop an update is reported, not ignored."""

import addon_updater as au

ENTITY = "update.central_core_hub_update"
PICTURE = "/api/hassio/addons/47253b21_central-core-hub/icon"


def _state(installed="2.0.43", latest="2.0.43", auto_update=True):
    return {"entity_id": ENTITY, "attributes": {"installed_version": installed, "latest_version": latest,
                                                "in_progress": False, "auto_update": auto_update,
                                                "entity_picture": PICTURE}}


class _Scripted:
    """Answers get_states from a script of replies, one per call (last repeats)."""

    def __init__(self, get_states_replies, other=None):
        self.replies = list(get_states_replies)
        self.other = other or {"success": True, "result": {}}
        self.sent = []

    def request(self, payload, timeout=15.0):
        self.sent.append(payload)
        if payload["type"] == "get_states":
            return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return self.other


def _ok(*states):
    return {"success": True, "result": list(states)}


def test_failure_uses_home_assistant_message_for_other_errors():
    assert au._failure({"success": False, "error": {"code": "not_found", "message": "No such add-on"}}) == \
        "No such add-on"
    assert au._failure({"success": False, "error": {"code": "x"}}) == "home_assistant_error"
    assert au._failure({"success": False, "error": {"code": "Forbidden"}}) == "token_not_admin"
    assert au._failure(None) == "ha_unreachable"


def test_other_update_entities_without_our_picture_are_ignored():
    sensor = {"entity_id": "sensor.not_update", "attributes": {"entity_picture": PICTURE}}
    other = {"entity_id": "update.mosquitto", "attributes": {"entity_picture": "/api/hassio/addons/core_mosquitto/icon"}}
    up = au.AddonUpdater(_Scripted([_ok(sensor, other, _state())]))
    state, reason = up._find()
    assert reason is None and state["entity_id"] == ENTITY
    assert up.slug == "47253b21_central-core-hub"


def test_check_fails_when_entity_disappears_after_store_reload():
    up = au.AddonUpdater(_Scripted([_ok(_state()), _ok()]))
    assert up.check()["outcome"] == "failed"
    assert up.check()["reason"] == "update_entity_not_found"


def test_update_returns_check_failure_without_installing():
    fake = _Scripted([None])
    res = au.AddonUpdater(fake).update()
    assert res == {"outcome": "failed", "installed": None, "latest": None, "auto_update": None,
                   "reason": "ha_unreachable"}
    assert not [p for p in fake.sent if p.get("service") == "install"]


def test_update_fails_when_entity_vanishes_while_waiting_for_version():
    slept = []
    fake = _Scripted([_ok(_state()), _ok(_state()), _ok(_state()), _ok()])
    res = au.AddonUpdater(fake, sleep=slept.append).update(expected_version="2.0.44")
    assert res["outcome"] == "failed" and res["reason"] == "update_entity_not_found"
    assert slept == [au.POLL_SECONDS]
    assert not [p for p in fake.sent if p.get("service") == "install"]


def test_disable_auto_update_false_when_entity_not_found():
    fake = _Scripted([_ok()])
    assert au.AddonUpdater(fake).disable_auto_update() is False
    assert [p["type"] for p in fake.sent] == ["get_states"]
