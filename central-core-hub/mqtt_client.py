#!/usr/bin/env python3
"""
Resilient MQTT client for the Central Core Hub add-on using the versioned
Hub ↔ Vault topic namespace.

Responsibilities:
- Read options from `/data/options.json` (Home Assistant add-on options)
- Maintain a single persistent MQTT connection
- Publish system telemetry/status heartbeats on the versioned Hub → Vault topics
- Handle versioned command topics (including broadcast) with ACKs
- Reconnect automatically and log connection lifecycle to stdout
"""
import importlib.util
import json
import os
import pathlib
import re
import socket
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
# HA integration helpers (websocket + REST fetch). Load sibling file when direct
# import isn't on sys.path (e.g. tests using spec_from_file_location).
try:
    import ha_client
except Exception:
    try:
        _ha_base = pathlib.Path(__file__).resolve().parent
        _ha_spec = importlib.util.spec_from_file_location(
            "ha_client", str(_ha_base / "ha_client.py")
        )
        ha_client = importlib.util.module_from_spec(_ha_spec)
        sys.modules["ha_client"] = ha_client
        _ha_spec.loader.exec_module(ha_client)
    except Exception:
        raise
try:
    import telemetry_helpers
except Exception:
    try:
        _tele_base = pathlib.Path(__file__).resolve().parent
        _tele_spec = importlib.util.spec_from_file_location(
            "telemetry_helpers", str(_tele_base / "telemetry_helpers.py")
        )
        telemetry_helpers = importlib.util.module_from_spec(_tele_spec)
        sys.modules["telemetry_helpers"] = telemetry_helpers
        _tele_spec.loader.exec_module(telemetry_helpers)
    except Exception:
        raise

from ha_client import HAWebSocketListener, fetch_sensors, fetch_sensors_by_ids
from telemetry_helpers import (
    attach_ha_timestamps,
    build_sensor_event_payload,
    build_sensor_maps,
    normalize_sensor_value,
)

# Shared MQTT protocol (topics/schemas)
try:
    from central_core_mqtt_shared import schemas as shared_schemas
    from central_core_mqtt_shared import topics as shared_topics
    from central_core_mqtt_shared.topics import build_topic
