# Copyright ...
import json
from datetime import datetime, timezone

# Get the local timezone for timestamp normalization
_LOCAL_TZ = datetime.now().astimezone().tzinfo


def _normalize_timestamp(ts_str):
    """Normalize timestamp string to hub's local timezone ISO format."""
    if not isinstance(ts_str, str):
        return ts_str
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            # Assume naive timestamps are in local timezone
            dt = dt.replace(tzinfo=_LOCAL_TZ)
        else:
            # Convert aware timestamps to local timezone
            dt = dt.astimezone(_LOCAL_TZ)
        return dt.isoformat()
    except ValueError:
        # If parsing fails, return as is
        return ts_str


def attach_ha_timestamps(attrs, sensor):
    """Attach Home Assistant timestamps to attributes, normalizing format."""
    lc = sensor.get("last_changed")
    if lc is not None:
        attrs["last_changed"] = _normalize_timestamp(lc)
    lu = sensor.get("last_updated")
    if lu is not None:
        attrs["last_updated"] = _normalize_timestamp(lu)
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
