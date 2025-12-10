# Copyright ...
import json
from datetime import datetime, timezone



def attach_ha_timestamps(attrs, sensor):
    if sensor.get("last_changed") is not None:
        attrs["last_changed"] = sensor.get("last_changed")
    if sensor.get("last_updated") is not None:
        attrs["last_updated"] = sensor.get("last_updated")
    return attrs


def build_sensor_maps(filtered):
    data_map = {}
    names_map = {}
    enabled_map = {}
    attrs_map = {}
    for s in filtered:
        ent = s.get("entity_id")
        if not ent:
            continue
        attrs = s.get("attributes", {}) or {}
        attach_ha_timestamps(attrs, s)
        raw_state = s.get("state")
        data_map[ent] = raw_state
        names_map[ent] = attrs.get("friendly_name") or s.get("name") or ent
        enabled_map[ent] = not bool(attrs.get("disabled_by"))
        attrs_map[ent] = attrs
    return data_map, names_map, enabled_map, attrs_map


def build_sensor_event_payload(entity_id, attrs, state_value):
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "data": {entity_id: state_value},
        "names": {entity_id: attrs.get("friendly_name") or entity_id},
        "enabled": {entity_id: not bool(attrs.get("disabled_by"))},
        "attributes": {entity_id: attrs},
        "timestamp": now_iso,
    }
    return json.dumps(payload)