except Exception:
    # Allow development without an installed package by falling back to a sibling checkout
    try:
        _bases = [
            pathlib.Path(__file__).resolve().parent.parent / "central-core-mqtt-shared",
            pathlib.Path(__file__).resolve().parent.parent.parent
            / "central-core-mqtt-shared",
        ]
        _base = next((b for b in _bases if b.exists()), None)
        if _base:
            sys.path.insert(0, str(_base))
            from central_core_mqtt_shared import schemas as shared_schemas
            from central_core_mqtt_shared import topics as shared_topics
            from central_core_mqtt_shared.topics import build_topic
        else:  # pragma: no cover - defensive fallback
            raise ImportError("shared package not found locally")

    except (
        Exception
    ):  # pragma: no cover - defensive fallback if even sibling import fails

        class _FallbackTopics:
            TELEMETRY_SYSTEM = "hubs/{hub_id}/v{version}/telemetry/system"
            TELEMETRY_SENSORS = "hubs/{hub_id}/v{version}/telemetry/sensors"
            TELEMETRY_EVENTS = "hubs/{hub_id}/v{version}/telemetry/events"
            TELEMETRY_GENERAL = "hubs/{hub_id}/v{version}/telemetry/general"
            STATUS_ONLINE = "hubs/{hub_id}/v{version}/status/online"
            STATUS_OFFLINE = "hubs/{hub_id}/v{version}/status/offline"
            CMD_SENSORS_POLL = "hubs/{hub_id}/v{version}/cmd/sensors/poll"
            CMD_SENSORS_SET = "hubs/{hub_id}/v{version}/cmd/sensors/set"
            CMD_CONFIG_UPDATE = "hubs/{hub_id}/v{version}/cmd/config/update"
            CMD_FIRMWARE_UPDATE = "hubs/{hub_id}/v{version}/cmd/firmware/update"
            CMD_TUNNEL_START = "hubs/{hub_id}/v{version}/cmd/tunnel/start"
            CMD_TUNNEL_STOP = "hubs/{hub_id}/v{version}/cmd/tunnel/stop"
            CMD_GENERIC = "hubs/{hub_id}/v{version}/cmd/{domain}/{action}"
            BROADCAST_CMD = "hubs/broadcast/v{version}/cmd/{command}"
            ACK_GENERIC = "hubs/{hub_id}/v{version}/ack/{command_name}/{command_id}"
            ADDON_HA_TELEMETRY = "hubs/{hub_id}/v{version}/addon/ha/telemetry"
            ADDON_HA_STATUS = "hubs/{hub_id}/v{version}/addon/ha/status"
            ADDON_HA_CMD = "hubs/{hub_id}/v{version}/addon/ha/cmd/{command}"

        class _FallbackSchemas:
            class AckStatus:
                SUCCESS = "success"
                ERROR = "error"

            class CommandName:
                SENSORS_POLL = "sensors.poll"
                SENSORS_SET = "sensors.set"
                CONFIG_UPDATE = "config.update"
                FIRMWARE_UPDATE = "firmware.update"
                TUNNEL_START = "tunnel.start"
                TUNNEL_STOP = "tunnel.stop"

            class CommandAck:
                def __init__(self, command_id, status, message=None, timestamp=None):
                    self.command_id = command_id
                    self.status = status
                    self.message = message
                    self.timestamp = timestamp

                def model_dump_json(self):
                    return json.dumps(
                        {
                            "command_id": self.command_id,
                            "status": self.status,
                            "message": self.message,
                            "timestamp": self.timestamp,
                        }
                    )

            class StatusOnline:
                def __init__(self, timestamp=None):
                    self.status = "online"
                    self.timestamp = timestamp

                def model_dump_json(self):
                    return json.dumps(
                        {"status": self.status, "timestamp": self.timestamp}
                    )

            class StatusOffline:
                def __init__(self, timestamp=None):
                    self.status = "offline"
                    self.timestamp = timestamp

                def model_dump_json(self):
                    return json.dumps(
                        {"status": self.status, "timestamp": self.timestamp}
                    )

        shared_schemas = _FallbackSchemas()
        shared_topics = _FallbackTopics()

        def build_topic(template: str, **kwargs) -> str:
            return template.format(**kwargs)


def _log(msg, file=sys.stdout):
    """Log a message with UTC timestamp."""
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    print(f"[{ts}] {msg}", file=file)


try:
    import requests
except Exception:
    requests = None

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


def get_addon_version():
    """Get the add-on version from config.json."""
    # Try HA add-on location first
    try:
        with open("/config.json", "r") as f:
            config = json.load(f)
            version = config.get("version")
            if version:
                return version
    except Exception:
        _log("Failed to read /config.json for add-on version", sys.stderr)

    # Fallback to development location
    try:
        config_path = pathlib.Path(__file__).parent / "config.json"
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("version")
    except Exception:
        return None


def load_options():
    if not os.path.exists(OPTIONS_PATH):
        return {}
    with open(OPTIONS_PATH, "r") as f:
        try:
            return json.load(f)
        except Exception:
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
    def build_telemetry(
        client_id,
        get_cpu_percent=None,
        uptime_fn=None,
        loadavg_fn=None,
        mem_info_fn=None,
        disk_info_fn=None,
        version=None,
        telemetry_interval=None,
    ):
        return _tele_mod.build_telemetry(
            client_id,
            get_cpu_percent=get_cpu_percent or get_cpu_percent,
            uptime_fn=uptime_fn,
            loadavg_fn=loadavg_fn,
            mem_info_fn=mem_info_fn,
            disk_info_fn=disk_info_fn,
            version=version or get_addon_version(),
            telemetry_interval=telemetry_interval or 30,
        )

    build_vault_payload = _tele_mod.build_vault_payload
