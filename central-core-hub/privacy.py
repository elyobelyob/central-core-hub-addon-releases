"""What the hub never sends, in one place so the paths that send things cannot drift.

- The privacy registry (SENSOR_REGISTRY): `registry_rule` turns its document
  into a test on entity ids. Errors and unknown modes deny everything.

Pure functions: no I/O, no logging. Callers log the `problem` strings.
"""
import fnmatch

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
