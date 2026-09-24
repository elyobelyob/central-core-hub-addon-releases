"""Update this add-on through Home Assistant, on the vault's order.

Home Assistant exposes the add-on as an update entity; `update.install` on it
performs the update. Asking the Supervisor to reload the add-on store first
means a release published minutes ago is seen. Both need an admin token.
"""
from __future__ import annotations

import re

SLUG_SUFFIX = "central-core-hub"
STORE_RELOAD_TIMEOUT = 90  # seconds
_PICTURE_RE = re.compile(r"/addons/([^/]+)/icon")


def version_tuple(version) -> tuple:
    return tuple(int(p) for p in re.findall(r"\d+", str(version or "")))


def _result(outcome, state=None, reason=None):
    attrs = (state or {}).get("attributes", {})
    return {
        "outcome": outcome,
        "installed": attrs.get("installed_version"),
        "latest": attrs.get("latest_version"),
        "auto_update": attrs.get("auto_update"),
        "reason": reason,
    }


def _failure(reply):
    """Map a failed websocket reply to a reason."""
    if reply is None:
        return "ha_unreachable"
    code = ((reply.get("error") or {}).get("code") or "").lower()
    if code in ("unauthorized", "forbidden") or "unauthor" in code:
        return "token_not_admin"
    return (reply.get("error") or {}).get("message") or "home_assistant_error"


class AddonUpdater:
    def __init__(self, listener):
        self.listener = listener
        self.entity_id = None
        self.slug = None

    def _find(self):
        """Return this add-on's update entity state, or (None, reason)."""
        reply = self.listener.request({"type": "get_states"})
        if not reply or not reply.get("success"):
            return None, _failure(reply)
        for state in reply.get("result") or []:
            if not str(state.get("entity_id", "")).startswith("update."):
                continue
            match = _PICTURE_RE.search(str(state.get("attributes", {}).get("entity_picture") or ""))
            if match and match.group(1).endswith(SLUG_SUFFIX):
                self.entity_id = state["entity_id"]
                self.slug = match.group(1)
                return state, None
        return None, "update_entity_not_found"

    def _reload_store(self):
        # Home Assistant allows supervisor/api calls 10 s unless told otherwise;
        # a reload fetches every add-on repository and can take longer.
        self.listener.request({"type": "supervisor/api", "endpoint": "/store/reload", "method": "post",
                               "timeout": STORE_RELOAD_TIMEOUT}, timeout=STORE_RELOAD_TIMEOUT + 10)
        if self.entity_id:
            self.listener.request({"type": "call_service", "domain": "homeassistant",
                                   "service": "update_entity",
                                   "target": {"entity_id": self.entity_id}})

    def check(self) -> dict:
        state, reason = self._find()
        if state is None:
            return _result("failed", reason=reason)
        self._reload_store()
        state, reason = self._find()
        if state is None:
            return _result("failed", reason=reason)
        return _result("checked", state)

    def update(self, expected_version=None, before_install=None) -> dict:
        checked = self.check()
        if checked["outcome"] == "failed":
            return checked
        state, reason = self._find()
        if state is None:   # e.g. Home Assistant restarted since the check
            return _result("failed", reason=reason)
        attrs = state["attributes"]
        installed, latest = attrs.get("installed_version"), attrs.get("latest_version")
        if attrs.get("in_progress"):
            return _result("started", state)
        if expected_version and version_tuple(latest) < version_tuple(expected_version):
            return _result("failed", state, reason="store_not_updated_yet")
        if version_tuple(latest) <= version_tuple(installed):
            return _result("up_to_date", state)
        started = _result("started", state)
        if before_install is not None:
            before_install(started)   # the add-on restarts during the install
        reply = self.listener.request({"type": "call_service", "domain": "update", "service": "install",
                                       "target": {"entity_id": self.entity_id},
                                       "service_data": {"backup": False}}, timeout=30.0)
        if reply is not None and not reply.get("success"):
            return _result("failed", state, reason=_failure(reply))
        return started

    def disable_auto_update(self) -> bool:
        """Turn off Home Assistant's own auto-update for this add-on."""
        state, _ = self._find()
        if state is None:
            return False
        if state["attributes"].get("auto_update") is False:
            return True
        reply = self.listener.request({"type": "supervisor/api", "endpoint": f"/addons/{self.slug}/options",
                                       "method": "post", "data": {"auto_update": False}})
        return bool(reply and reply.get("success"))