except Exception:
    # Fallback: load modules relative to this file using importlib
    _base = pathlib.Path(__file__).parent
    try:
        spec_h = importlib.util.spec_from_file_location(
            "cc_helpers", str(_base / "helpers.py")
        )
        _helpers = importlib.util.module_from_spec(spec_h)
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
        spec_t = importlib.util.spec_from_file_location(
            "cc_telemetry", str(_base / "telemetry.py")
        )
        _tele = importlib.util.module_from_spec(spec_t)
        sys.modules[spec_t.name] = _tele
        spec_t.loader.exec_module(_tele)

        # build_telemetry wrapper injects this module's get_cpu_percent
        def build_telemetry(
            client_id,
            get_cpu_percent=None,
            uptime_fn=None,
            loadavg_fn=None,
            mem_info_fn=None,
            disk_info_fn=None,
            version=None,
            telemetry_interval=None,
        ):
            return _tele.build_telemetry(
                client_id,
                get_cpu_percent=get_cpu_percent or get_cpu_percent,
                uptime_fn=uptime_fn,
                loadavg_fn=loadavg_fn,
                mem_info_fn=mem_info_fn,
                disk_info_fn=disk_info_fn,
                version=version or get_addon_version(),
                telemetry_interval=telemetry_interval or 30,
            )

        build_vault_payload = _tele.build_vault_payload
    except Exception:

        def build_telemetry(client_id):
            return json.dumps({"client_id": client_id})

        def build_vault_payload(raw):
            return None


# Wrap whichever `build_telemetry` we have so tests that monkeypatch
# `get_cpu_percent` on the `mqtt_client` module are respected. This sets
# a temporary override attribute on the telemetry module before invoking
# the original function.
try:
    _orig_bt = build_telemetry

    def _wrapped_build_telemetry(
        client_id, version=None, telemetry_interval=None, **kwargs
    ):
        modname = getattr(_orig_bt, "__module__", None)
        tele_mod = sys.modules.get(modname) if modname else None
        old = None
        if tele_mod is not None:
            old = getattr(tele_mod, "_external_get_cpu_percent", None)
            try:
                tele_mod._external_get_cpu_percent = get_cpu_percent
            except Exception:
                traceback.print_exc()
        try:
            return _orig_bt(
                client_id,
                get_cpu_percent=get_cpu_percent,
                version=version,
                telemetry_interval=telemetry_interval,
                **kwargs,
            )
        finally:
            if tele_mod is not None:
                try:
                    if old is None:
                        delattr(tele_mod, "_external_get_cpu_percent")
                    else:
                        tele_mod._external_get_cpu_percent = old
                except Exception:
                    traceback.print_exc()

    build_telemetry = _wrapped_build_telemetry
except Exception:
    traceback.print_exc()


def _read_proc_stat():  # noqa: F811
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
            if not line.startswith("cpu "):
                return None, None
            parts = line.split()[1:]
            vals = [int(x) for x in parts]
            idle = vals[3]
            total = sum(vals)
            return idle, total
    except Exception:
        return None, None


def get_cpu_percent():  # noqa: F811
    # Simple /proc/stat based CPU percentage over short interval
    idle1, total1 = _read_proc_stat()
    if idle1 is None:
        return None
    time.sleep(0.1)
    idle2, total2 = _read_proc_stat()
    if idle2 is None or total2 is None or total2 == total1:
        return None
    idle_delta = idle2 - idle1
    total_delta = total2 - total1
    try:
        usage = (1.0 - (idle_delta / total_delta)) * 100.0
        return round(usage, 1)
    except Exception:
        return None


def fetch_sensors(ha_api_url, ha_api_token):
    """Delegate to ha_client but allow tests to override requests module."""
    return ha_client.fetch_sensors(
        ha_api_url, ha_api_token, requests_mod=requests
    )


def fetch_sensors_by_ids(ha_api_url, ha_api_token, entity_ids, requests_mod=None):
    """Delegate to ha_client when extra TTL data is needed."""
    return ha_client.fetch_sensors_by_ids(
        ha_api_url,
        ha_api_token,
        entity_ids,
        requests_mod=requests_mod or requests,
    )
