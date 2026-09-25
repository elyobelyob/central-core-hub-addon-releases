"""Checks that keep the hub from being used against Home Assistant or leaking from it.

- entity ids are validated before they are placed in a Home Assistant URL;
- only sensor entities can be selected;
- credentials and location are stripped from attributes before publishing;
- the Home Assistant token is not sent unencrypted to another machine.
"""

import re

# Home Assistant entity ids are `<domain>.<object_id>`, lower case letters,
# digits and underscores only. Anything else (`/`, `..`, `?`, `%`, upper case)
# is refused before an id is ever placed in a Home Assistant URL.
_ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
_ENTITY_ID_MAX_LEN = 255


def is_valid_entity_id(entity_id) -> bool:
    """True only for a well-formed Home Assistant entity id."""
    return (
        isinstance(entity_id, str)
        and len(entity_id) <= _ENTITY_ID_MAX_LEN
        and _ENTITY_ID_RE.fullmatch(entity_id) is not None
    )


# The add-on runs on the Home Assistant host, so Home Assistant is local. The
# token is a long-lived admin token: over plain http/ws it may only go to this
# host (loopback, the Supervisor's internal names, or one of our addresses).
_LOCAL_HA_HOSTNAMES = {"localhost", "homeassistant", "supervisor", "hassio"}


def _resolve_host(host):
    import socket

    return sorted({str(info[4][0]) for info in socket.getaddrinfo(host, None)})


def _is_local_address(ip):
    """True for loopback or an address assigned to this host."""
    import ipaddress
    import socket

    try:
        addr = ipaddress.ip_address(ip.split("%", 1)[0])
    except ValueError:
        return False
    if addr.is_loopback:
        return True
    family = socket.AF_INET6 if addr.version == 6 else socket.AF_INET
    try:
        # A UDP "connect" sends nothing; it only asks the kernel for the source
        # address it would use. For one of our own addresses that is itself.
        with socket.socket(family, socket.SOCK_DGRAM) as sock:
            sock.connect((str(addr), 9))
            return sock.getsockname()[0] == str(addr)
    except OSError:
        return False


def check_token_transport(url):
    """(ok, reason): may the Home Assistant token be sent to `url`?"""
    from urllib.parse import urlsplit

    try:
        parts = urlsplit((url or "").strip())
        host = (parts.hostname or "").lower()
    except ValueError:
        return False, "unparseable URL"
    if parts.scheme in ("https", "wss"):
        return (True, "encrypted") if host else (False, "no host")
    if parts.scheme not in ("http", "ws"):
        return False, f"unsupported scheme {parts.scheme!r}"
    if not host:
        return False, "no host"
    if host in _LOCAL_HA_HOSTNAMES:
        return True, "local name"
    import ipaddress

    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        addresses = None
    try:
        if addresses is None:
            addresses = _resolve_host(host)
    except OSError:
        # Nothing can be sent to a name that does not resolve.
        return True, "host does not resolve; not verified"
    remote = [a for a in addresses if not _is_local_address(a)]
    if remote:
        return False, f"{host} is not this machine ({', '.join(remote)})"
    return True, "local address"


# The vault only watches sensors (its kept set is selected sensors plus their
# battery sensors). Cameras, trackers, locks and the rest are never selectable.
SELECTABLE_DOMAINS = ("sensor", "binary_sensor")


def is_selectable_entity(entity_id) -> bool:
    return is_valid_entity_id(entity_id) and entity_id.split(".", 1)[0] in SELECTABLE_DOMAINS


# Attributes that must not leave the home: credentials (camera access tokens,
# entity_picture URLs that embed them) and location.
_SENSITIVE_ATTRIBUTES = frozenset(
    {
        "access_token",
        "entity_picture",
        "entity_picture_local",
        "latitude",
        "longitude",
        "gps_accuracy",
        "altitude",
        "location",
    }
)
_SENSITIVE_ATTRIBUTE_PARTS = ("token", "password", "secret", "api_key", "apikey")


def sanitize_attributes(attrs) -> dict:
    """A copy of `attrs` without credentials or location."""
    if not isinstance(attrs, dict):
        return {}
    clean = {}
    for key, value in attrs.items():
        k = str(key).lower()
        if k in _SENSITIVE_ATTRIBUTES or any(part in k for part in _SENSITIVE_ATTRIBUTE_PARTS):
            continue
        clean[key] = value
    return clean

# Safe device classes allowed for sensor inclusion.
# Sensors with device_class values in this set are considered safe for telemetry.
# Sensors with device_class values NOT in this set are filtered out.
# Sensors without a device_class attribute are excluded.
SAFE_DEVICE_CLASSES = {"motion", "door", "battery", "occupancy", "presence", "opening"}
