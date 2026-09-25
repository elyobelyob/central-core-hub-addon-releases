#!/usr/bin/env python3
"""
Simple resilient MQTT client using paho-mqtt for the Central Core Hub add-on.

Responsibilities:
- Read options from `/data/options.json` (Home Assistant add-on options)
- Maintain a single persistent MQTT connection
- Publish telemetry every 30s to `telemetry/{client_id}`
- Subscribe to Vault-style command topics `hubs/{client_id}/v1/cmd/...` and handle commands
- Reconnect automatically and log connection lifecycle to stdout
"""

import importlib.util
import json
import os
import pathlib
import queue
import re
import socket
import sys
import tempfile
import threading
import time
import traceback
import typing
from datetime import datetime, timezone
from typing import cast

# Get the local timezone for timestamp normalization
_LOCAL_TZ = datetime.now().astimezone().tzinfo

# Device class filtering is handled by MQTT vault requests (authoritative source).
# fetch_sensors() returns all sensors without client-side device class restrictions.

# Outbox configuration: persistent file location and maximum queued items.
# Default file is under the add-on data directory so it survives upgrades.
OUTBOX_FILE = pathlib.Path(os.environ.get("MQTT_OUTBOX_FILE") or "/data/outbox.jsonl")
OUTBOX_MAX = int(os.environ.get("MQTT_OUTBOX_MAX") or "1000")
OUTBOX_MAX_BYTES = int(os.environ.get("MQTT_OUTBOX_MAX_BYTES") or str(1024 * 1024))
OUTBOX_TOPICS = os.environ.get("MQTT_OUTBOX_TOPICS")


def _normalize_timestamp(ts_str):
    """Normalize timestamp string to hub's local timezone ISO format.

    Parses ISO timestamp strings, ensures local timezone, and formats accordingly.
    If parsing fails, returns the original string.
    """
    if not ts_str:
        return ts_str
    try:
        # Handle 'Z' suffix by replacing with +00:00 for parsing
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            # Assume naive timestamps are in local timezone
            dt = dt.replace(tzinfo=_LOCAL_TZ)
        else:
            # Convert aware timestamps to local timezone
            dt = dt.astimezone(_LOCAL_TZ)
        return dt.isoformat()
    except ValueError:
        return ts_str


def _should_persist_topic(topic: str) -> bool:
    """Decide whether a topic should be persisted to the outbox.

    By default persist Vault ACK topics (contain '/v1/ack/'), the
    configured vault topic (if present), and the preferred sensors topic
    name pattern. Users can override selection with `MQTT_OUTBOX_TOPICS`
    environment variable as a comma-separated list of substrings to match.
    """
    try:
        if not topic:
            return False
        # If explicit override provided, use substring match for any entry
        if OUTBOX_TOPICS:
            for part in [p.strip() for p in OUTBOX_TOPICS.split(",") if p.strip()]:
                if part in topic:
                    return True
            return False
        # Default heuristics
        if "/v1/ack/" in topic:
            return True
        # vault topic typically contains 'vault' or '/vault/'
        if "vault" in topic:
            return True
        # sensors preferred topic uses 'sensors' in topic
        if "sensors" in topic:
            return True
        return False
    except Exception:
        return False


class PersistentOutbox:
    """Newline-delimited JSON outbox for messages that could not be sent.

    Each line is {"topic", "payload", "qos", "ts"}. Appends are plain appends;
    the file is rewritten only when it goes over `max_items` or `max_bytes`
    (keeping the newest entries) and when a flush removes what was sent.
    """

    def __init__(self, path: pathlib.Path, max_items: int = 1000, max_bytes: int = 1_000_000):
        self.path = pathlib.Path(path)
        self.max_items = int(max_items)
        self.max_bytes = int(max_bytes)
        self._count = None  # lines in the file; read once, then tracked
        self._lock = threading.Lock()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def has_entries(self) -> bool:
        try:
            return self.path.exists() and self.path.stat().st_size > 0
        except Exception:
            return False

    def append(self, topic: str, payload: str, qos: int = 0) -> bool:
        """Append a message. Returns True on success, False if it cannot be stored."""
        line = json.dumps({"topic": topic, "payload": payload, "qos": qos, "ts": time.time()}) + "\n"
        if len(line.encode("utf-8")) > self.max_bytes:
            return False
        try:
            with self._lock:
                if self._count is None:
                    self._count = len(self._read_all())
                with open(self.path, "a") as f:
                    f.write(line)
                self._count += 1
                if self._count > self.max_items or self.path.stat().st_size > self.max_bytes:
                    self._trim()
            return True
        except Exception:
            return False

    def _trim(self):
        """Keep the newest entries that fit both caps (caller holds the lock)."""
        entries = self._read_all()
        kept, size = [], 0
        for e in reversed(entries):
            n = len(json.dumps(e).encode("utf-8")) + 1
            if len(kept) >= self.max_items or size + n > self.max_bytes:
                break
            kept.append(e)
            size += n
        kept.reverse()
        self._write(kept)

    def _read_all(self):
        try:
            if not self.path.exists():
                return []
            with open(self.path, "r") as f:
                out = []
                for line in f.read().splitlines():
                    if not line.strip():
                        continue
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
                return out
        except Exception:
            return []

    def _write(self, entries):
        lines = [json.dumps(e) for e in entries]
        with tempfile.NamedTemporaryFile(mode="w", dir=str(self.path.parent), delete=False) as tf:
            tf.write("\n".join(lines) + ("\n" if lines else ""))
            tmp = tf.name
        pathlib.Path(tmp).replace(self.path)
        self._count = len(entries)

    def replace_all(self, entries):
        try:
            with self._lock:
                self._write(list(entries))
            return True
        except Exception:
            return False

    def flush_with_sender(self, sender_fn):
        """Send queued messages in order with sender_fn(topic, payload, qos) -> bool.

        Messages the sender refuses stay queued. Returns how many were sent.
        """
        with self._lock:
            entries = self._read_all()
        if not entries:
            return 0
        remaining = []
        success = 0
        for e in entries:
            try:
                ok = bool(sender_fn(e.get("topic"), e.get("payload"), e.get("qos", 0)))
            except Exception:
                ok = False
            if ok:
                success += 1
            else:
                remaining.append(e)
        with self._lock:
            # keep anything appended while we were sending
            appended = self._read_all()[len(entries):]
            try:
                self._write(remaining + appended)
            except Exception:
                pass
        return success


def _log(msg, file=None):
    """Log a message with UTC timestamp."""
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    print(f"[{ts}] {msg}", file=file or sys.stdout, flush=True)


