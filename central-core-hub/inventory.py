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
MAX_RUNS = 3  # finished runs kept for paging; the oldest goes first
BUSY_S = 60  # a collection older than this is presumed stuck and may be overtaken
DEADLINE_S = 45  # total time for collecting one inventory
ASK_TIMEOUT_S = 15
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


def _ask(listener, kind, errors, required, deadline, clock):
    left = deadline - clock()
    reply = None
    if left > 0:
        reply = listener.request({"type": kind}, timeout=min(ASK_TIMEOUT_S, left))
    if reply is None:
        reason = "timeout" if clock() >= deadline else "ha_unreachable"
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


def _zigbee(zha_devices, hidden_devices=(), hidden_ieees=()):
    """ZHA's nodes and links, without the devices the privacy rules hide
    (neither as nodes nor as anyone's neighbour)."""
    kept = []
    hidden_ieees = set(hidden_ieees)
    for d in zha_devices or []:
        ieee = _ieee(d.get("ieee"))
        if d.get("device_reg_id") in hidden_devices or ieee in hidden_ieees:
            hidden_ieees.add(ieee)
        else:
            kept.append((ieee, d))
    nodes = []
    for ieee, d in kept:
        rssi = _int(d.get("rssi"))
        nodes.append({
            "ieee": ieee,
            "type": d.get("device_type"),
            "lqi": _int(d.get("lqi")),
            "rssi": None if rssi == 0 else rssi,  # Home Assistant reports the coordinator as 0
            "available": d.get("available"),
            "last_seen": d.get("last_seen"),
            "neighbours": [{"ieee": _ieee(n.get("ieee")), "lqi": _int(n.get("lqi")),
                            "relationship": n.get("relationship")}
                           for n in (d.get("neighbors") or [])[:MAX_NEIGHBOURS]
                           if _ieee(n.get("ieee")) not in hidden_ieees],
        })
    return nodes


def _hidden_devices(devices, entities, allowed):
    """Device ids the privacy rules hide: phones, and devices that have
    entities of which the registry allows none."""
    hidden = {d.get("id") for d in devices if privacy.is_phone_device(d)}
    if allowed:
        per_device = {}
        for e in entities or []:
            if e.get("ei") and e.get("di"):
                per_device.setdefault(e["di"], []).append(e["ei"])
        hidden |= {dev for dev, ids in per_device.items() if not any(allowed(i) for i in ids)}
    return hidden


def collect(listener, addon_version, ha_version, now, allowed=None, deadline_s=DEADLINE_S, clock=time.monotonic):
    """Build the report from Home Assistant's registries and ZHA. Read-only.

    Takes at most `deadline_s` in all: past it, a required read fails the
    run with "timeout" and an optional one is reported in `errors`.
    """
    errors = {}
    deadline = clock() + deadline_s

    def ask(kind, required):
        return _ask(listener, kind, errors, required, deadline, clock)

    devices = ask("config/device_registry/list", True) or []
    listing = ask("config/entity_registry/list_for_display", True) or {}
    floors = ask("config/floor_registry/list", False) or []
    areas = ask("config/area_registry/list", False) or []
    zha = ask("zha/devices", False) or []

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

    hidden = _hidden_devices(devices, listing.get("entities"), allowed)
    hidden_ieees = {_stack(d.get("identifiers"))[1] for d in devices if d.get("id") in hidden} - {None}
    coordinators = {_ieee(d.get("ieee")) for d in zha if d.get("device_type") == "Coordinator"}
    out = []
    for d in devices:
        idents = d.get("identifiers") or []
        if d.get("disabled_by") or d.get("entry_type") == "service":
            continue
        if d.get("id") in hidden:
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
        "zigbee": {"nodes": _zigbee(zha, hidden, hidden_ieees), "network_map": None},
        "errors": errors,
    }


def pages(report):
    """The report as compact ASCII JSON, cut into pages."""
    text = json.dumps(report, separators=(",", ":"), ensure_ascii=True)
    return [text[i:i + PAGE_CHARS] for i in range(0, len(text), PAGE_CHARS)] or [""]


class RunStore:
    """Pages of the last MAX_RUNS runs, kept for 10 minutes so the vault can
    fetch part 2, 3, ...; and which hubs have a collection under way."""

    def __init__(self, ttl=RUN_TTL_S, clock=time.monotonic, max_runs=MAX_RUNS, busy_s=BUSY_S):
        self._ttl, self._clock, self._runs, self._lock = ttl, clock, {}, threading.Lock()
        self._max_runs, self._busy_s = max_runs, busy_s
        self._busy = {}  # hub -> (started, token)

    def begin(self, hub=""):
        """A token for a new collection, or None while one for `hub` started
        less than `busy_s` ago is still running."""
        with self._lock:
            now = self._clock()
            current = self._busy.get(hub)
            if current is not None and now - current[0] < self._busy_s:
                return None
            token = object()
            self._busy[hub] = (now, token)
            return token

    def end(self, hub, token):
        with self._lock:
            current = self._busy.get(hub)
            if current is not None and current[1] is token:  # not one that overtook it
                del self._busy[hub]

    def put(self, run, parts):
        with self._lock:
            now = self._clock()
            runs = {k: v for k, v in self._runs.items() if now - v[0] < self._ttl and k != run}
            runs[run] = (now, parts)
            while len(runs) > self._max_runs:
                del runs[min(runs, key=lambda k: runs[k][0])]
            self._runs = runs

    def get(self, run):
        with self._lock:
            hit = self._runs.get(run)
            if not hit or self._clock() - hit[0] >= self._ttl:
                return None
            return hit[1]


RUNS = RunStore()


def answer(cmd, listener, addon_version, ha_version, now, allowed=None, runs=RUNS, hub=""):
    """The completion result for one cmd/inventory/get message: {run, part, parts, data}."""
    payload = cmd.get("payload") if isinstance(cmd.get("payload"), dict) else {}
    part = _int(payload.get("part")) or 1
    if part == 1:
        if listener is None:
            raise InventoryError("ha_unreachable")
        token = runs.begin(hub)
        if token is None:
            raise InventoryError("busy")
        try:
            parts = pages(collect(listener, addon_version, ha_version, now, allowed))
            if len(parts) > MAX_PARTS:
                raise InventoryError("too_large")
            run = str(cmd.get("command_id"))
            runs.put(run, parts)
        finally:
            runs.end(hub, token)
    else:
        run = str(payload.get("run") or "")
        parts = runs.get(run)
        if parts is None:
            raise InventoryError("run_expired")
    if not 1 <= part <= len(parts):
        raise InventoryError("no_such_part")
    return {"run": run, "part": part, "parts": len(parts), "data": parts[part - 1]}
