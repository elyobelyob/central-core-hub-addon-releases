"""AddonUpdater drives Home Assistant's update entity for this add-on."""
import addon_updater as au

ENTITY = "update.central_core_hub_update"
PICTURE = "/api/hassio/addons/47253b21_central-core-hub/icon"


def _state(installed="2.0.43", latest="2.0.43", in_progress=False, auto_update=True):
    return {"entity_id": ENTITY, "state": "on" if latest != installed else "off",
            "attributes": {"installed_version": installed, "latest_version": latest,
                           "in_progress": in_progress, "auto_update": auto_update,
                           "entity_picture": PICTURE, "title": "Central Core Hub"}}


class FakeListener:
    """Stands in for HAWebSocketListener.request(); records every call."""

    def __init__(self, states, deny=(), after_reload=None):
        self.states = states
        self.deny = set(deny)            # message types answered with "unauthorized"
        self.after_reload = after_reload  # states to switch to after a store reload
        self.sent = []

    def request(self, payload, timeout=15.0):
        self.sent.append(payload)
        kind = payload["type"]
        if kind in self.deny or (kind == "supervisor/api" and "supervisor/api" in self.deny):
            return {"success": False, "error": {"code": "unauthorized", "message": "Unauthorized"}}
        if kind == "get_states":
            return {"success": True, "result": self.states}
        if kind == "supervisor/api":
            if payload["endpoint"] == "/store/reload" and self.after_reload is not None:
                self.states = self.after_reload
            return {"success": True, "result": {}}
        if kind == "call_service":
            return {"success": True, "result": {}}
        return {"success": False, "error": {"code": "unknown", "message": kind}}

    def calls(self, kind):
        return [p for p in self.sent if p["type"] == kind]


def test_version_tuple_orders_numerically():
    assert au.version_tuple("2.0.9") < au.version_tuple("2.0.43")
    assert au.version_tuple("2.0.43") == (2, 0, 43)


def test_check_reloads_store_and_reports_versions():
    fake = FakeListener([_state("2.0.43", "2.0.43")], after_reload=[_state("2.0.43", "2.0.44")])
    res = au.AddonUpdater(fake).check()
    assert res == {"outcome": "checked", "installed": "2.0.43", "latest": "2.0.44",
                   "auto_update": True, "reason": None}
    assert fake.calls("supervisor/api")[0]["endpoint"] == "/store/reload"


def test_finds_its_own_entity_by_slug_not_by_entity_id():
    other = {"entity_id": "update.central_core_hub_update_2", "attributes": {
        "installed_version": "1.0", "latest_version": "1.0",
        "entity_picture": "/api/hassio/addons/core_mosquitto/icon"}}
    renamed = _state()
    renamed["entity_id"] = "update.my_renamed_entity"
    res = au.AddonUpdater(FakeListener([other, renamed])).check()
    assert res["installed"] == "2.0.43"


def test_update_installs_when_newer_and_calls_hook_first():
    fake = FakeListener([_state("2.0.43", "2.0.44")])
    order = []
    res = au.AddonUpdater(fake).update(before_install=lambda r: order.append(("ack", dict(r))))
    assert res["outcome"] == "started" and res["latest"] == "2.0.44"
    install = fake.calls("call_service")
    install = [c for c in install if c["domain"] == "update" and c["service"] == "install"][0]
    assert install["target"] == {"entity_id": ENTITY}
    assert install["service_data"] == {"backup": False}
    # the hook (which sends the "started" ACK) ran before update.install was sent
    assert order and order[0][1]["outcome"] == "started"
    assert fake.sent.index(install) > 0


def test_update_when_already_current():
    fake = FakeListener([_state("2.0.44", "2.0.44")])
    res = au.AddonUpdater(fake).update()
    assert res["outcome"] == "up_to_date"
    assert not [c for c in fake.calls("call_service") if c.get("service") == "install"]


def test_update_does_not_reinstall_while_in_progress():
    fake = FakeListener([_state("2.0.43", "2.0.44", in_progress=True)])
    res = au.AddonUpdater(fake).update()
    assert res["outcome"] == "started"
    assert not [c for c in fake.calls("call_service") if c.get("service") == "install"]


def test_non_admin_token_is_reported():
    fake = FakeListener([_state("2.0.43", "2.0.44")], deny={"call_service"})
    res = au.AddonUpdater(fake).update()
    assert res["outcome"] == "failed" and res["reason"] == "token_not_admin"


def test_store_reload_refused_still_updates_to_what_is_visible():
    fake = FakeListener([_state("2.0.43", "2.0.44")], deny={"supervisor/api"})
    res = au.AddonUpdater(fake).update()
    assert res["outcome"] == "started"


def test_expected_version_not_yet_in_store():
    fake = FakeListener([_state("2.0.43", "2.0.43")])
    res = au.AddonUpdater(fake).update(expected_version="2.0.45")
    assert res["outcome"] == "failed" and res["reason"] == "store_not_updated_yet"


def test_entity_not_found():
    res = au.AddonUpdater(FakeListener([])).check()
    assert res["outcome"] == "failed" and res["reason"] == "update_entity_not_found"


def test_home_assistant_unreachable():
    class Dead:
        def request(self, payload, timeout=15.0):
            return None
    res = au.AddonUpdater(Dead()).check()
    assert res["outcome"] == "failed" and res["reason"] == "ha_unreachable"


def test_disable_auto_update_uses_full_slug():
    fake = FakeListener([_state(auto_update=True)])
    assert au.AddonUpdater(fake).disable_auto_update() is True
    call = [c for c in fake.calls("supervisor/api") if c["endpoint"].endswith("/options")][0]
    assert call["endpoint"] == "/addons/47253b21_central-core-hub/options"
    assert call["method"] == "post" and call["data"] == {"auto_update": False}


def test_disable_auto_update_skips_when_already_off():
    fake = FakeListener([_state(auto_update=False)])
    assert au.AddonUpdater(fake).disable_auto_update() is True
    assert not [c for c in fake.calls("supervisor/api") if c["endpoint"].endswith("/options")]


def test_entity_disappearing_between_check_and_install_is_reported():
    # Home Assistant restarting between the check and the install
    class Flaky(FakeListener):
        def __init__(self):
            super().__init__([_state("2.0.43", "2.0.44")])
            self.lookups = 0

        def request(self, payload, timeout=15.0):
            if payload["type"] == "get_states":
                self.lookups += 1
                if self.lookups > 2:
                    return {"success": True, "result": []}
            return super().request(payload, timeout)

    res = au.AddonUpdater(Flaky()).update()
    assert res["outcome"] == "failed" and res["reason"] == "update_entity_not_found"