# Payloads (sensor states, attributes, command bodies) are logged only when
# debug logging is on: the `debug_logging` add-on option or CC_HUB_DEBUG=1.
_DEBUG_LOGGING = os.environ.get("CC_HUB_DEBUG", "").lower() in ("1", "true", "yes")
_PREVIEW_CHARS = 300
_PEM_RE = re.compile(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", re.DOTALL)


def _log_debug(msg):
    if _DEBUG_LOGGING:
        _log(msg)


def _preview(payload, limit=_PREVIEW_CHARS):
    """A short, PEM-redacted rendering of a payload for debug logs."""
    if payload is None:
        return "<none>"
    try:
        text = payload.decode("utf-8", errors="replace") if isinstance(payload, (bytes, bytearray)) else str(payload)
    except Exception:
        return "<unprintable>"
    text = _PEM_RE.sub("[PEM REDACTED]", text)
    return text if len(text) <= limit else text[:limit] + f"...(+{len(text) - limit} chars)"


try:
    import requests
except Exception:
    requests = None


try:
    import central_core_mqtt_shared as mqtt_shared
except Exception:
    mqtt_shared = None

# Attempt to resolve `topics` from the shared package when available.
topics: typing.Any = None
if mqtt_shared is not None:
    try:
        topics = getattr(mqtt_shared, "topics")
    except Exception:
        try:
            import importlib

            topics = importlib.import_module("central_core_mqtt_shared.topics")
        except Exception:
            topics = None

# If the shared package (or its topics submodule) isn't available, prefer
# a local `mqtt_topics.py` shim next to this file (used by tests), and
# finally fall back to a minimal in-module shim.
if topics is None:
    try:
        import importlib.util as _il

        _local = pathlib.Path(__file__).parent / "mqtt_topics.py"
        if _local.exists():
            spec = _il.spec_from_file_location("local_mqtt_topics", str(_local))
            if not spec or not getattr(spec, "loader", None):
                raise RuntimeError("Could not load local mqtt_topics spec")
            lm = _il.module_from_spec(spec)
            spec.loader.exec_module(lm)  # type: ignore

            class _LocalTopics:
                TELEMETRY_SYSTEM = getattr(
                    lm, "TELEMETRY_SYSTEM", getattr(lm, "TELEMETRY_TOPIC_TMPL", "telemetry/{client_id}")
                )
                TELEMETRY_SENSORS = getattr(
                    lm,
                    "TELEMETRY_SENSORS",
                    getattr(lm, "PREFERRED_SENSORS_TOPIC_TMPL", "hubs/{hub_id}/telemetry/sensors"),
                )
                CMD_GENERIC = getattr(
                    lm, "CMD_GENERIC", getattr(lm, "CMD_BASE_TMPL", "hubs/{hub_id}/v{version}/cmd/{domain}/{action}")
                )
                ACK_GENERIC = getattr(lm, "ACK_GENERIC", "hubs/{hub_id}/v{version}/ack/{command_name}/{command_id}")

                @staticmethod
                def build_topic(tpl, **kwargs):
                    try:
                        if isinstance(tpl, str):
                            return tpl.format(**kwargs)
                        return str(tpl)
                    except Exception:
                        # Best-effort: fallback to joining parts
                        return str(tpl)

            topics = _LocalTopics()
        else:
            # Final fallback: provide a tiny shim with sensible defaults
            class _FallbackTopics:
                TELEMETRY_SYSTEM = "hubs/{hub_id}/v{version}/telemetry/system"
                TELEMETRY_SENSORS = "hubs/{hub_id}/v{version}/telemetry/sensors"
                CMD_GENERIC = "hubs/{hub_id}/v{version}/cmd/{domain}/{action}"
                ACK_GENERIC = "hubs/{hub_id}/v{version}/ack/{command_name}/{command_id}"

                @staticmethod
                def build_topic(tpl, **kwargs):
                    try:
                        if isinstance(tpl, str):
                            return tpl.format(**kwargs)
                        return str(tpl)
                    except Exception:
                        return str(tpl)

            topics = _FallbackTopics()
    except Exception:
        # As a last-resort shim that never fails import.
        class _EmptyTopics:
            TELEMETRY_SYSTEM = "telemetry/{client_id}"
            TELEMETRY_SENSORS = "hubs/{hub_id}/telemetry/sensors"
            CMD_GENERIC = "hubs/{hub_id}/v{version}/cmd/{domain}/{action}"
            ACK_GENERIC = "hubs/{hub_id}/v{version}/ack/{command_name}/{command_id}"

            @staticmethod
            def build_topic(tpl, **kwargs):
                try:
                    if isinstance(tpl, str):
                        return tpl.format(**kwargs)
                    return str(tpl)
                except Exception:
                    return str(tpl)

        topics = _EmptyTopics()

# If the environment requests strict enforcement, fail import when the
# shared package is not available. This lets CI or production environments
# opt into a strict policy while leaving development/tests permissive by
# default. Set `STRICT_SHARED=1` or `REQUIRE_SHARED=1` to enable.
if topics is None and os.environ.get("STRICT_SHARED", os.environ.get("REQUIRE_SHARED", "")):
    raise ImportError("`central_core_mqtt_shared` is required in strict mode; install it or unset STRICT_SHARED")

try:
    import paho.mqtt.client as mqtt
except Exception:
    # Do not raise during import so unit tests can import this module
    # in environments where `paho-mqtt` isn't installed. The runtime
    # CentralCoreClient will require a working `paho-mqtt` installation
    # if it is instantiated.
    _log(
        "paho-mqtt not installed; MQTT functionality disabled for import-time",
        sys.stderr,
    )
    mqtt = None

OPTIONS_PATH = "/data/options.json"
# Where a generated client id is kept when none is configured (see _derive_client_id).
CLIENT_ID_FILE = pathlib.Path(os.environ.get("CLIENT_ID_FILE") or "/data/client_id")
# Shipped as the default in earlier versions, so many hubs may share it.
SHARED_DEFAULT_CLIENT_ID = "home-assistant"
_GENERIC_HOSTNAMES = {"", "localhost", "homeassistant", "home-assistant", "hassio", "supervisor"}
MQTT_OPTIONS_ENV = "MQTT_OPTIONS_PATH"
SENSOR_REGISTRY = pathlib.Path(__file__).parent / "SENSOR_REGISTRY.yaml"

# File to persist the vault-selected sensors so selections survive restarts.
# Default to the add-on data directory (`/data`) so the file survives
# add-on upgrades. Allow overriding via the `SELECTED_SENSORS_FILE`
# environment variable for testing or alternate deployments.
_PACKAGE_SELECTED = pathlib.Path(__file__).parent / "SELECTED_SENSORS.json"
_DATA_SELECTED = pathlib.Path(os.environ.get("SELECTED_SENSORS_FILE") or "/data/SELECTED_SENSORS.json")
SELECTED_SENSORS_FILE = _DATA_SELECTED

# If an older selected-sensors file exists in the package directory (e.g.
# from a previous runtime where the file was created next to the code),
# migrate it into the add-on data directory so selections survive upgrades.
try:
    if _PACKAGE_SELECTED.exists() and not SELECTED_SENSORS_FILE.exists():
        d = SELECTED_SENSORS_FILE.parent
        d.mkdir(parents=True, exist_ok=True)
        try:
            # Copy contents to a temp file and atomically replace target
            with open(_PACKAGE_SELECTED, "r") as pf:
                content = pf.read()
            import tempfile as _temp

            with _temp.NamedTemporaryFile(mode="w", dir=str(d), delete=False) as tf:
                tf.write(content)
                tmpname = tf.name
            pathlib.Path(tmpname).replace(SELECTED_SENSORS_FILE)
        except Exception:
            # Best-effort migration; do not fail import if we can't copy
            pass
except Exception:
    # Defensive: never raise during module import
    pass
# In-memory cache for the parsed SENSOR_REGISTRY to avoid repeated disk
# reads during tight publish loops. Calls to `reload_sensor_registry()` will
# clear the cache so handlers can update the file at runtime.
_SENSOR_REGISTRY_CACHE = None
_SENSOR_REGISTRY_MTIME = None
_SENSOR_REGISTRY_DOC_CACHE = None
_SENSOR_REGISTRY_DOC_MTIME = None


def _load_sensor_registry():
    """Read and parse the SENSOR_REGISTRY.yaml file.

    Returns a list of registry entry dicts (with keys: entity_id, type, provide)
    or an empty list if the registry is not present, malformed, or not
    opted-in.
    """
    try:
        import yaml

        # Use mtime-based caching to avoid re-parsing the file every call.
        global _SENSOR_REGISTRY_CACHE, _SENSOR_REGISTRY_MTIME
        if not SENSOR_REGISTRY.exists():
            _SENSOR_REGISTRY_CACHE = []
            _SENSOR_REGISTRY_MTIME = None
            return []
        try:
            mtime = SENSOR_REGISTRY.stat().st_mtime
        except Exception:
            mtime = None
        if _SENSOR_REGISTRY_CACHE is not None and mtime is not None and mtime == _SENSOR_REGISTRY_MTIME:
            return _SENSOR_REGISTRY_CACHE
        with open(SENSOR_REGISTRY, "r") as f:
            doc = yaml.safe_load(f) or {}
        if not isinstance(doc, dict):
            _SENSOR_REGISTRY_CACHE = []
            _SENSOR_REGISTRY_MTIME = mtime
            return []
        mode = doc.get("registry_mode")
        apply_registry = bool(doc.get("apply_registry", False))
        if mode is None and not apply_registry:
            _SENSOR_REGISTRY_CACHE = []
            _SENSOR_REGISTRY_MTIME = mtime
            return []
        entries = doc.get("entries") or []
        results = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            results.append(
                {
                    "entity_id": e.get("entity_id"),
                    "type": e.get("type"),
                    "provide": e.get("provide"),
                    # optional metadata which may include device_class
                    "attributes": e.get("attributes") or {},
                    "device_class": e.get("device_class"),
                }
            )
        _SENSOR_REGISTRY_CACHE = results
        _SENSOR_REGISTRY_MTIME = mtime
        return results
    except Exception:
        return []


def _load_sensor_registry_doc():
    """Load and cache the full SENSOR_REGISTRY.yaml document dict.

    Uses mtime-based caching so the file is only read when it changes.
    Returns an empty dict if the file is absent, unreadable, or malformed.
    """
    global _SENSOR_REGISTRY_DOC_CACHE, _SENSOR_REGISTRY_DOC_MTIME
    try:
        import yaml

        if not SENSOR_REGISTRY.exists():
            _SENSOR_REGISTRY_DOC_CACHE = {}
            _SENSOR_REGISTRY_DOC_MTIME = None
            return {}
        try:
            mtime = SENSOR_REGISTRY.stat().st_mtime
        except Exception:
            mtime = None
        if _SENSOR_REGISTRY_DOC_CACHE is not None and mtime is not None and mtime == _SENSOR_REGISTRY_DOC_MTIME:
            return _SENSOR_REGISTRY_DOC_CACHE
        with open(SENSOR_REGISTRY, "r") as f:
            doc = yaml.safe_load(f) or {}
        _SENSOR_REGISTRY_DOC_CACHE = doc if isinstance(doc, dict) else {}
        _SENSOR_REGISTRY_DOC_MTIME = mtime
        return _SENSOR_REGISTRY_DOC_CACHE
    except Exception:
        return {}


def reload_sensor_registry():
    """Invalidate any cached sensor registry so subsequent calls read disk."""
    global _SENSOR_REGISTRY_CACHE, _SENSOR_REGISTRY_MTIME
    _SENSOR_REGISTRY_CACHE = None
    _SENSOR_REGISTRY_MTIME = None

    # Immediately reload and log what we're monitoring so operators can see
    # the active sensor set when a runtime update occurs.
    try:
        entries = _load_sensor_registry() or []
        provided = [e.get("entity_id") for e in entries if e.get("entity_id") and e.get("provide")]
        _log(f"Monitored sensors: {len(provided) or 'none'}")
        _log_debug(f"Monitored sensors: {', '.join(provided)}")
    except Exception:
        _log("Monitored sensors: none")


def _device_class_from_registry(entity_id: str):
    """Return a device_class for `entity_id` from the SENSOR_REGISTRY if present."""
    try:
        import fnmatch

        entries = _load_sensor_registry() or []
        for e in entries:
            pat = e.get("entity_id")
            if not isinstance(pat, str):
                continue
            try:
                if fnmatch.fnmatch(entity_id, pat):
                    # prefer explicit device_class field, then attributes.device_class
                    dc = e.get("device_class") or (e.get("attributes") or {}).get("device_class")
                    if dc:
                        return dc
            except Exception:
                continue
        return None
    except Exception:
        return None


def list_monitored_sensors():
    """Return a list of entity_ids that are currently configured to be provided.

    This consults the in-disk `SENSOR_REGISTRY` and filters entries with
    `provide` truthy. An empty list means no sensors are being monitored.
    """
    try:
        entries = _load_sensor_registry() or []
        return [e.get("entity_id") for e in entries if e.get("entity_id") and e.get("provide")]
    except Exception:
        return []


def is_entity_allowed(entity_id: str) -> bool:
    """Return True if entity_id is allowed by the registry (uses mtime cache).

    Defaults to True (allow) when the registry is absent or not enabled.
    """
    try:
        import fnmatch

        doc = _load_sensor_registry_doc()
        if not doc:
            return True
        mode = doc.get("registry_mode")
        apply_registry = bool(doc.get("apply_registry", False))
        if mode is None and not apply_registry:
            return True
        active_mode = str(mode).lower() if mode else "deny"

        allow_patterns = []
        deny_patterns = []
        for e in doc.get("entries") or []:
            if not isinstance(e, dict):
                continue
            eid = e.get("entity_id")
            prov = e.get("provide")
            if not isinstance(eid, str):
                continue
            if active_mode == "allow":
                if prov:
                    allow_patterns.append(eid)
            else:
                if prov is False:
                    deny_patterns.append(eid)

        if active_mode == "allow":
            if not allow_patterns:
                return True
            for p in allow_patterns:
                if fnmatch.fnmatch(entity_id, p):
                    return True
            return False

        if not deny_patterns:
            return True
        for p in deny_patterns:
            if fnmatch.fnmatch(entity_id, p):
                return False
        return True
    except Exception:
        return True


def _certificate_common_name(cert_path):
    """The subject CN of a PEM certificate file, or None."""
    if not cert_path:
        return None
    try:
        import ssl

        decoded = ssl._ssl._test_decode_cert(str(cert_path))  # type: ignore[attr-defined]
    except Exception:
        return None
    for rdn in decoded.get("subject", ()):
        for key, value in rdn:
            if key == "commonName" and value:
                return str(value)
    return None


def _derive_client_id(cert_path=None):
    """A client id for a hub whose client_id option is unset.

    The vault issues each hub a certificate with CN = hub id, so that comes
    first. Otherwise a specific hostname, and for generic ones (an HA OS host
    is usually "homeassistant") a random id kept in CLIENT_ID_FILE so it
    survives restarts and upgrades.
    """
    cn = _certificate_common_name(cert_path)
    if cn:
        return cn
    host = (socket.gethostname() or "").strip().lower().replace(" ", "-")
    if host not in _GENERIC_HOSTNAMES:
        return host
    try:
        saved = CLIENT_ID_FILE.read_text().strip()
        if saved:
            return saved
    except Exception:
        pass
    import secrets

    generated = f"hub-{secrets.token_hex(6)}"
    try:
        CLIENT_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        CLIENT_ID_FILE.write_text(generated + "\n")
    except Exception:
        _log(f"WARNING: could not save generated client_id to {CLIENT_ID_FILE}; it will change on restart")
    return generated


def get_addon_version():
    """Get the add-on version from config.json."""
    # Allow an explicit override via environment variable. This is useful
    # for containers, CI, or test harnesses where the runtime-installed
    # `/config.json` may be out of date or intentionally different.
    env_v = os.environ.get("ADDON_VERSION")
    if env_v:
        return env_v
    # Check add-on options (Home Assistant mounts `/data/options.json`).
    # Some add-on installers surface the installed version in the add-on
    # options or allow an `addon_version` field to be set; prefer that
    # when present so the value matches what is shown on the Add-on UI.
    try:
        if os.path.exists(OPTIONS_PATH):
            with open(OPTIONS_PATH, "r") as f:
                try:
                    opts = json.load(f) or {}
                    ver = opts.get("addon_version") or opts.get("version")
                    if ver:
                        return ver
                except Exception:
                    pass
    except Exception:
        pass
    # Try HA add-on location first
    try:
        with open("/config.json", "r") as f:
            config = json.load(f)
            version = config.get("version")
            if version:
                return version
    except Exception:
        pass

    # Fallback to development location
    try:
        config_path = pathlib.Path(__file__).parent / "config.json"
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("version")
    except Exception:
        return None


def _resolve_options_path():
    """Return the options file path, respecting the environment override."""
    return os.environ.get(MQTT_OPTIONS_ENV, OPTIONS_PATH)


def load_options():
    # Resolve primary path and fall back to the default add-on location.
    candidates = []
    primary = _resolve_options_path()
    if primary:
        candidates.append(primary)
    if OPTIONS_PATH not in candidates:
        candidates.append(OPTIONS_PATH)

    for path in candidates:
        if not path:
            continue
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            continue
    return {}


# Prefer importing helpers/telemetry modules, but support file-local import
try:
    # try standard local import (works when tests adjust sys.path or package context)
    import helpers as _helpers_mod
    import telemetry as _tele_mod

    uptime_seconds = _helpers_mod.uptime_seconds
    loadavg = _helpers_mod.loadavg
    mem_info_kb = _helpers_mod.mem_info_kb
    disk_info_kb = _helpers_mod.disk_info_kb
    _read_proc_stat = _helpers_mod._read_proc_stat
    get_cpu_percent = _helpers_mod.get_cpu_percent

    # wrap telemetry.build_telemetry to inject this module's get_cpu_percent at call time
    def _bt_from_mod(
        client_id,
        cpu_percent_fn=None,
        uptime_fn=None,
        loadavg_fn=None,
        mem_info_fn=None,
        disk_info_fn=None,
        version=None,
        telemetry_interval=None,
        home_assistant=None,
    ):
        return _tele_mod.build_telemetry(
            client_id,
            get_cpu_percent=cpu_percent_fn or get_cpu_percent,
            uptime_fn=uptime_fn,
            loadavg_fn=loadavg_fn,
            mem_info_fn=mem_info_fn,
            disk_info_fn=disk_info_fn,
            version=version or get_addon_version(),
            telemetry_interval=telemetry_interval if telemetry_interval is not None else 30,
            home_assistant=home_assistant,
        )

    build_vault_payload = _tele_mod.build_vault_payload
    # expose a single name for analyzers: assign the implementation
    build_telemetry = _bt_from_mod
except Exception:
    # Fallback: load modules relative to this file using importlib
    _base = pathlib.Path(__file__).parent
    try:
        spec_h = importlib.util.spec_from_file_location("cc_helpers", str(_base / "helpers.py"))
        if spec_h is None or spec_h.loader is None:
            raise ImportError("could not load helpers spec")
        _helpers = importlib.util.module_from_spec(spec_h)
        # register under the spec name if available
        if getattr(spec_h, "name", None):
            sys.modules[spec_h.name] = _helpers
        spec_h.loader.exec_module(_helpers)
        uptime_seconds = _helpers.uptime_seconds
        loadavg = _helpers.loadavg
        mem_info_kb = _helpers.mem_info_kb
        disk_info_kb = _helpers.disk_info_kb
        _read_proc_stat = _helpers._read_proc_stat
        get_cpu_percent = _helpers.get_cpu_percent
    except Exception:
        # define fallback helpers if local helpers import fails
        def uptime_seconds():
            try:
                with open("/proc/uptime", "r") as f:
                    return int(float(f.readline().split()[0]))
            except Exception:
                return None

        def loadavg():
            try:
                with open("/proc/loadavg", "r") as f:
                    parts = f.readline().split()
                    return parts[0:3]
            except Exception:
                return []

        def mem_info_kb():
            try:
                m = {}
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            m[parts[0].rstrip(":")] = int(parts[1])
                return m.get("MemTotal"), m.get("MemFree")
            except Exception:
                return None, None

        def disk_info_kb(path="/"):
            try:
                st = os.statvfs(path)
                total = (st.f_blocks * st.f_frsize) // 1024
                free = (st.f_bavail * st.f_frsize) // 1024
                return total, free
            except Exception:
                return None, None

    try:
        spec_t = importlib.util.spec_from_file_location("cc_telemetry", str(_base / "telemetry.py"))
        if spec_t is None or spec_t.loader is None:
            raise ImportError("could not load telemetry spec")
        _tele = importlib.util.module_from_spec(spec_t)
        if getattr(spec_t, "name", None):
            sys.modules[spec_t.name] = _tele
        spec_t.loader.exec_module(_tele)

        # build_telemetry wrapper injects this module's get_cpu_percent
        def _bt_from_file(
            client_id,
            cpu_percent_fn=None,
            uptime_fn=None,
            loadavg_fn=None,
            mem_info_fn=None,
            disk_info_fn=None,
            version=None,
            telemetry_interval=None,
            home_assistant=None,
        ):
            return _tele.build_telemetry(
                client_id,
                get_cpu_percent=cpu_percent_fn or get_cpu_percent,
                uptime_fn=uptime_fn,
                loadavg_fn=loadavg_fn,
                mem_info_fn=mem_info_fn,
                disk_info_fn=disk_info_fn,
                version=version or get_addon_version(),
                telemetry_interval=telemetry_interval or 30,
                home_assistant=home_assistant,
            )

        build_vault_payload = _tele.build_vault_payload
        # expose a single name for analyzers: assign the implementation
        build_telemetry = _bt_from_file
    except Exception:

        def _bt_simple(client_id):
            return json.dumps({"client_id": client_id})

        def _bv_simple(_raw):
            return None

        # expose a single name for analyzers: assign the simple implementations
        build_telemetry = _bt_simple
        build_vault_payload = _bv_simple


# Wrap whichever `build_telemetry` we have so tests that monkeypatch
# `get_cpu_percent` on the `mqtt_client` module are respected. This sets
# a temporary override attribute on the telemetry module before invoking
# the original function.
try:
    _orig_bt = build_telemetry

    def _wrapped_build_telemetry(client_id, version=None, telemetry_interval=None, **kwargs):
        modname = getattr(_orig_bt, "__module__", None)
        tele_mod = sys.modules.get(modname) if modname else None
        old = None
        if tele_mod is not None:
            old = getattr(tele_mod, "_external_get_cpu_percent", None)
            try:
                # cast to Any so static analyzers allow assigning a dynamic attribute
                setattr(cast(typing.Any, tele_mod), "_external_get_cpu_percent", get_cpu_percent)
            except Exception:
                pass
        try:
            # Inspect the target's signature and only pass parameters it
            # actually accepts. Build a kwargs dict dynamically to avoid
            # static-analysis complaints about unknown parameter names.
            try:
                import inspect

                sig = inspect.signature(_orig_bt)
                call_kwargs = dict(**kwargs) if kwargs is not None else {}
                # Always pass version/telemetry_interval if supported
                if "version" in sig.parameters:
                    call_kwargs["version"] = version
                if "telemetry_interval" in sig.parameters:
                    call_kwargs["telemetry_interval"] = telemetry_interval
                # Prefer the two common cpu param names if supported
                if "cpu_percent_fn" in sig.parameters:
                    call_kwargs["cpu_percent_fn"] = get_cpu_percent
                elif "get_cpu_percent" in sig.parameters:
                    call_kwargs["get_cpu_percent"] = get_cpu_percent

                return _orig_bt(client_id, **call_kwargs)
            except Exception:
                # Fallback: try calling with minimal args
                try:
                    return _orig_bt(client_id)
                except Exception:
                    # As a last resort, re-raise to let outer finally run
                    raise
        finally:
            if tele_mod is not None:
                try:
                    if old is None:
                        delattr(cast(typing.Any, tele_mod), "_external_get_cpu_percent")
                    else:
                        setattr(cast(typing.Any, tele_mod), "_external_get_cpu_percent", old)
                except Exception:
                    pass

    build_telemetry = _wrapped_build_telemetry
except Exception:
    pass


def get_cpu_percent():  # noqa: F811
    # Simple /proc/stat based CPU percentage over short interval
    idle1, total1 = _read_proc_stat()
    # Ensure values are present and numeric before arithmetic to satisfy
    # static analyzers that don't narrow types returned as `Any` or
    # `Optional[int]`.
    if idle1 is None or total1 is None:
        return None
    time.sleep(0.1)
    idle2, total2 = _read_proc_stat()
    if idle2 is None or total2 is None:
        return None
    try:
        # Coerce to ints; if this fails, treat as unavailable
        idle1_i = int(idle1)
        total1_i = int(total1)
        idle2_i = int(idle2)
        total2_i = int(total2)
    except Exception:
        return None
    if total2_i == total1_i:
        return None
    idle_delta = idle2_i - idle1_i
    total_delta = total2_i - total1_i
    try:
        usage = (1.0 - (idle_delta / total_delta)) * 100.0
        return round(usage, 1)
    except Exception:
        return None


def _sanitize_attributes(attrs):
    import ha_safety

    return ha_safety.sanitize_attributes(attrs)


def _is_selectable_entity(entity_id):
    import ha_safety

    return ha_safety.is_selectable_entity(entity_id)


def fetch_selected_sensors(ha_api_url, ha_api_token, entity_ids):
    """States of just `entity_ids` (one GET per id), minus registry-denied ones."""
    if not ha_api_url or not ha_api_token or requests is None:
        return None
    import ha_client

    states = ha_client.fetch_sensors_by_ids(ha_api_url, ha_api_token, entity_ids, requests_mod=requests)
    if states is None:
        return None
    return [s for s in states if is_entity_allowed(s.get("entity_id"))]


def fetch_sensors(ha_api_url, ha_api_token, _safe_device_classes=None):
    if not ha_api_url or not ha_api_token or requests is None:
        return None

    try:
        url = ha_api_url.rstrip("/") + "/api/states"
        headers = {
            "Authorization": f"Bearer {ha_api_token}",
            "Content-Type": "application/json",
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        sensors = []
        for ent in data:
            ent_id = ent.get("entity_id")
            if not ent_id:
                continue
            if not (ent_id.startswith("sensor.") or ent_id.startswith("binary_sensor.")):
                continue

            attrs = _sanitize_attributes(ent.get("attributes"))
            # Device class resolution deferred until after registry check
            sensors.append(
                {
                    "entity_id": ent_id,
                    "state": ent.get("state"),
                    "name": attrs.get("friendly_name") or ent_id,
                    "attributes": attrs,
                    "device_class": attrs.get("device_class") if isinstance(attrs, dict) else None,
                    "last_changed": _normalize_timestamp(ent.get("last_changed")),
                    "last_updated": _normalize_timestamp(ent.get("last_updated")),
                }
            )

        # Consult SENSOR_REGISTRY if present. Registry is the source-of-truth:
        reg = _load_sensor_registry()
        if not reg:
            return sensors

        # If registry is present, ensure sensors have device_class either from
        # HA attributes or from the registry; exclude those without one.
        resolved = []
        for s in sensors:
            ent_id = s.get("entity_id")
            dc = s.get("device_class")
            if not dc:
                try:
                    dc = _device_class_from_registry(ent_id)
                except Exception:
                    dc = None
            if not dc:
                continue
            s["device_class"] = dc
            resolved.append(s)
        sensors = resolved

        import fnmatch

        # obtain the registry_mode from the file top-level if present
        mode = None
        try:
            with open(SENSOR_REGISTRY, "r") as _f:
                import yaml as _yaml

                _doc = _yaml.safe_load(_f) or {}
                if isinstance(_doc, dict):
                    mode = _doc.get("registry_mode")
        except Exception:
            mode = None

        active_mode = str(mode).lower() if mode else "deny"

        allow_patterns = []
        deny_patterns = []
        for e in reg:
            eid = e.get("entity_id")
            prov = e.get("provide")
            if not isinstance(eid, str):
                continue
            if active_mode == "allow":
                if prov:
                    allow_patterns.append(eid)
            else:
                if prov is False:
                    deny_patterns.append(eid)

        if active_mode == "allow":
            if not allow_patterns:
                return sensors
            filtered = []
            for s in sensors:
                ent = s.get("entity_id")
                for p in allow_patterns:
                    if fnmatch.fnmatch(ent, p):
                        filtered.append(s)
                        break
            return filtered

        # deny mode
        if not deny_patterns:
            return sensors
        filtered = []
        for s in sensors:
            ent = s.get("entity_id")
            denied = False
            for p in deny_patterns:
                if fnmatch.fnmatch(ent, p):
                    denied = True
                    break
            if not denied:
                filtered.append(s)
        return filtered
    except Exception:
        return None


class CentralCoreClient:
    def __init__(self, options):
        self.options = options
        self.mqtt_host = options.get("mqtt_host") or os.environ.get("MQTT_HOST", "")
        self.mqtt_port = int(options.get("mqtt_port") or os.environ.get("MQTT_PORT", 1883))
        self.mqtt_username = options.get("mqtt_username") or ""
        self.mqtt_password = options.get("mqtt_password") or ""
        self.mqtt_tls = bool(options.get("mqtt_tls"))
        if not self.mqtt_tls:
            _log("WARNING: mqtt_tls is off; the MQTT password and all telemetry travel unencrypted")
        self.mqtt_ca = ""
        self.mqtt_cert = ""
        self.mqtt_key = ""
        self.mqtt_cert_bundle = options.get("mqtt_cert_bundle") or ""
        # Must be initialized before _setup_cert_files() which calls _handle_cert
        self._temp_cert_files = []
        # Handle certificate content vs paths
        self._setup_cert_files()
        configured_id = str(options.get("client_id") or "").strip()
        if configured_id:
            self.client_id = configured_id
            if configured_id == SHARED_DEFAULT_CLIENT_ID:
                _log(
                    f"WARNING: client_id is the shared default {configured_id!r}; hubs using it receive "
                    "each other's commands. Set a unique client_id (the vault's hub id)."
                )
        else:
            self.client_id = _derive_client_id(self.mqtt_cert)
            _log(f"client_id not set; using {self.client_id!r}")
        cert_cn = _certificate_common_name(self.mqtt_cert)
        if cert_cn and cert_cn != self.client_id:
            _log(f"WARNING: client_id {self.client_id!r} differs from the client certificate CN {cert_cn!r}")
        self.ha_api_url = options.get("ha_api_url") or ""
        self.ha_api_token = options.get("ha_api_token") or ""
        if self.ha_api_url and self.ha_api_token:
            import ha_safety

            ok, why = ha_safety.check_token_transport(self.ha_api_url)
            if not ok:
                _log(
                    f"ERROR: not sending the Home Assistant token over unencrypted {self.ha_api_url!r}: {why}. "
                    "Use http://localhost:8123 (or https://). Home Assistant integration is disabled."
                )
                self.ha_api_url = ""
                self.ha_api_token = ""
            elif why != "encrypted" and why != "local name" and why != "local address":
                _log(f"WARNING: Home Assistant URL {self.ha_api_url!r}: {why}")
        if options.get("debug_logging"):
            global _DEBUG_LOGGING
            _DEBUG_LOGGING = True
        # Load safe device classes from options (vault is authoritative for filtering)
        # Default to common safe device classes if not configured
        configured_safe = options.get("safe_device_classes")
        if isinstance(configured_safe, list):
            cleaned_safe = [str(cls).strip().lower() for cls in configured_safe if cls is not None and str(cls).strip()]
        else:
            # Default safe device classes for initial sensor publish
            cleaned_safe = ["battery", "door", "motion", "occupancy", "plug", "presence", "window"]
        self.safe_device_classes = cleaned_safe
        # Diagnostic: log whether HA options are present (do not print token)
        try:
            _log(
                f"HA config: ha_api_url={'set' if self.ha_api_url else 'unset'}, ha_api_token={'set' if self.ha_api_token else 'unset'}"
            )
        except Exception:
            pass
        # Whether to read back authoritative values from HA after a set operation.
        # Default True for backwards compatibility; can be disabled in options
        # to avoid an extra GET call when not desired.
        self.ha_readback_after_set = bool(options.get("ha_readback_after_set", True))
        # Optional vault-compatible topic to publish telemetry to in addition
        # to the default `telemetry/{client_id}` topic. If set, telemetry
        # payloads will be published to both topics.
        self.vault_topic = options.get("vault_topic") or ""
        self.telemetry_interval = int(options.get("telemetry_interval", 30))
        # Track when we last logged monitored sensors (epoch seconds)
        self._last_monitor_log = 0
        # Use the authoritative `central_core_mqtt_shared` package for topic
        # templates. The shared package is required in production; fail fast
        # if expected templates are missing so deployments do not run with
        # inconsistent or legacy topic formats.
        try:
            # Build the authoritative topics using the shared package helper.
            # Use protocol version 1 (current default in the shared package).
            ver = 1
            self.telemetry_topic = topics.build_topic(topics.TELEMETRY_SYSTEM, hub_id=self.client_id, version=ver)
            self.preferred_sensors_topic = topics.build_topic(
                topics.TELEMETRY_SENSORS, hub_id=self.client_id, version=ver
            )
            # Subscribe to hub command space using the generic command template
            # with single-level wildcards for domain/action.
            self.cmd_sub_topic = topics.build_topic(
                topics.CMD_GENERIC,
                hub_id=self.client_id,
                version=ver,
                domain="+",
                action="+",
            )
            self.status_offline_topic = topics.build_topic(
                getattr(topics, "STATUS_OFFLINE", "hubs/{hub_id}/v{version}/status/offline"),
                hub_id=self.client_id,
                version=ver,
            )
            # Commands topic (logical base) - alias for subscription pattern
            self.commands_topic = self.cmd_sub_topic
            # expose sensors_topic for compatibility; prefer preferred_sensors_topic
            self.sensors_topic = self.preferred_sensors_topic
        except Exception as e:
            raise RuntimeError(
                (
                    "central_core_mqtt_shared is missing required topic templates; "
                    "ensure the package is installed and up-to-date"
                )
            ) from e

        # Delegate client creation and TLS setup to mqtt_runtime so it can
        # be unit-tested separately and to keep this class focused on
        # higher-level behavior.
        try:
            # Prefer simple local import when available (tests run with
            # package context that allows this).
            from mqtt_runtime import setup_mqtt_client

            setup_mqtt_client(self, mqtt)
        except Exception:
            # Fallback: load the runtime helper relative to this file
            try:
                _base = pathlib.Path(__file__).parent
                spec_rt = importlib.util.spec_from_file_location("cc_mqtt_runtime", str(_base / "mqtt_runtime.py"))
                if spec_rt is None or spec_rt.loader is None:
                    raise ImportError("could not load mqtt_runtime spec")
                _rt = importlib.util.module_from_spec(spec_rt)
                if getattr(spec_rt, "name", None):
                    sys.modules[spec_rt.name] = _rt
                spec_rt.loader.exec_module(_rt)
                _rt.setup_mqtt_client(self, mqtt)
            except Exception:
                # If even the fallback fails, preserve previous behavior as best-effort
                # by creating a minimal shim client so the instance is usable during tests.
                class _ClientShim:
                    def __init__(self, *_a, **_k):
                        pass

                    def username_pw_set(self, _u, _p=None):
                        return None

                    def tls_set(self, **_kw):
                        return None

                    def publish(self, *_args, **_kwargs):
                        class R:
                            rc = 0

                        return R()

                    def subscribe(self, *_args, **_kwargs):
                        return (0, 1)

                    def connect(self, *_a, **_k):
                        return 0

                    def loop_start(self):
                        return None

                    def loop_stop(self):
                        return None

                    def disconnect(self):
                        return None

                self._client = _ClientShim()

        # Persistent outbox for queued outbound messages (best-effort)
        try:
            self._outbox = PersistentOutbox(OUTBOX_FILE, max_items=OUTBOX_MAX, max_bytes=OUTBOX_MAX_BYTES)
        except Exception:
            self._outbox = None

        self._connected = False
        self._stop_event = threading.Event()
        # Work that may wait on Home Assistant (command handlers, the
        # on-connect sensor publish) runs here, not on paho's network thread.
        self._work_queue = queue.Queue()
        self._worker = None
        # Cache the last HA version we observed so telemetry can reuse it
        self._ha_version_cache = None
        # track last sensors publish time (epoch seconds)
        self._last_sensors_sent = 0
        # the list of sensor entity_ids that Vault has indicated are selected
        # Vault is considered authoritative for selections when it requests/sets
        # them; handlers will update this list accordingly.
        self._selected_sensor_cache = {}
        self._selected_sensors = []
        self._selected_sensors_set = set()
        # Load any persisted selected sensors so selections survive restarts
        try:
            # Default to empty list; file may not exist in many environments
            sel = []
            try:
                if SELECTED_SENSORS_FILE.exists():
                    with open(SELECTED_SENSORS_FILE, "r") as f:
                        import json

                        data = json.load(f)
                        if isinstance(data, list):
                            sel = data
            except Exception:
                sel = []
            self.selected_sensors = sel
        except Exception:
            # Fallback: ensure property initialized
            self.selected_sensors = []
        # HA websocket listener instance (populated when HA integration configured)
        self._ha_ws_listener = None
        self._addon_slug = None
        # Try to start HA websocket listener if HA API config present
        try:
            _log("Evaluating HA websocket startup conditions")
            if self.ha_api_url and self.ha_api_token:
                _log("HA websocket config present; attempting listener setup")
                try:
                    import ha_client as _ha

                    try:
                        # Pass an on_ha_version callback when supported by the
                        # listener implementation. Older test fakes may not accept
                        # the kwarg, so fall back to constructing without it.
                        cls = getattr(_ha, "HAWebSocketListener")
                        listener_kwargs = dict(
                            on_event=self._on_ha_state_event,
                            log_fn=_log,
                            selectors=self._selected_sensors_set,
                            on_ha_version=self._on_ha_version,
                        )
                        try:
                            self._ha_ws_listener = cls(
                                self.ha_api_url,
                                self.ha_api_token,
                                on_snapshot=self._on_ha_snapshot,
                                **listener_kwargs,
                            )
                        except TypeError:
                            # listener without snapshot support: per-entity events only
                            self._ha_ws_listener = cls(self.ha_api_url, self.ha_api_token, **listener_kwargs)
                        started = self._ha_ws_listener.start()
                        _log(f"HA WS listener started={started}")
                        # Log which sensors the websocket is currently monitoring
                        _log(f"HA WS monitoring sensors: {len(self._selected_sensors_set) or 'none'}")
                    except Exception:
                        _log("Failed to start HA WS listener")
                        traceback.print_exc()
                        self._ha_ws_listener = None
                except Exception:
                    # ha_client not available or import failed
                    _log("HA WS helper import failed")
                    traceback.print_exc()
                    self._ha_ws_listener = None
            else:
                _log("HA websocket config missing; listener disabled")
        except Exception:
            # Non-fatal
            _log("Unexpected error during HA WS setup")
            traceback.print_exc()
            self._ha_ws_listener = None

    def start_worker(self):
        """Start the worker thread; from now on _submit() queues instead of running inline."""
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.is_alive():
            return
        if getattr(self, "_work_queue", None) is None:
            self._work_queue = queue.Queue()
        self._worker = threading.Thread(target=self._work_loop, name="hub-worker", daemon=True)
        self._worker.start()

    def stop_worker(self, timeout=5):
        worker = getattr(self, "_worker", None)
        if worker is None:
            return
        self._work_queue.put(None)
        worker.join(timeout)
        self._worker = None

    def _work_loop(self):
        while True:
            job = self._work_queue.get()
            try:
                if job is None:
                    return
                fn, args = job
                try:
                    fn(*args)
                except Exception:
                    _log(f"Worker job {getattr(fn, '__name__', fn)} failed", sys.stderr)
                    traceback.print_exc()
            finally:
                self._work_queue.task_done()

    def _submit(self, fn, *args):
        """Run `fn(*args)` on the worker thread, or inline when no worker runs."""
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.is_alive():
            self._work_queue.put((fn, args))
        else:
            fn(*args)

    def wait_for_commands(self, timeout=None):
        """Wait until queued work is done; True if it finished within `timeout`."""
        q = getattr(self, "_work_queue", None)
        if q is None:
            return True
        deadline = None if timeout is None else time.monotonic() + timeout
        while q.unfinished_tasks:
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.01)
        return True

    def _update_ha_listener_selectors(self):
        listener = getattr(self, "_ha_ws_listener", None)
        if listener is None:
            return
        updater = getattr(listener, "update_selectors", None)
        if not callable(updater):
            return
        try:
            updater(self._selected_sensors_set)
        except Exception:
            pass

    def _prune_selected_sensor_cache(self):
        if not self._selected_sensors_set:
            self._selected_sensor_cache = {}
            return
        self._selected_sensor_cache = {
            entity: value
            for entity, value in self._selected_sensor_cache.items()
            if entity in self._selected_sensors_set
        }

    @property
    def selected_sensors(self):
        return list(self._selected_sensors)

    @selected_sensors.setter
    def selected_sensors(self, value):
        try:
            new_list = list(value) if value else []
        except Exception:
            new_list = []
        self._selected_sensors = new_list
        self._selected_sensors_set = set(new_list)
        self._prune_selected_sensor_cache()
        self._update_ha_listener_selectors()

    def build_ack_topic(self, action, command_id):
        """Build a versioned ACK topic for the given action and command_id.

        Prefer an ACK template from the optional `central_core_mqtt_shared`
        package (attribute name `ACK_TMPL`) if available; otherwise fall
        back to the canonical f-string used previously.
        """
        key = action.replace("/", ".") if isinstance(action, str) else str(action)
        # Use the shared package ACK template (ACK_GENERIC) via topics.build_topic.
        try:
            return topics.build_topic(
                topics.ACK_GENERIC,
                hub_id=self.client_id,
                version=1,
                command_name=key,
                command_id=command_id,
            )
        except Exception:
            # If the shared package is present but ACK template missing, raise
            raise RuntimeError("central_core_mqtt_shared missing ACK template")

    def _setup_cert_files(self):
        """Handle certificate content vs file paths, and parse bundle if provided."""

        def _sanitize_for_logging(text):
            import re

            safe = str(text) if text is not None else ""
            stripped = safe.strip()
            # Mask JSON blobs to avoid leaking certificates/keys
            if stripped.startswith("{") or stripped.startswith("["):
                return "[REDACTED JSON payload]"
            safe = re.sub(
                r"-----BEGIN CERTIFICATE-----[^-]*-----END CERTIFICATE-----",
                "[CERTIFICATE REDACTED]",
                safe,
                flags=re.DOTALL,
            )
            safe = re.sub(
                r"-----BEGIN PRIVATE KEY-----[^-]*-----END PRIVATE KEY-----",
                "[PRIVATE KEY REDACTED]",
                safe,
                flags=re.DOTALL,
            )
            safe = re.sub(
                r"-----BEGIN [^-]*-----[^-]*-----END [^-]*-----",
                "[CERT DATA REDACTED]",
                safe,
                flags=re.DOTALL,
            )
            return safe

        def _read_content_or_file(value):
            if not value:
                return ""
            if isinstance(value, str) and value.startswith("-----BEGIN"):
                return value
            else:
                try:
                    with open(value, "r") as f:
                        return f.read()
                except Exception:
                    safe_value = _sanitize_for_logging(value)
                    _log(f"Warning: Could not read cert file {safe_value}")
                    return ""

        def _apply_bundle_from_json(value):
            data = value
            if isinstance(value, str):
                try:
                    data = json.loads(value)
                except Exception:
                    return False
            if not isinstance(data, dict):
                return False
            candidates = data.get("certificates") or data.get("certs") or data.get("certificate_bundle")
            if not isinstance(candidates, dict):
                return False
            applied = False
            mapping = {
                "ca_cert": "mqtt_ca",
                "client_cert": "mqtt_cert",
                "client_key": "mqtt_key",
            }
            for json_key, attr in mapping.items():
                val = candidates.get(json_key)
                if isinstance(val, str) and val.strip():
                    if not getattr(self, attr):
                        setattr(self, attr, val)
                        applied = True
            return applied

        bundle_content = ""
        if self.mqtt_cert_bundle:
            applied = _apply_bundle_from_json(self.mqtt_cert_bundle)
            if not applied:
                bundle_content = _read_content_or_file(self.mqtt_cert_bundle)
        if bundle_content:
            self._parse_cert_bundle(bundle_content)

        # Now handle individual certs
        def _handle_cert(cert_str, suffix):
            if not cert_str:
                return ""
            if cert_str.startswith("-----BEGIN"):
                with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
                    f.write(cert_str)
                    path = f.name
                self._temp_cert_files.append(path)
                return path
            else:
                return cert_str

        self.mqtt_ca = _handle_cert(self.mqtt_ca, ".ca.crt")
        self.mqtt_cert = _handle_cert(self.mqtt_cert, ".client.crt")
        self.mqtt_key = _handle_cert(self.mqtt_key, ".client.key")

    def _parse_cert_bundle(self, bundle_content):
        """Parse a certificate bundle and set individual certs if not already set."""
        # Find all PEM blocks
        pem_pattern = r"-----BEGIN ([^-]+)-----\n(.*?)\n-----END \1-----"
        matches = re.findall(pem_pattern, bundle_content, re.DOTALL)

        certs = []
        keys = []

        for block_type, content in matches:
            full_block = f"-----BEGIN {block_type}-----\n{content}\n-----END {block_type}-----"
            if "CERTIFICATE" in block_type:
                certs.append(full_block)
            elif "PRIVATE KEY" in block_type:
                keys.append(full_block)

        # Assume first cert is CA, second is client cert
        if not self.mqtt_ca and len(certs) > 0:
            self.mqtt_ca = certs[0]
        if not self.mqtt_cert and len(certs) > 1:
            self.mqtt_cert = certs[1]
        if not self.mqtt_key and keys:
            self.mqtt_key = keys[0]

    def _publish(self, topic, payload, qos=0, persist=None):
        """Publish, log topic/length/result, and queue eligible messages that fail.

        `persist=False` never queues the message (full sensor dumps: the next
        one supersedes it); None decides by topic (_should_persist_topic).
        """
        try:
            outbox = getattr(self, "_outbox", None)
        except Exception:
            outbox = None
        length = len(payload) if payload is not None else 0
        eligible = persist is not False and _should_persist_topic(topic)
        try:
            _log_debug(f"MQTT -> PUBLISH {topic} qos={qos} len={length} payload={_preview(payload)}")
            # If not connected, only enqueue when we have a real paho MQTT
            # client (i.e. runtime) and the topic is eligible for persistence.
            # In tests the client is often a dummy shim; allow those publishes
            # to proceed so unit tests keep their expectations.
            if (
                outbox
                and (not getattr(self, "_connected", False))
                and eligible
                and (
                    mqtt is not None and isinstance(getattr(self, "_client", None), getattr(mqtt, "Client", type(None)))
                )
            ):
                try:
                    outbox.append(topic, payload if payload is not None else "", qos)
                    _log(f"MQTT OUTBOX <- {topic} len={length} (not connected)")
                    return None
                except Exception:
                    pass

            result = self._client.publish(topic, payload, qos=qos)
            # paho may return an object with rc or a tuple
            try:
                rc = getattr(result, "rc", None)
            except Exception:
                rc = None
            _log(f"MQTT -> {topic} qos={qos} len={length} rc={rc}")
            # If publish returned an rc indicating failure and outbox is enabled,
            # persist the message for retry if the topic is eligible.
            try:
                if outbox and getattr(result, "rc", 0) != 0 and eligible:
                    outbox.append(topic, payload if payload is not None else "", qos)
            except Exception:
                pass
            return result
        except Exception as exc:
            _log(f"MQTT ERROR publishing to {topic} len={length}: {type(exc).__name__}", sys.stderr)
            # On exception, persist the message if appropriate
            try:
                outbox = getattr(self, "_outbox", None)
                if outbox and eligible:
                    outbox.append(topic, payload if payload is not None else "", qos)
                    _log(f"MQTT OUTBOX <- {topic} len={length} (after error)")
            except Exception:
                pass
            return None

    def _on_ha_state_event(self, entity_id, new_state):
        """Handle HA websocket state_changed events for selected sensors."""
        if not entity_id:
            return
        if not self._selected_sensors_set or entity_id not in self._selected_sensors_set:
            return
        if not new_state:
            return

        # Respect the central SENSOR_REGISTRY: if the entity is not allowed
        # by the registry, skip publishing its state changes even if selected.
        try:
            if not is_entity_allowed(entity_id):
                _log(f"Registry denies publishing for {entity_id}; skipping")
                return
        except Exception:
            # If registry check fails, fall back to previous behavior
            pass

        if not _is_selectable_entity(entity_id):
            return

        raw_state = new_state.get("state")
        prev_value = self._selected_sensor_cache.get(entity_id)
        if prev_value == raw_state:
            return
        self._selected_sensor_cache[entity_id] = raw_state

        attrs = _sanitize_attributes(new_state.get("attributes"))
        name = attrs.get("friendly_name") or new_state.get("name") or entity_id
        enabled = not bool(attrs.get("disabled_by"))
        now_iso = datetime.now(timezone.utc).isoformat()
        # Extract device_class if present; if missing, consult SENSOR_REGISTRY
        device_classes_map = {}
        dc = attrs.get("device_class")
        if not dc:
            try:
                dc = _device_class_from_registry(entity_id)
            except Exception:
                dc = None
        if dc:
            device_classes_map[entity_id] = dc
        obs_ts = _normalize_timestamp(new_state.get("last_changed") or new_state.get("last_updated")) or now_iso
        telemetry_payload = {
            "data": {entity_id: raw_state},
            "names": {entity_id: name},
            "enabled": {entity_id: enabled},
            "attributes": {entity_id: dict(attrs)},
            "observed": {entity_id: obs_ts},
            "device_classes": device_classes_map,
            "timestamp": now_iso,
        }
        try:
            self._publish(
                self.preferred_sensors_topic,
                json.dumps(telemetry_payload),
                qos=0,
            )
            _log_debug(f"HA WS -> sent change for {entity_id}: {raw_state!r}")
        except Exception:
            _log("Failed to publish selected sensor change via HA WS", sys.stderr)
        return

    def _call_ha_service(
        self,
        domain,
        service,
        service_data=None,
        timeout=15.0,
    ):
        listener = getattr(self, "_ha_ws_listener", None)
        if listener is None:
            return None
        call_srv = getattr(listener, "call_service", None)
        if not callable(call_srv):
            return None
        try:
            return call_srv(
                domain,
                service,
                service_data=service_data,
                timeout=timeout,
            )
        except Exception:
            return None

    def _on_ha_version(self, version):
        """Callback invoked when the HA websocket listener discovers a HA version.

        Update the local cache; the next run_iteration will include it in telemetry.
        """
        if not version:
            return
        try:
            ver = str(version)
        except Exception:
            return
        self._ha_version_cache = ver
        # Once per process, now that Home Assistant is answering. Not on this
        # thread: it is the websocket receive loop, which is what delivers the
        # replies the updater waits for.
        if not getattr(self, "_auto_update_checked", False):
            self._auto_update_checked = True
            threading.Thread(target=self._switch_off_ha_auto_update, name="ha-auto-update-off",
                             daemon=True).start()

    def addon_updater(self):
        """The updater for this add-on, or None if Home Assistant isn't connected."""
        listener = getattr(self, "_ha_ws_listener", None)
        if listener is None or not callable(getattr(listener, "request", None)):
            return None
        from addon_updater import AddonUpdater

        return AddonUpdater(listener)

    def _switch_off_ha_auto_update(self):
        """Updates happen only when the vault orders them."""
        try:
            updater = self.addon_updater()
            if updater is not None and updater.disable_auto_update():
                _log("Home Assistant auto-update is off for this add-on: updates come from the vault")
        except Exception as exc:
            _log(f"Could not switch off Home Assistant auto-update: {exc}")
    def on_connect(self, client, _userdata, *args, **kwargs):
        """MQTT on_connect callback.

        Accept variable args/kwargs to be tolerant of different paho-mqtt
        versions (MQTT v3/v5 differences). Extract the return code (`rc`)
        and optional `properties` when present. Catch all exceptions so
        the paho background thread does not crash when callbacks fail.
        """
        try:
            # rc may be provided positionally or as a kwarg (different paho versions)
            rc = None
            properties = None
            if len(args) >= 1:
                rc = args[0]
            if len(args) >= 2:
                properties = args[1]
            rc = kwargs.get("rc", kwargs.get("reasonCode", rc))
            properties = kwargs.get("properties", properties)

            _log(f"Connected to MQTT broker with rc={rc}")
            try:
                # Subscribe to Vault command pattern with QoS=1
                client.subscribe(self.cmd_sub_topic, qos=1)
                _log(f"Subscribed to {self.cmd_sub_topic} (Vault command pattern)")
            except Exception:
                _log("Subscription failed", sys.stderr)
            self._connected = True
            # Anything that may wait (outbox, Home Assistant) runs on the worker.
            self._submit(self._after_connect)
        except Exception:
            # Ensure no exceptions escape the callback into paho's thread
            _log("Unhandled exception in on_connect", sys.stderr)
            traceback.print_exc()

    def _after_connect(self):
        """Work to do once connected; runs on the worker thread. (The outbox
        is flushed by the main loop.)"""
        try:
            self.publish_sensors_with_default_filter()
        except Exception:
            _log("Failed to publish default sensors on connect", sys.stderr)

    def _flush_outbox(self):
        """Send messages queued while offline (main loop, when connected)."""
        outbox = getattr(self, "_outbox", None)
        if outbox is None or not self._connected:
            return 0
        has_entries = getattr(outbox, "has_entries", None)
        if callable(has_entries) and not has_entries():
            return 0

        def _sender(t, p, q):
            try:
                return getattr(self._client.publish(t, p, qos=q), "rc", 0) == 0
            except Exception:
                return False

        flushed = outbox.flush_with_sender(_sender)
        if flushed:
            _log(f"Flushed {flushed} messages from outbox")
        return flushed

    def on_disconnect(self, _client, _userdata, *args, **kwargs):
        """MQTT on_disconnect callback.

        Be tolerant of varying callback signatures from paho-mqtt. Attempt
        to extract a return code or reason and set internal connected
        state to False. Catch all exceptions so paho's background thread
        remains running even if disconnect handling fails.
        """
        try:
            rc = None
            properties = None
            # Positional args may be (rc,) or (rc, properties, ...)
            if len(args) >= 1:
                rc = args[0]
            if len(args) >= 2:
                properties = args[1]
            # Also check kwargs for common names
            rc = kwargs.get("rc", kwargs.get("reasonCode", rc))
            properties = kwargs.get("properties", properties)

            _log(f"Disconnected from MQTT broker rc={rc}")
            self._connected = False
        except Exception:
            _log("Unhandled exception in on_disconnect", sys.stderr)
            traceback.print_exc()

    def on_message(self, _client, userdata, msg):
        try:
            try:
                payload = msg.payload.decode("utf-8", errors="replace")
            except Exception:
                payload = "<binary>"

            try:
                size = len(msg.payload)
            except Exception:
                size = "?"
            _log(f"MQTT <- {msg.topic} len={size} retain={getattr(msg, 'retain', False) is True}")
            _log_debug(f"MQTT <- {msg.topic} payload={_preview(payload)}")
            # Handlers may call Home Assistant: run them on the worker.
            self._submit(self._dispatch_message, msg, payload)
        except Exception:
            traceback.print_exc()

    def _dispatch_message(self, msg, payload):
        try:
            from handlers import handle_message as _hm
        except Exception:
            try:
                _base = pathlib.Path(__file__).parent
                spec_h = importlib.util.spec_from_file_location("cc_handlers", str(_base / "handlers.py"))
                if spec_h is None or spec_h.loader is None:
                    raise ImportError("could not load handlers spec")
                _hmod = importlib.util.module_from_spec(spec_h)
                if getattr(spec_h, "name", None):
                    sys.modules[spec_h.name] = _hmod
                spec_h.loader.exec_module(_hmod)
                _hm = _hmod.handle_message
            except Exception:
                _hm = None
        if _hm is not None:
            try:
                _hm(
                    self,
                    msg,
                    payload,
                    fetch_sensors,
                    build_telemetry,
                    build_vault_payload,
                    requests,
                )
            except Exception:
                traceback.print_exc()

    def connect(self):
        """Make the first connection, retrying with backoff until it succeeds
        or the client is stopped. After that, paho's network loop reconnects
        by itself (see connect_once)."""
        delay = 1.0
        while not self._stop_event.is_set():
            if getattr(self, "_tls_error", None):
                self.connect_once()  # logs why
                return False
            ok = self.connect_once()
            if ok:
                # wait for connection signal from on_connect handler
                if self.wait_for_connected(timeout=5):
                    return True
                _log("Connection not confirmed yet; paho keeps trying")
            else:
                _log(f"MQTT connect failed, retrying in {int(delay)}s")
            # Interruptible sleep: exits early if stop is requested
            self._stop_event.wait(timeout=delay)
            delay = min(delay * 2, 120.0)
        return False

    def connect_once(self):
        """Connect and start paho's network loop, once.

        Returns True when the loop is running (then paho handles reconnects
        with reconnect_delay_set backoff), False if the connect attempt failed.
        """
        tls_error = getattr(self, "_tls_error", None)
        if tls_error:
            _log(f"Not connecting: MQTT TLS is enabled but could not be set up ({tls_error})", sys.stderr)
            return False
        if getattr(self, "_loop_started", False):
            return True
        try:
            _log(f"Connecting to {self.mqtt_host}:{self.mqtt_port} as {self.client_id}")
            self._client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self._client.loop_start()
            self._loop_started = True
            return True
        except Exception as exc:
            _log(f"MQTT connect to {self.mqtt_host}:{self.mqtt_port} failed: {type(exc).__name__}: {exc}")
            return False

    def wait_for_connected(self, timeout=5):
        """Wait up to `timeout` seconds for the `on_connect` handler to set
        `self._connected`. Returns True if connected, False on timeout.
        """
        attempts = int(max(1, timeout / 0.5))
        for _ in range(attempts):
            if self._connected:
                return True
            time.sleep(0.5)
        return False

    def _resolve_ha_version(self):
        """Return the cached HA version or read it from helpers/options."""
        if self._ha_version_cache:
            return self._ha_version_cache

        version = None
        opts_path = None
        try:
            import ha_client as _ha

            getter = getattr(_ha, "get_ha_version", None)
            if callable(getter):
                try:
                    # Prefer a TTL-aware getter if available; fall back to
                    # a no-arg getter for older versions.
                    try:
                        version = getter(ttl_seconds=300)
                    except TypeError:
                        version = getter()
                except Exception:
                    version = None
            opts_path = getattr(_ha, "OPTIONS_PATH", None)
        except Exception:
            opts_path = None

        if not version:
            version = self._read_ha_version_from_options(opts_path)

        if not version:
            # At most every 10 minutes: the websocket normally supplies it.
            now = time.monotonic()
            last = getattr(self, "_last_ha_version_fetch", None)
            if last is None or now - last >= 600:
                self._last_ha_version_fetch = now
                version = self._fetch_ha_version_from_api()

        if version:
            try:
                version = str(version)
            except Exception:
                pass

        if version:
            self._ha_version_cache = version
        return version

    @staticmethod
    def _read_ha_version_from_options(opts_path):
        candidates = []
        if opts_path:
            candidates.append(str(opts_path))
        resolved = _resolve_options_path()
        if resolved:
            resolved_str = str(resolved)
            if resolved_str not in candidates:
                candidates.append(resolved_str)
        if not candidates:
            candidates.append("/data/options.json")
        for path in candidates:
            if not path:
                continue
            try:
                with open(path, "r") as f:
                    opts = json.load(f)
            except Exception:
                continue
            if isinstance(opts, dict):
                hv = opts.get("ha_version")
                if hv:
                    try:
                        return str(hv)
                    except Exception:
                        return hv
        return None

    def _fetch_ha_version_from_api(self):
        if not self.ha_api_url or not self.ha_api_token or requests is None:
            return None
        try:
            url = self.ha_api_url.rstrip("/") + "/api/config"
            headers = {
                "Authorization": f"Bearer {self.ha_api_token}",
                "Content-Type": "application/json",
            }
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                return data.get("version") or data.get("homeassistant_version")
        except Exception:
            pass
        return None

    def publish_telemetry(self):
        # (run_iteration refreshes telemetry_interval from the options file.)
        # Include the Home Assistant core version learned via the websocket
        # listener (memory, then the options file, then a throttled REST call).
        ha_version = self._resolve_ha_version()
        ha_info = {"core": ha_version} if ha_version else None
        if getattr(self, "_addon_version", None) is None:
            self._addon_version = get_addon_version()

        payload = build_telemetry(
            self.client_id,
            **{
                "version": self._addon_version,
                "telemetry_interval": self.telemetry_interval,
                "home_assistant": ha_info,
            },
        )
        # Ensure the emitted telemetry reflects the effective interval even if
        # an upstream schema defaults to 30s when the field is missing or None.
        try:
            if isinstance(payload, str):
                data = json.loads(payload)
                data["telemetry_interval"] = self.telemetry_interval
                payload = json.dumps(data)
        except Exception:
            pass
        try:
            self._publish(self.telemetry_topic, payload)
        except Exception:
            _log("Failed to publish telemetry")
        # Also publish to an optional vault-specific topic if configured.
        if self.vault_topic:
            try:
                vault_payload = build_vault_payload(payload)
                if vault_payload:
                    self._publish(self.vault_topic, vault_payload)
                    _log(f"Also published vault-formatted telemetry to {self.vault_topic}")
                else:
                    # Fallback: publish the full payload if transformation failed
                    self._publish(self.vault_topic, payload)
                    _log(f"Also published (fallback) telemetry to vault topic {self.vault_topic}")
            except Exception:
                _log(
                    f"Failed to publish telemetry to vault topic {self.vault_topic}",
                    sys.stderr,
                )

    def _filter_sensors_by_device_class(self, sensors, device_classes):
        """Filter sensors by device_class. If device_classes is empty, return all.

        Args:
            sensors: List of sensor objects with 'attributes' containing 'device_class'
            device_classes: List of allowed device classes (empty = return all)

        Returns:
            Filtered sensor list (only includes sensors with matching device_class)
        """
        if not device_classes:
            return sensors
        allowed_set = set(device_classes)
        filtered = []
        for s in sensors:
            attrs = s.get("attributes", {}) or {}
            dc = attrs.get("device_class")
            # Normalize to lowercase for case-insensitive comparison
            dc_normalized = str(dc).lower() if dc else None
            # Only include sensors with matching device_class
            if dc_normalized in allowed_set:
                filtered.append(s)
        return filtered

    def publish_sensors_with_default_filter(self):
        """Publish sensors filtered by safe_device_classes on initial connect.

        This provides the Vault with a safe default set of sensors without
        broadcasting all available sensors at startup.
        """
        if not self.ha_api_url or not self.ha_api_token:
            # HA integration not configured
            return
        sensors = fetch_sensors(self.ha_api_url, self.ha_api_token) or []
        # Filter by safe_device_classes if configured
        filtered = self._filter_sensors_by_device_class(sensors, self.safe_device_classes)
        now_iso = datetime.now(timezone.utc).isoformat()
        data_map = {}
        names_map = {}
        enabled_map = {}
        attrs_map = {}
        observed_map = {}
        for s in filtered or []:
            ent = s.get("entity_id")
            if not ent:
                continue
            attrs = s.get("attributes", {}) or {}
            data_map[ent] = s.get("state")
            names_map[ent] = attrs.get("friendly_name") or s.get("name") or ent
            enabled_map[ent] = not bool(attrs.get("disabled_by"))
            attrs_map[ent] = attrs
            obs = s.get("last_changed") or s.get("last_updated")
            observed_map[ent] = _normalize_timestamp(obs) if obs else now_iso
        payload = {
            "data": data_map,
            "names": names_map,
            "enabled": enabled_map,
            "attributes": attrs_map,
            "observed": observed_map,
            "timestamp": now_iso,
        }
        try:
            self._publish(self.preferred_sensors_topic, json.dumps(payload), qos=0, persist=False)
            _log(f"Published default sensors to {self.preferred_sensors_topic} (count={len(data_map)})")
        except Exception:
            _log(
                f"Failed to publish default sensors to {self.preferred_sensors_topic}",
                sys.stderr,
            )
        self._last_sensors_sent = int(time.time())

    def publish_sensors(self):
        """Fetch sensors from Home Assistant (if configured) and publish to MQTT.

        Publishes to `telemetry/<client_id>/sensors` as a JSON object:
        { schema_version: 1, client_id, timestamp, sensors: [...] }

        Note: This publishes the full list of available sensors to the Vault.
        The Vault then requests specific sensors via device_class filtering.
        The SENSOR_REGISTRY still applies as a security layer.
        """
        if not self.ha_api_url or not self.ha_api_token:
            # HA integration not configured
            return
        sensors = fetch_sensors(self.ha_api_url, self.ha_api_token) or []
        # Note: fetch_sensors already applies SENSOR_REGISTRY filtering
        payload = {
            "schema_version": 1,
            "client_id": self.client_id,
            "timestamp": datetime.now(_LOCAL_TZ).isoformat().replace("+00:00", "Z"),
            "sensors": sensors or [],
        }
        # Publish to preferred Vault topic (development-only; legacy dropped)
        try:
            self._publish(self.preferred_sensors_topic, json.dumps(payload), qos=0, persist=False)
            _log(f"Published sensors list to {self.preferred_sensors_topic} (count={len(payload['sensors'])})")
        except Exception:
            _log(
                f"Failed to publish sensors to {self.preferred_sensors_topic}",
                sys.stderr,
            )
        self._last_sensors_sent = int(time.time())

    def _ws_streaming(self):
        """True while the HA websocket delivers the selected entities' changes."""
        listener = getattr(self, "_ha_ws_listener", None)
        check = getattr(listener, "is_streaming", None)
        try:
            return bool(check()) if callable(check) else False
        except Exception:
            return False

    def publish_selected_sensor_changes(self):
        """REST fallback for selected sensors while the websocket is not streaming.

        Fetches only the selected entities (by id), and publishes the selected
        set when any of them changed since the last publish.
        """
        if not self.selected_sensors:
            return
        if self._ws_streaming():
            return
        # Require HA configuration and a functioning `requests` runtime
        # dependency. Tests should monkeypatch the module-level `requests`
        # symbol when they intend to bypass network calls.
        if not self.ha_api_url or not self.ha_api_token or requests is None:
            return
        wanted = [e for e in self.selected_sensors if _is_selectable_entity(e)]
        sensors = fetch_selected_sensors(self.ha_api_url, self.ha_api_token, wanted) or []
        self._publish_selected_states(sensors)

    def _on_ha_snapshot(self, states):
        """Current states of the watched entities, sent by HA when a websocket
        subscription starts (startup, reconnect, selection change)."""
        try:
            self._publish_selected_states(states or [])
        except Exception:
            _log("Failed to publish websocket snapshot", sys.stderr)

    def _publish_selected_states(self, sensors):
        """Publish the selected entities among `sensors` if any value changed."""
        selected_set = set(self.selected_sensors)
        filtered = [
            s
            for s in sensors
            if s.get("entity_id") in selected_set
            and _is_selectable_entity(s.get("entity_id"))
            and is_entity_allowed(s.get("entity_id"))
        ]

        data_map = {}
        names_map = {}
        enabled_map = {}
        attrs_map = {}
        observed_map = {}
        for s in filtered:
            ent = s.get("entity_id")
            if not ent:
                continue
            attrs = _sanitize_attributes(s.get("attributes"))
            data_map[ent] = s.get("state")
            names_map[ent] = attrs.get("friendly_name") or s.get("name") or ent
            enabled_map[ent] = not bool(attrs.get("disabled_by"))
            attrs_map[ent] = attrs
            obs = s.get("last_changed") or s.get("last_updated")
            observed_map[ent] = _normalize_timestamp(obs) if obs else None

        if not data_map:
            return

        snapshot = {k: data_map[k] for k in data_map.keys()}
        if snapshot == {k: self._selected_sensor_cache.get(k) for k in snapshot}:
            return

        self._selected_sensor_cache.update(snapshot)
        now_iso = datetime.now(timezone.utc).isoformat()
        telemetry_payload = {
            "data": data_map,
            "names": names_map,
            "enabled": enabled_map,
            "attributes": attrs_map,
            "observed": observed_map,
            "timestamp": now_iso,
        }
        try:
            self._publish(self.preferred_sensors_topic, json.dumps(telemetry_payload), qos=0)
        except Exception:
            _log("Failed to publish selected sensor changes", sys.stderr)

    def _refresh_telemetry_interval_from_options(self) -> bool:
        """Reload telemetry_interval from the HA options file when it changes."""
        try:
            latest = load_options()
        except Exception:
            return False
        if not isinstance(latest, dict):
            return False
        if "telemetry_interval" not in latest:
            return False
        value = latest.get("telemetry_interval")
        if value is None:
            return False
        try:
            new_interval = int(value)
        except Exception:
            return False
        if new_interval <= 0 or new_interval == self.telemetry_interval:
            return False
        old_interval = self.telemetry_interval
        self.telemetry_interval = new_interval
        try:
            _log(f"telemetry_interval updated via options: {old_interval} -> {new_interval}")
        except Exception:
            pass
        return True

    def run(self):
        self.start_worker()
        # connect first
        self.connect()
        try:
            while True:
                self.run_iteration()
                time.sleep(self.telemetry_interval)
        finally:
            # Stop HA websocket listener if running (safe/idempotent)
            try:
                listener = getattr(self, "_ha_ws_listener", None)
                if listener is not None:
                    stop_fn = getattr(listener, "stop", None)
                    if callable(stop_fn):
                        try:
                            stop_fn()
                            _log("HA WS listener stopped")
                        except Exception:
                            _log("Failed to stop HA WS listener")
                            traceback.print_exc()
                    else:
                        _log("HA WS listener has no stop() method")
                    try:
                        # Clear reference so subsequent calls are no-ops
                        self._ha_ws_listener = None
                    except Exception:
                        pass
            except Exception:
                traceback.print_exc()
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass

    def close(self):
        """Stop background listeners and disconnect MQTT (safe to call multiple times)."""
        try:
            self._stop_event.set()
        except Exception:
            pass
        try:
            self.stop_worker()
        except Exception:
            pass
        for path in list(getattr(self, "_temp_cert_files", [])):
            try:
                os.unlink(path)
            except Exception:
                pass
        self._temp_cert_files = []
        try:
            listener = getattr(self, "_ha_ws_listener", None)
            if listener is not None:
                stop_fn = getattr(listener, "stop", None)
                if callable(stop_fn):
                    try:
                        stop_fn()
                    except Exception:
                        traceback.print_exc()
                try:
                    self._ha_ws_listener = None
                except Exception:
                    pass
        except Exception:
            traceback.print_exc()
        try:
            self._client.loop_stop()
        except Exception:
            pass
        try:
            self._client.disconnect()
        except Exception:
            pass

    def run_iteration(self):
        """Single run loop iteration: reconnect if needed, publish telemetry
        and optionally publish sensors. Called every telemetry_interval seconds.
        """
        try:
            self._refresh_telemetry_interval_from_options()
        except Exception:
            pass
        if not self._connected:
            if getattr(self, "_loop_started", False):
                _log("MQTT not connected; paho is reconnecting")
            else:
                self.connect()
        try:
            self._flush_outbox()
        except Exception:
            _log("Outbox flush exception", sys.stderr)
        try:
            self.publish_telemetry()
        except Exception:
            _log("Telemetry publish exception", sys.stderr)
        try:
            self.publish_selected_sensor_changes()
        except Exception:
            _log("Selected sensor change publish exception", sys.stderr)
        # Every 5 minutes, log which sensors the HA websocket is currently
        # monitoring (selectors) and which sensors the registry provides.
        try:
            now_ts = int(time.time())
            if now_ts - getattr(self, "_last_monitor_log", 0) >= 300:
                self._last_monitor_log = now_ts
                _log(f"Periodic: HA WS monitoring sensors: {len(self._selected_sensors_set) or 'none'}")
                try:
                    provided = list_monitored_sensors()
                except Exception:
                    provided = []
                _log(f"Periodic: Registry provided sensors: {len(provided) or 'none'}")
        except Exception:
            pass
        # send telemetry every 30s; send sensors every hour
        now = int(time.time())
        try:
            if now - self._last_sensors_sent >= 3600:
                self.publish_sensors()
        except Exception:
            _log("Sensors publish exception", sys.stderr)


def main():
    options = load_options()
    # Sanitize options for logging (hide sensitive data)
    safe_options = {
        k: ("[REDACTED]" if "token" in k or "password" in k or "cert" in k else v) for k, v in options.items()
    }
    _log(f"Loaded options: {safe_options}")
    c = CentralCoreClient(options)
    _log(f"Created client with mqtt_host={c.mqtt_host}, mqtt_port={c.mqtt_port}")
    if not c.mqtt_host:
        _log(
            "ERROR: mqtt_host is not configured. Please set MQTT_HOST environment variable or configure in options.",
            sys.stderr,
        )
        return
    c.run()


if __name__ == "__main__":
    main()
