"""cmd/entity/rename: change a sensor's friendly name in Home Assistant.

Only the name changes (config/entity_registry/update with `name`); the entity
id, the device and Zigbee2MQTT itself are never touched. The same call renames
ZHA and Zigbee2MQTT sensors, because both are entities in HA's registry.
"""
import re

NAME_MAX = 80
# Sensors only, as everywhere else in the add-on.
_ENTITY = re.compile(r"^(binary_sensor|sensor)\.[a-z0-9_]{1,200}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_HA_ERRORS = {"unauthorized": "token_not_admin", "not_found": "not_found"}


class RenameError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def rename(listener, entity_id, name, allowed, timeout=15.0):
    if not isinstance(name, str):
        raise RenameError("bad_name")
    text = name.strip()
    if not text or len(text) > NAME_MAX or _CONTROL.search(text):
        raise RenameError("bad_name")
    if not isinstance(entity_id, str) or not _ENTITY.fullmatch(entity_id):
        raise RenameError("bad_entity")
    if not allowed(entity_id):
        raise RenameError("not_allowed")
    reply = listener.request(
        {"type": "config/entity_registry/update", "entity_id": entity_id, "name": text}, timeout=timeout
    )
    if reply is None:
        raise RenameError("ha_unreachable")
    if not reply.get("success"):
        code = (reply.get("error") or {}).get("code")
        raise RenameError(_HA_ERRORS.get(str(code), "failed"))
    return {"entity_id": entity_id, "name": text}
