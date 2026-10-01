"""cmd/inventory/get: a read-only device inventory for the vault's floor plans.

The vault owns the plans; the hub only reports what Home Assistant knows:
floors, areas, devices (names, makers, models, areas, radio addresses and
entity ids) and ZHA's Zigbee readings. It never sends locations, states or
attributes, and entities are limited to five domains and the privacy registry.
The report is sent in pages so each ACK stays small.
"""
import json
import re
import threading
import time

import privacy

DOMAINS = ("sensor", "binary_sensor", "switch", "climate", "media_player")
PAGE_CHARS = 96 * 1024  # escaped inside the ACK's JSON, a page stays well under 256 KiB
MAX_PARTS = 16
RUN_TTL_S = 600
MAX_DEVICES = 1000
MAX_NEIGHBOURS = 128
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_Z2M = re.compile(r"zigbee2mqtt_(?:bridge_)?0x([0-9a-fA-F]{16})$")


class InventoryError(Exception):
    """A reason the vault can show, e.g. token_not_admin or ha_unreachable."""


def _clean(text, limit=80):
    if text is None:
        return None
    return _CONTROL.sub("", str(text))[:limit]


def _ieee(text):
    return re.sub(r"[^0-9a-f]", "", str(text).lower())[-16:]


def _ask(listener, kind, errors, required):
    reply = listener.request({"type": kind}, timeout=15.0)
    if reply is None:
        reason = "ha_unreachable"
    elif reply.get("success"):
        return reply.get("result")
    else:
        code = (reply.get("error") or {}).get("code")
        reason = "token_not_admin" if code == "unauthorized" else str(code or "failed")
    if required:
        raise InventoryError(reason)
    errors[kind] = reason
    return None


def _stack(identifiers):
    for ident in identifiers or []:
        if not ident or len(ident) < 2:
            continue
        if ident[0] == "zha":
            return "zha", _ieee(ident[1])
        if ident[0] == "mqtt":
            m = _Z2M.search(str(ident[1]))
            if m:
                return "z2m", m.group(1).lower()
    return None, None


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _zigbee(zha_devices):
    nodes = []
    for d in zha_devices or []:
        rssi = _int(d.get("rssi"))
        nodes.append({
            "ieee": _ieee(d.get("ieee")),
            "type": d.get("device_type"),
            "lqi": _int(d.get("lqi")),
            "rssi": None if rssi == 0 else rssi,  # Home Assistant reports the coordinator as 0
            "available": d.get("available"),
            "last_seen": d.get("last_seen"),
            "neighbours": [{"ieee": _ieee(n.get("ieee")), "lqi": _int(n.get("lqi")),
                            "relationship": n.get("relationship")}
                           for n in (d.get("neighbors") or [])[:MAX_NEIGHBOURS]],
        })
    return nodes


def collect(listener, addon_version, ha_version, now, allowed=None):
    """Build the report from Home Assistant's registries and ZHA. Read-only."""
    errors = {}
    devices = _ask(listener, "config/device_registry/list", errors, True) or []
    listing = _ask(listener, "config/entity_registry/list_for_display", errors, True) or {}
    floors = _ask(listener, "config/floor_registry/list", errors, False) or []
    areas = _ask(listener, "config/area_registry/list", errors, False) or []
    zha = _ask(listener, "zha/devices", errors, False) or []

    # Phones and location are left out exactly as on the sensor paths.
    phone_ids = privacy.phone_entities(devices, listing.get("entities"))
    by_device = {}
    for e in listing.get("entities") or []:
        entity_id, device_id = e.get("ei"), e.get("di")
        if not entity_id or not device_id or e.get("hb"):
            continue
        if entity_id.split(".", 1)[0] not in DOMAINS or (allowed and not allowed(entity_id)):
            continue
        if entity_id in phone_ids or privacy.is_location_entity(entity_id):
            continue
        by_device.setdefault(device_id, []).append(entity_id)

    coordinators = {_ieee(d.get("ieee")) for d in zha if d.get("device_type") == "Coordinator"}
    out = []
    for d in devices:
        idents = d.get("identifiers") or []
        if d.get("disabled_by") or d.get("entry_type") == "service":
            continue
        if privacy.is_phone_device(d):
            continue
        stack, ieee = _stack(idents)
        entities = sorted(by_device.get(d.get("id"), []))
        if not entities and ieee not in coordinators:
            continue
        out.append({"ha_id": d.get("id"), "name": _clean(d.get("name_by_user") or d.get("name")),
                    "manufacturer": _clean(d.get("manufacturer")), "model": _clean(d.get("model")),
                    "area": d.get("area_id"), "stack": stack, "ieee": ieee, "entities": entities})
        if len(out) >= MAX_DEVICES:
            break
    return {
        "addon_version": addon_version,
        "ha_version": ha_version,
        "taken_at": now,
        "floors": [{"floor_id": f.get("floor_id"), "name": _clean(f.get("name")), "level": f.get("level")}
                   for f in floors],
        "areas": [{"area_id": a.get("area_id"), "name": _clean(a.get("name")), "floor_id": a.get("floor_id")}
                  for a in areas],
        "devices": out,
        "zigbee": {"nodes": _zigbee(zha), "network_map": None},
        "errors": errors,
    }


def pages(report):
    """The report as compact ASCII JSON, cut into pages."""
    text = json.dumps(report, separators=(",", ":"), ensure_ascii=True)
    return [text[i:i + PAGE_CHARS] for i in range(0, len(text), PAGE_CHARS)] or [""]


class RunStore:
    """Pages of recent runs, kept for 10 minutes so the vault can fetch part 2, 3, ..."""

    def __init__(self, ttl=RUN_TTL_S, clock=time.monotonic):
        self._ttl, self._clock, self._runs, self._lock = ttl, clock, {}, threading.Lock()

    def put(self, run, parts):
        with self._lock:
            now = self._clock()
            self._runs = {k: v for k, v in self._runs.items() if now - v[0] < self._ttl}
            self._runs[run] = (now, parts)

    def get(self, run):
        with self._lock:
            hit = self._runs.get(run)
            if not hit or self._clock() - hit[0] >= self._ttl:
                return None
            return hit[1]


RUNS = RunStore()


def answer(cmd, listener, addon_version, ha_version, now, allowed=None, runs=RUNS):
    """The completion result for one cmd/inventory/get message: {run, part, parts, data}."""
    payload = cmd.get("payload") if isinstance(cmd.get("payload"), dict) else {}
    part = _int(payload.get("part")) or 1
    if part == 1:
        if listener is None:
            raise InventoryError("ha_unreachable")
        parts = pages(collect(listener, addon_version, ha_version, now, allowed))
        if len(parts) > MAX_PARTS:
            raise InventoryError("too_large")
        run = str(cmd.get("command_id"))
        runs.put(run, parts)
    else:
        run = str(payload.get("run") or "")
        parts = runs.get(run)
        if parts is None:
            raise InventoryError("run_expired")
    if not 1 <= part <= len(parts):
        raise InventoryError("no_such_part")
    return {"run": run, "part": part, "parts": len(parts), "data": parts[part - 1]}
