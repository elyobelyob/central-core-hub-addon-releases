"""What the hub never sends, in one place so the paths that send things cannot drift.

- The privacy registry (SENSOR_REGISTRY): `registry_rule` turns its document
  into a test on entity ids. Errors and unknown modes deny everything.
- Phones and location: devices from Home Assistant's `mobile_app` integration
  (and every entity on them), device trackers, people, zones and geocoded
  location sensors never leave the home, whatever the registry says.

Pure functions: no I/O, no logging. Callers log the `problem` strings.
"""
import fnmatch
import re
import threading
import time

# --- privacy registry -------------------------------------------------------

# registry_mode values:
#   (absent, and apply_registry not set)  no registry: everything is allowed
#   "all"    everything, except entries with `provide: false`
#   "deny"   the same as "all" (the historical name)
#   "allow"  only entries with `provide: true`; no such entries allows nothing
REGISTRY_MODES = ("all", "allow", "deny")


def _allow_all(_entity_id):
    return True


def deny_all(_entity_id):
    return False


def _matcher(patterns):
    pats = tuple(patterns)
    return lambda eid: isinstance(eid, str) and any(fnmatch.fnmatchcase(eid, p) for p in pats)


def registry_rule(doc):
    """(allowed, problem): `allowed(entity_id) -> bool` for a registry document.

    `problem` is None, or a sentence to log when the document denies more than
    its author probably meant (an error, an unknown mode, an empty allow list).
    """
    if doc is None or doc == {}:
        return _allow_all, None
    if not isinstance(doc, dict):
        return deny_all, "the privacy registry is not a mapping; nothing is sent"
    mode = doc.get("registry_mode")
    if mode is None and not doc.get("apply_registry"):
        return _allow_all, None
    if mode is None:
        mode = "deny"
    if not isinstance(mode, str) or mode.lower() not in REGISTRY_MODES:
        return deny_all, f"unknown registry_mode {mode!r}; nothing is sent (use all, allow or deny)"
    mode = mode.lower()
    entries = doc.get("entries") or []
    if not isinstance(entries, list):
        return deny_all, "registry entries is not a list; nothing is sent"
    allow, deny = [], []
    for e in entries:
        if not isinstance(e, dict) or not isinstance(e.get("entity_id"), str):
            continue
        if e.get("provide") is False:
            deny.append(e["entity_id"])
        elif e.get("provide"):
            allow.append(e["entity_id"])
    if mode == "allow":
        if not allow:
            return deny_all, (
                "registry_mode is allow with no `provide: true` entries, so nothing is sent. "
                "Use registry_mode: all to send everything except `provide: false` entries."
            )
        return _matcher(allow), None
    denied = _matcher(deny)
    return (lambda eid: not denied(eid)), None


# --- phones and location ----------------------------------------------------

PHONE_INTEGRATION = "mobile_app"
LOCATION_DOMAINS = ("device_tracker", "person", "zone")
# Geocoded location is a mobile_app sensor; other integrations name theirs alike.
_LOCATION_OBJECT_ID = re.compile(r"(?:^|_)geocoded_location(?:_|$)")


def is_phone_device(device):
    """True for a Home Assistant device registry entry from the mobile_app integration."""
    if not isinstance(device, dict):
        return False
    return any(isinstance(i, (list, tuple)) and i and i[0] == PHONE_INTEGRATION
               for i in device.get("identifiers") or [])


def is_location_entity(entity_id, attributes=None):
    """True for an entity whose state is a location: trackers, people, zones,
    geocoded location sensors, or anything carrying coordinates."""
    if not isinstance(entity_id, str) or "." not in entity_id:
        return True  # not an entity id at all: nothing to send
    domain, object_id = entity_id.split(".", 1)
    if domain in LOCATION_DOMAINS or _LOCATION_OBJECT_ID.search(object_id):
        return True
    if isinstance(attributes, dict) and ("latitude" in attributes or "longitude" in attributes):
        return True
    return False


def phone_entities(devices, entities):
    """Entity ids on mobile_app devices, or from the mobile_app platform.

    `devices` is config/device_registry/list, `entities` the `entities` of
    config/entity_registry/list_for_display (keys `ei` entity id, `di` device
    id, `pl` platform).
    """
    phones = {d.get("id") for d in devices or [] if is_phone_device(d)}
    out = set()
    for e in entities or []:
        if not isinstance(e, dict):
            continue
        eid = e.get("ei")
        if isinstance(eid, str) and (e.get("pl") == PHONE_INTEGRATION or (e.get("di") and e.get("di") in phones)):
            out.add(eid)
    return out


class PhoneGuard:
    """Keeps the set of phone entity ids, read from Home Assistant's registries.

    `excluded()` returns the set, refreshing it when older than `ttl` seconds.
    When it has never been read (Home Assistant not answering) it returns
    None, and callers send nothing: an unknown entity might be a phone's.
    A set older than `max_stale` is not used.
    """

    def __init__(self, listener_fn, ttl=300.0, max_stale=3600.0, timeout=5.0, retry=30.0, clock=time.monotonic):
        self._listener_fn = listener_fn
        self._ttl, self._max_stale, self._timeout, self._clock = ttl, max_stale, timeout, clock
        self._retry = retry
        self._lock = threading.Lock()
        self._ids = None
        self._at = None
        self._failed_at = None

    def _read(self):
        listener = self._listener_fn()
        request = getattr(listener, "request", None)
        if not callable(request):
            return None
        connected = getattr(listener, "is_connected", None)
        if callable(connected) and not connected():
            return None  # don't wait on a socket Home Assistant isn't answering
        devices = request({"type": "config/device_registry/list"}, timeout=self._timeout)
        listing = request({"type": "config/entity_registry/list_for_display"}, timeout=self._timeout)
        if not (isinstance(devices, dict) and devices.get("success")
                and isinstance(listing, dict) and listing.get("success")):
            return None
        result = listing.get("result")
        return phone_entities(devices.get("result"), result.get("entities") if isinstance(result, dict) else None)

    def update(self, devices, entities):
        """Record registries read elsewhere (e.g. by the inventory)."""
        with self._lock:
            self._ids, self._at = frozenset(phone_entities(devices, entities)), self._clock()

    def cached(self):
        """The set without refreshing (for threads that must not wait on Home Assistant)."""
        with self._lock:
            if self._at is None or self._clock() - self._at >= self._max_stale:
                return None
            return self._ids

    def excluded(self):
        with self._lock:
            now = self._clock()
            if self._at is not None and now - self._at < self._ttl:
                return self._ids
            backing_off = self._failed_at is not None and now - self._failed_at < self._retry
        if not backing_off:
            try:
                ids = self._read()
            except Exception:
                ids = None
            with self._lock:
                if ids is None:
                    self._failed_at = self._clock()
                else:
                    self._ids, self._at, self._failed_at = frozenset(ids), self._clock(), None
        return self.cached()


def leaves_home(entity_id, attributes=None, phone_ids=None):
    """True when this entity may be sent: not a location, not on a phone.

    `phone_ids` None means the phone set is unknown, so nothing may be sent.
    """
    if phone_ids is None or entity_id in phone_ids:
        return False
    return not is_location_entity(entity_id, attributes)