class CentralCoreClient:
    def __init__(self, options):
        self.options = options
        self.mqtt_host = options.get("mqtt_host") or os.environ.get("MQTT_HOST", "")
        self.mqtt_port = int(
            options.get("mqtt_port") or os.environ.get("MQTT_PORT", 1883)
        )
        self.mqtt_username = options.get("mqtt_username") or ""
        self.mqtt_password = options.get("mqtt_password") or ""
        self.mqtt_tls = bool(options.get("mqtt_tls"))
        self.mqtt_ca = ""
        self.mqtt_cert = ""
        self.mqtt_key = ""
        self.mqtt_cert_bundle = options.get("mqtt_cert_bundle") or ""
        # Handle certificate content vs paths
        self._setup_cert_files()
        self.client_id = options.get(
            "client_id"
        ) or socket.gethostname().lower().replace(" ", "-")
        self.ha_api_url = options.get("ha_api_url") or ""
        self.ha_api_token = options.get("ha_api_token") or ""
        # Whether to read back authoritative values from HA after a set operation.
        # Default True for backwards compatibility; can be disabled in options
        # to avoid an extra GET call when not desired.
        self.ha_readback_after_set = bool(options.get("ha_readback_after_set", True))
        # Optional vault-compatible topic to publish telemetry to in addition
        # to the default `telemetry/{client_id}` topic. If set, telemetry
        # payloads will be published to both topics.
        self.vault_topic = options.get("vault_topic") or ""
        self.telemetry_interval = int(options.get("telemetry_interval", 30))
        # MQTT protocol version for versioned topics (default v1)
        self.protocol_version = int(options.get("protocol_version", 1))

        def _topic(attr, **kwargs):
            try:
                template = getattr(shared_topics, attr)
            except Exception:
                return None
            try:
                return build_topic(template, **kwargs)
            except Exception:
                return None

        # Versioned telemetry topics (Hub -> Vault)
        self.telemetry_topic = _topic(
            "TELEMETRY_SYSTEM", hub_id=self.client_id, version=self.protocol_version
        )
        self.telemetry_system_topic = self.telemetry_topic
        self.telemetry_general_topic = _topic(
            "TELEMETRY_GENERAL", hub_id=self.client_id, version=self.protocol_version
        )
        self.telemetry_events_topic = _topic(
            "TELEMETRY_EVENTS", hub_id=self.client_id, version=self.protocol_version
        )
        # Preferred sensors telemetry topic for Vault (versioned)
        self.preferred_sensors_topic = _topic(
            "TELEMETRY_SENSORS", hub_id=self.client_id, version=self.protocol_version
        )
        # Status / presence
        self.status_online_topic = _topic(
            "STATUS_ONLINE", hub_id=self.client_id, version=self.protocol_version
        )
        self.status_offline_topic = _topic(
            "STATUS_OFFLINE", hub_id=self.client_id, version=self.protocol_version
        )
        # Add-on (Home Assistant) namespace
        self.addon_telemetry_topic = _topic(
            "ADDON_HA_TELEMETRY", hub_id=self.client_id, version=self.protocol_version
        )
        self.addon_status_topic = _topic(
            "ADDON_HA_STATUS", hub_id=self.client_id, version=self.protocol_version
        )
        self.addon_cmd_sub_topic = _topic(
            "ADDON_HA_CMD",
            hub_id=self.client_id,
            version=self.protocol_version,
            command="+",
        )
        # Subscribe patterns for commands (versioned only)
        self.cmd_sub_topic = _topic(
            "CMD_GENERIC",
            hub_id=self.client_id,
            version=self.protocol_version,
            domain="+",
            action="+",
        )
        self.broadcast_cmd_topic = _topic(
            "BROADCAST_CMD", version=self.protocol_version, command="+"
        )
        # Consolidated list of command subscriptions (hub-specific + broadcast + add-on)
        self.command_subscription_topics = [
            t
            for t in (
                self.cmd_sub_topic,
                self.broadcast_cmd_topic,
                self.addon_cmd_sub_topic,
            )
            if t
        ]
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
                spec_rt = importlib.util.spec_from_file_location(
                    "cc_mqtt_runtime", str(_base / "mqtt_runtime.py")
                )
                _rt = importlib.util.module_from_spec(spec_rt)
                sys.modules[spec_rt.name] = _rt
                spec_rt.loader.exec_module(_rt)
                _rt.setup_mqtt_client(self, mqtt)
            except Exception:
                # If even the fallback fails, preserve previous behavior as best-effort
                # by creating a minimal shim client so the instance is usable during tests.
                class _ClientShim:
                    def __init__(self, *a, **k):
                        pass

                    def username_pw_set(self, u, p=None):
                        return None

                    def tls_set(self, **kw):
                        return None

                    def publish(self, topic, payload, qos=0):
                        class R:
                            rc = 0

                        return R()

                    def will_set(self, topic, payload=None, qos=0, retain=False):
                        return None

                    def subscribe(self, topic, qos=0):
                        return (0, 1)

                    def connect(self, *a, **k):
                        return 0

                    def loop_start(self):
                        return None

                    def loop_stop(self):
                        return None

                    def disconnect(self):
                        return None

                self._client = _ClientShim()

        # Configure MQTT LWT for offline status if supported
        self._configure_will()

        self._connected = False
        # optional HA websocket listener for state_changed events
        self._ha_ws_listener = None
        # track last status heartbeat publish
        self._last_status_sent = 0
        # track last sensors publish time (epoch seconds)
        self._last_sensors_sent = 0
        # the list of sensor entity_ids that Vault has indicated are selected
        # Vault is considered authoritative for selections when it requests/sets
        # them; handlers will update this list accordingly.
        self.selected_sensors = []
        # cache of last published selected sensor values for change detection
        self._selected_sensor_cache = {}

    def _setup_cert_files(self):
        """Handle certificate content vs file paths, and parse bundle if provided."""

        def _read_content_or_file(value):
            if not value:
                return ""
            if value.startswith("-----BEGIN"):
                return value
            else:
                # Assume it's a file path, try to read
                try:
                    with open(value, "r") as f:
                        return f.read()
                except Exception:
                    # Sanitize value for logging to avoid exposing certificates
                    def _sanitize_for_logging(text):
                        import re

                        # Redact certificate content
                        text = re.sub(
                            r"-----BEGIN CERTIFICATE-----[^-]*-----END CERTIFICATE-----",
                            "[CERTIFICATE REDACTED]",
                            text,
                            flags=re.DOTALL,
                        )
                        text = re.sub(
                            r"-----BEGIN PRIVATE KEY-----[^-]*-----END PRIVATE KEY-----",
                            "[PRIVATE KEY REDACTED]",
                            text,
                            flags=re.DOTALL,
                        )
                        text = re.sub(
                            r"-----BEGIN [^-]*-----[^-]*-----END [^-]*-----",
                            "[CERT DATA REDACTED]",
                            text,
                            flags=re.DOTALL,
                        )
                        return text

                    safe_value = _sanitize_for_logging(str(value))
                    _log(f"Warning: Could not read cert file {safe_value}")
                    return ""

        # If bundle is provided, parse it
        if self.mqtt_cert_bundle:
            bundle_content = _read_content_or_file(self.mqtt_cert_bundle)
            if bundle_content:
                self._parse_cert_bundle(bundle_content)

        # Now handle individual certs
        def _handle_cert(cert_str, suffix):
            if not cert_str:
                return ""
            if cert_str.startswith("-----BEGIN"):
                # It's certificate content, write to temp file
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=suffix, delete=False
                ) as f:
                    f.write(cert_str)
                    return f.name
            else:
                # It's a file path
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
            full_block = (
                f"-----BEGIN {block_type}-----\n{content}\n-----END {block_type}-----"
            )
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

    def _configure_will(self):
        """Configure MQTT LWT to publish offline status when disconnected."""
        try:
            client = getattr(self, "_client", None)
            if client is None or not hasattr(client, "will_set"):
                return
            if not self.status_offline_topic:
                return
            payload = self._build_status_payload(online=False)
            client.will_set(self.status_offline_topic, payload, qos=1, retain=False)
        except Exception:
            # Do not raise if LWT configuration fails
            traceback.print_exc()

    def _publish(self, topic, payload, qos=0):
        """Publish and log the MQTT publish action and result."""
        try:
            _log(
                f"MQTT -> PUBLISH to {topic} qos={qos} len={len(payload) if payload is not None else 0}"
            )
            result = self._client.publish(topic, payload, qos=qos)
            # paho may return an object with rc or a tuple
            try:
                rc = getattr(result, "rc", None)
            except Exception:
                rc = None
            _log(f"MQTT <- PUBLISH result for {topic} rc={rc}")
            return result
        except Exception:
            _log(f"MQTT ERROR publishing to {topic}", sys.stderr)
            traceback.print_exc()
            return None

    def _build_status_payload(self, online=True):
        """Build a status payload using shared schemas when available."""
        status_str = "online" if online else "offline"
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            schema_cls = getattr(
                shared_schemas, "StatusOnline" if online else "StatusOffline", None
            )
            if schema_cls:
                try:
                    obj = schema_cls(timestamp=time.time())
                    if hasattr(obj, "model_dump_json"):
                        return obj.model_dump_json()
                    if hasattr(obj, "json"):
                        return obj.json()
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()
        return json.dumps(
            {
                "schema_version": 1,
                "client_id": self.client_id,
                "status": status_str,
                "timestamp": now_iso,
            }
        )

    def publish_status_online(self):
        """Publish an online heartbeat to the hub and add-on status topics."""
        payload = self._build_status_payload(online=True)
        try:
            if self.status_online_topic:
                self._publish(self.status_online_topic, payload, qos=1)
                _log(f"Published status to {self.status_online_topic}")
            if self.addon_status_topic:
                self._publish(self.addon_status_topic, payload, qos=1)
                _log(f"Published add-on status to {self.addon_status_topic}")
            self._last_status_sent = int(time.time())
        except Exception:
            _log("Failed to publish status heartbeat", sys.stderr)

    def on_connect(self, client, userdata, flags, rc):
        _log(f"Connected to MQTT broker with rc={rc}")
        try:
            # Subscribe to versioned command patterns (hub + broadcast/add-on) with QoS=1
            for topic in self.command_subscription_topics or []:
                client.subscribe(topic, qos=1)
                _log(f"Subscribed to {topic} (command pattern)")
        except Exception:
            _log("Subscription failed", sys.stderr)
        self._connected = True
        # Publish status heartbeat immediately on connect
        try:
            self.publish_status_online()
        except Exception:
            _log("Failed to publish status on connect", sys.stderr)
        # Publish sensors list immediately on startup/connection
        try:
            self.publish_sensors()
        except Exception:
            # do not let sensor publish failures prevent client
            _log("Failed to publish sensors on connect", sys.stderr)
        # Publish initial telemetry on connection
        try:
            self.publish_telemetry()
        except Exception:
            _log("Failed to publish telemetry on connect", sys.stderr)

    def on_disconnect(self, client, userdata, rc):
        _log(f"Disconnected from MQTT broker rc={rc}")
        self._connected = False

    def on_message(self, client, userdata, msg):
        try:
            try:
                payload = msg.payload.decode("utf-8", errors="replace")
            except Exception:
                payload = "<binary>"

            # Sanitize payload for logging to avoid exposing certificates
            def _sanitize_payload_for_logging(text):
                import re

                # Redact certificate content
                text = re.sub(
                    r"-----BEGIN CERTIFICATE-----[^-]*-----END CERTIFICATE-----",
                    "[CERTIFICATE REDACTED]",
                    text,
                    flags=re.DOTALL,
                )
                text = re.sub(
                    r"-----BEGIN PRIVATE KEY-----[^-]*-----END PRIVATE KEY-----",
                    "[PRIVATE KEY REDACTED]",
                    text,
                    flags=re.DOTALL,
                )
                text = re.sub(
                    r"-----BEGIN [^-]*-----[^-]*-----END [^-]*-----",
                    "[CERT DATA REDACTED]",
                    text,
                    flags=re.DOTALL,
                )
                return text

            safe_payload = _sanitize_payload_for_logging(payload)
            _log(f"Received message on {msg.topic}: {safe_payload}")
            # Prefer a local import of the handlers module; fall back to
            # loading relative to the file for test contexts.
            try:
                from handlers import handle_message as _hm
            except Exception:
                try:
                    _base = pathlib.Path(__file__).parent
                    spec_h = importlib.util.spec_from_file_location(
                        "cc_handlers", str(_base / "handlers.py")
                    )
                    _hmod = importlib.util.module_from_spec(spec_h)
                    sys.modules[spec_h.name] = _hmod
                    spec_h.loader.exec_module(_hmod)
                    _hm = _hmod.handle_message
                except Exception:
                    _hm = None

            if _hm is not None:
                _hm(
                    self,
                    msg,
                    payload,
                    fetch_sensors,
                    build_telemetry,
                    build_vault_payload,
                    requests,
                )
                return
        except Exception:
            traceback.print_exc()

    def connect(self):
        # Backwards-compatible public connect method implemented in
        # terms of smaller helpers: `connect_once` and `wait_for_connected`.
        while True:
            ok = self.connect_once()
            if ok:
                # wait for connection signal from on_connect handler
                if self.wait_for_connected(timeout=5):
                    return True
                # timed out waiting for on_connect
                try:
                    _log("Connection timed out, retrying in 5s")
                except Exception:
                    traceback.print_exc()
                try:
                    self._client.loop_stop()
                except Exception:
                    traceback.print_exc()
            else:
                try:
                    _log("MQTT connect failed, retrying in 5s")
                except Exception:
                    traceback.print_exc()
            time.sleep(5)

    def connect_once(self):
        """Attempt a single connect + loop_start. Returns True on no exception.

        This helper is small and easy to unit-test (e.g. when the client
        shim raises or returns errors).
        """
        try:
            _log(f"Connecting to {self.mqtt_host}:{self.mqtt_port} as {self.client_id}")
            self._client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self._client.loop_start()
            return True
        except Exception:
            traceback.print_exc()
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

    def publish_telemetry(self):
        payload = build_telemetry(
            self.client_id,
            version=get_addon_version(),
            telemetry_interval=self.telemetry_interval,
        )
        try:
            if self.telemetry_topic:
                self._publish(self.telemetry_topic, payload)
                _log(f"Published telemetry to {self.telemetry_topic}")
        except Exception:
            _log("Failed to publish telemetry")
        # Also publish to add-on telemetry namespace if present
        try:
            if self.addon_telemetry_topic:
                self._publish(self.addon_telemetry_topic, payload)
                _log(f"Published add-on telemetry to {self.addon_telemetry_topic}")
        except Exception:
            _log("Failed to publish add-on telemetry", sys.stderr)
        # Also publish to an optional vault-specific topic if configured.
        if self.vault_topic:
            try:
                vault_payload = build_vault_payload(payload)
                if vault_payload:
                    self._publish(self.vault_topic, vault_payload)
                    _log(
                        f"Also published vault-formatted telemetry to {self.vault_topic}"
                    )
                else:
                    # Fallback: publish the full payload if transformation failed
                    self._publish(self.vault_topic, payload)
                    _log(
                        f"Also published (fallback) telemetry to vault topic {self.vault_topic}"
                    )
            except Exception:
                _log(
                    f"Failed to publish telemetry to vault topic {self.vault_topic}",
                    sys.stderr,
                )

    def publish_sensors(self):
        """Fetch sensors from Home Assistant (if configured) and publish to MQTT.

        Publishes to `telemetry/<client_id>/sensors` as a JSON object:
        { schema_version: 1, client_id, timestamp, sensors: [...] }
        """
        if not self.ha_api_url or not self.ha_api_token:
            # HA integration not configured
            return
        sensors = fetch_sensors(self.ha_api_url, self.ha_api_token)
        payload = {
            "schema_version": 1,
            "client_id": self.client_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sensors": sensors or [],
        }
        # Publish to preferred Vault topic (development-only; legacy dropped)
        try:
            self._publish(self.preferred_sensors_topic, json.dumps(payload), qos=0)
            _log(
                f"Published sensors list to {self.preferred_sensors_topic} (count={len(payload['sensors'])})"
            )
        except Exception:
            _log(
                f"Failed to publish sensors to {self.preferred_sensors_topic}",
                sys.stderr,
            )
        self._last_sensors_sent = int(time.time())

    def _normalize_sensor_value(self, state):
        val = state
        try:
            if isinstance(state, str):
                low = state.lower()
                if low in ("on", "true"):
                    val = True
                elif low in ("off", "false"):
                    val = False
                else:
                    if "." in state:
                        val = float(state)
                    else:
                        val = int(state)
        except Exception:
            val = state
        return val

    def publish_selected_sensor_changes(self):
        """Publish telemetry for selected sensors when their state changes."""
        if not self.selected_sensors:
            return
        if not self.ha_api_url or not self.ha_api_token:
            return
        self._ensure_ha_ws_listener()
        sensors = fetch_sensors(self.ha_api_url, self.ha_api_token) or []
        # If nothing returned from full-state API, try more detailed per-entity fetch.
        if not sensors and self.selected_sensors:
            sensors = (
                fetch_sensors_by_ids(
                    self.ha_api_url, self.ha_api_token, self.selected_sensors
                )
                or []
            )
        selected_set = set(self.selected_sensors)
        filtered = [s for s in sensors if s.get("entity_id") in selected_set]
        data_map, names_map, enabled_map, attrs_map = build_sensor_maps(filtered)

        if not data_map:
            return

        snapshot = {k: data_map[k] for k in data_map.keys()}
        if snapshot == self._selected_sensor_cache:
            return

        self._selected_sensor_cache = snapshot
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        telemetry_payload = {
            "data": data_map,
            "names": names_map,
            "enabled": enabled_map,
            "attributes": attrs_map,
            "timestamp": now_iso,
        }
        try:
            self._publish(
                self.preferred_sensors_topic, json.dumps(telemetry_payload), qos=0
            )
        except Exception:
            _log("Failed to publish selected sensor changes", sys.stderr)

    def _handle_ha_state_event(self, entity_id, new_state):
        """Handle HA websocket state_changed event for selected sensors."""
        try:
            if not entity_id or entity_id not in set(self.selected_sensors or []):
                return
            attrs = new_state.get("attributes", {}) or {}
            attach_ha_timestamps(attrs, new_state)
            telemetry_payload = build_sensor_event_payload(
                entity_id,
                attrs,
                normalize_sensor_value(new_state.get("state")),
            )
            self._publish(
                self.preferred_sensors_topic, telemetry_payload, qos=0
            )
        except Exception:
            traceback.print_exc()

    def _ensure_ha_ws_listener(self):
        """Start HA websocket listener for state changes when possible."""
        if not self.ha_api_url or not self.ha_api_token or not self.selected_sensors:
            return
        try:
            if self._ha_ws_listener is None:
                self._ha_ws_listener = HAWebSocketListener(
                    self.ha_api_url,
                    self.ha_api_token,
                    self._handle_ha_state_event,
                    _log,
                    self.selected_sensors,
                )
            else:
                self._ha_ws_listener.update_selectors(self.selected_sensors)
            self._ha_ws_listener.start()
        except Exception:
            traceback.print_exc()

    def run(self):
        # connect first
        self.connect()
        try:
            while True:
                self.run_iteration()
                time.sleep(self.telemetry_interval)
        finally:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                traceback.print_exc()
            try:
                if self._ha_ws_listener:
                    self._ha_ws_listener.stop()
            except Exception:
                traceback.print_exc()

    def run_iteration(self):
        """Single run loop iteration: reconnect if needed, publish telemetry
        and optionally publish sensors. Called every telemetry_interval seconds.
        """
        if not self._connected:
            try:
                _log("Not connected, attempting reconnect")
            except Exception:
                traceback.print_exc()
            self.connect()
        try:
            self.publish_telemetry()
        except Exception:
            _log("Telemetry publish exception", sys.stderr)
        try:
            self.publish_selected_sensor_changes()
        except Exception:
            _log("Selected sensor change publish exception", sys.stderr)
        # send telemetry every 30s; send sensors every hour
        now = int(time.time())
        try:
            if now - self._last_status_sent >= self.telemetry_interval:
                self.publish_status_online()
        except Exception:
            _log("Status publish exception", sys.stderr)
        try:
            if now - self._last_sensors_sent >= 3600:
                self.publish_sensors()
        except Exception:
            _log("Sensors publish exception", sys.stderr)


def main():
    options = load_options()
    # Sanitize options for logging (hide sensitive data)
    safe_options = {
        k: v
        for k, v in options.items()
        if k
        not in [
            "mqtt_password",
            "mqtt_cert_bundle",
            "mqtt_ca_cert",
            "mqtt_client_cert",
            "mqtt_client_key",
        ]
    }
    # Redact sensitive certificate fields
    sensitive_fields = [
        "mqtt_password",
        "mqtt_cert_bundle",
        "mqtt_ca_cert",
        "mqtt_client_cert",
        "mqtt_client_key",
    ]
    for field in sensitive_fields:
        if field in options and options[field]:
            safe_options[field] = "[REDACTED]"
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
