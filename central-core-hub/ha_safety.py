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


def _pick_address(addresses):
    """The address to connect to: IPv4 first (Home Assistant always listens on it),
    then IPv6. Link-local IPv6 with a zone id (fe80::1%eth0) cannot be put in a
    URL safely, so it is never picked."""
    v4 = [a for a in addresses if ":" not in a]
    v6 = [a for a in addresses if ":" in a and "%" not in a]
    return (v4 or v6 or [None])[0]


def _assess(url):
    """(ok, reason, url_to_use) for sending the token to `url`; resolves a host name at most once.

    Over plain http/ws to a host *name* (not a fixed local name, not an
    address), the address that was checked replaces the name in `url_to_use`,
    so the checked address is the one that is used. Call it for every
    connection: the answer is for this connection only (a DHCP change moves
    Home Assistant's address, so a pin must never be kept).
    """
    from urllib.parse import urlsplit

    try:
        parts = urlsplit((url or "").strip())
        host = (parts.hostname or "").lower()
    except ValueError:
        return False, "unparseable URL", url
    try:
        port = parts.port  # raises ValueError for a port out of range, e.g. :99999
    except ValueError:
        return False, "invalid port", url
    if parts.scheme in ("https", "wss"):
        return (True, "encrypted", url) if host else (False, "no host", url)
    if parts.scheme not in ("http", "ws"):
        return False, f"unsupported scheme {parts.scheme!r}", url
    if not host:
        return False, "no host", url
    if "%" in host:
        return False, "IPv6 zone ids are not supported; use another address or https", url
    if host in _LOCAL_HA_HOSTNAMES:
        return True, "local name", url
    import ipaddress

    try:
        addresses = [str(ipaddress.ip_address(host))]
        is_name = False
    except ValueError:
        is_name = True
        try:
            addresses = _resolve_host(host)
        except OSError:
            # Fail closed: a name that does not resolve now cannot be checked, and
            # may later resolve to another machine (DNS change, rebinding).
            return False, f"{host} does not resolve, so it cannot be checked to be this machine", url
    remote = [a for a in addresses if not _is_local_address(a)]
    if remote:
        return False, f"{host} is not this machine ({', '.join(remote)})", url
    if not is_name:
        return True, "local address", url
    address = _pick_address(addresses)
    if address is None:
        return False, f"{host} has only link-local IPv6 addresses with a zone id; use another address", url
    shown = f"[{address}]" if ":" in address else address
    userinfo = parts.netloc.rpartition("@")[0]
    netloc = (userinfo + "@" if userinfo else "") + shown + (f":{port}" if port else "")
    return True, f"local address ({host} pinned to {address})", parts._replace(netloc=netloc).geturl()


def check_token_transport(url):
    """(ok, reason): may the Home Assistant token be sent to `url`?"""
    ok, reason, _ = _assess(url)
    return ok, reason


def pin_token_url(url):
    """(ok, reason, url_to_use) for ONE connection or request.

    A host name in a plain http/ws URL is resolved here, checked, and the checked
    address replaces it in `url_to_use`, so this connection goes to the address
    that was checked and cannot be steered elsewhere by a DNS or mDNS answer in
    between. Call it again for the next connection; never keep the result.
    Every other URL comes back unchanged.
    """
    return _assess(url)


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
