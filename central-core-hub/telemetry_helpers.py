# Copyright ...
import json
from datetime import datetime, timezone


def attach_ha_timestamps(attrs, sensor):
    """Attach Home Assistant timestamps to attributes, normalizing format."""
    lc = sensor.get("last_changed")
    if lc is not None:
        # Normalize HA timestamps to match add-on format
        if isinstance(lc, str):
            lc = lc.replace("+00:00", "Z")
        attrs["last_changed"] = lc
    lu = sensor.get("last_updated")
    if lu is not None:
        # Normalize HA timestamps to match add-on format
        if isinstance(lu, str):
            lu = lu.replace("+00:00", "Z")
        attrs["last_updated"] = lu
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
