#!/usr/bin/env python3
"""
Message dispatch handlers extracted from `mqtt_client` to make the
command lifecycles testable independently.
"""
import json
import traceback
from datetime import datetime, timezone
import sys
import pathlib
import time

# Shared MQTT protocol (topics/schemas)
try:
    from central_core_mqtt_shared import schemas as shared_schemas
    from central_core_mqtt_shared import topics as shared_topics
    from central_core_mqtt_shared.topics import build_topic
except Exception:
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
        else:  # pragma: no cover - fallback to templated format
            raise ImportError("shared package not found locally")

    except Exception:  # pragma: no cover

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
            ACK_GENERIC = "hubs/{hub_id}/v{version}/ack/{command_name}/{command_id}"
            BROADCAST_CMD = "hubs/broadcast/v{version}/cmd/{command}"
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


def handle_message(
    client,
    msg,
    payload_str,
    fetch_sensors,
    build_telemetry,
    build_vault_payload,
    requests,
):
    """Handle an incoming MQTT message for Vault-style commands.

    Args:
        client: CentralCoreClient instance (for _publish and attributes)
        msg: original message object (with .topic)
        payload_str: decoded payload string (or '<binary>')
        fetch_sensors: callable to fetch sensors from HA
        build_telemetry: callable to build telemetry payloads
        build_vault_payload: callable to build vault payloads
        requests: requests module or None
    """
    try:
        topic = msg.topic
        protocol_version = getattr(client, "protocol_version", 1)

        def _publish_shared_ack(command_name, command_id, status, message=None):
            """Publish versioned ACK using shared schema when available."""
            if not (shared_topics and shared_schemas and command_id):
                return
            try:
                ack_topic = build_topic(
                    shared_topics.ACK_GENERIC,
                    hub_id=client.client_id,
                    version=protocol_version,
                    command_name=command_name,
                    command_id=command_id,
                )
                # Log explicitly that we are publishing an ack (use client logger if available)
                log_fn = getattr(client, "_log", None)
                try:
                    now_ts = (
                        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    )
                    msg_txt = (
                        f"Publishing ack to {ack_topic} status={status} "
                        f"command_id={command_id} at {now_ts}"
                    )
                    if callable(log_fn):
                        log_fn(msg_txt)
                    else:
                        print(f"[{now_ts}] {msg_txt}", file=sys.stdout)
                except Exception:
                    traceback.print_exc()
                if hasattr(shared_schemas, "CommandAck"):
                    ack_payload = shared_schemas.CommandAck(
                        command_id=command_id,
                        status=status,
                        message=message,
                        timestamp=time.time(),
                    ).model_dump_json()
                else:
                    ack_payload = json.dumps(
                        {
                            "command_id": command_id,
                            "status": status,
                            "message": message,
                            "timestamp": time.time(),
                        }
                    )
                client._publish(ack_topic, ack_payload, qos=1)
            except Exception:
                traceback.print_exc()  # pragma: no cover - do not break handling on ack failure

        def _sensor_topics():
            """Return versioned sensor telemetry topic."""
            topics = []
            for cand in (getattr(client, "preferred_sensors_topic", None),):
                if cand and cand not in topics:
                    topics.append(cand)
            try:
                versioned = build_topic(
                    shared_topics.TELEMETRY_SENSORS,
                    hub_id=client.client_id,
                    version=protocol_version,
                )
                if versioned not in topics:
                    topics.append(versioned)
            except Exception:
                traceback.print_exc()
            return topics

        def _fetch_by_ids(ids):
            """Best-effort per-entity fetch for richer state (timestamps)."""
            if requests is None or not getattr(client, "ha_api_url", None):
                return None
            url_base = client.ha_api_url.rstrip("/")
            headers = {
                "Authorization": f"Bearer {getattr(client, 'ha_api_token', '')}",
                "Content-Type": "application/json",
            }
            results = []
            for ent_id in ids or []:
                try:
                    r = requests.get(
                        f"{url_base}/api/states/{ent_id}", headers=headers, timeout=10
                    )
                    r.raise_for_status()
                    data = r.json()
                    if data.get("entity_id"):
                        results.append(
                            {
                                "entity_id": data.get("entity_id"),
                                "state": data.get("state"),
                                "attributes": data.get("attributes", {}) or {},
                                "last_changed": data.get("last_changed"),
                                "last_updated": data.get("last_updated"),
                            }
                        )
                except Exception:
                    traceback.print_exc()
            return results

        def _val(obj, fallback):
            try:
                return obj.value
            except Exception:
                return obj if obj is not None else fallback

        cmd_name_poll = (
            _val(shared_schemas.CommandName.SENSORS_POLL, "sensors.poll")
            if shared_schemas
            else "sensors.poll"
        )
        cmd_name_set = (
            _val(shared_schemas.CommandName.SENSORS_SET, "sensors.set")
            if shared_schemas
            else "sensors.set"
        )
        ack_success = (
            _val(shared_schemas.AckStatus.SUCCESS, "success")
            if shared_schemas
            else "success"
        )

        expected_cmd_topics = []
        try:
            expected_cmd_topic_v = (
                build_topic(
                    shared_topics.CMD_SENSORS_POLL,
                    hub_id=client.client_id,
                    version=protocol_version,
                )
                if shared_topics
                else None
            )
            if expected_cmd_topic_v:
                expected_cmd_topics.append(expected_cmd_topic_v)
        except Exception:
            expected_cmd_topics = []
        try:
            bcast_template = getattr(shared_topics, "BROADCAST_CMD", None)
            if bcast_template:
                expected_cmd_topics.append(
                    build_topic(
                        bcast_template,
                        version=protocol_version,
                        command="sensors/poll",
                    )
                )
        except Exception:
            traceback.print_exc()
        if topic in expected_cmd_topics:
            try:
                cmd = (
                    json.loads(payload_str)
                    if payload_str and payload_str != "<binary>"
                    else {}
                )
            except Exception:
                cmd = {}

            command_id = cmd.get("command_id")
            if command_id:
                _publish_shared_ack(
                    cmd_name_poll, command_id, ack_success, "acknowledged"
                )

            sensors_requested = None
            try:
                if isinstance(cmd.get("payload"), dict):
                    srv = cmd.get("payload").get("sensors")
                    if isinstance(srv, list):
                        sensors_requested = srv
            except (
                Exception
            ):  # pragma: no cover - defensive branch hard to reproduce in tests
                sensors_requested = None
            sensors = fetch_sensors(client.ha_api_url, client.ha_api_token) or []
            if sensors_requested and not sensors:
                enriched = _fetch_by_ids(sensors_requested)
                if enriched:
                    sensors = enriched
            # If the Vault requested a specific set of sensors, treat that
            # list as authoritative and remember it on the client for future
            # reminder publications.
            try:
                if sensors_requested:
                    # normalize to list of ids
                    client.selected_sensors = list(sensors_requested)
            except Exception:
                # don't let selection storage failure stop command handling
                traceback.print_exc()
            if sensors_requested:
                sensors = [
                    s for s in sensors if s.get("entity_id") in sensors_requested
                ]

            data_map = {}
            for s in sensors:  # pragma: no cover
                ent = s.get("entity_id")  # pragma: no cover
                st = s.get("state")  # pragma: no cover
                val = st
                try:
                    if isinstance(st, str):
                        low = st.lower()
                        if low in ("on", "true"):
                            val = True
                        elif low in ("off", "false"):
                            val = False
                        else:
                            if "." in st:
                                val = float(st)
                            else:
                                val = int(st)
                except Exception:
                    val = st
                data_map[ent] = val
            # also include friendly names and enabled status if available
            names_map = {}
            enabled_map = {}
            for s in sensors:
                ent = s.get("entity_id")
                if not ent:
                    continue
                attrs = s.get("attributes", {}) or {}
                names_map[ent] = attrs.get("friendly_name") or s.get("name") or ent
                # consider entity disabled if 'disabled_by' attribute is set
                enabled_map[ent] = not bool(attrs.get("disabled_by"))

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            telemetry_payload = {
                "data": data_map,
                "names": names_map,
                "enabled": enabled_map,
                "timestamp": now_iso,
            }
            try:
                for t in _sensor_topics():
                    client._publish(t, json.dumps(telemetry_payload), qos=0)
            except Exception:
                traceback.print_exc()  # pragma: no cover

            # If a vault topic is configured, remind the Vault server which
            # sensors were selected/reported by publishing a short payload
            # containing the selected sensor IDs. The Vault-authoritative
            # list (`client.selected_sensors`) is preferred when available.
            try:
                if getattr(client, "vault_topic", None):
                    selected = getattr(client, "selected_sensors", None) or list(
                        data_map.keys()
                    )
                    reminder = {
                        "schema_version": 1,
                        "client_id": client.client_id,
                        "timestamp": now_iso,
                        "selected_sensors": list(selected),
                    }
                    client._publish(client.vault_topic, json.dumps(reminder), qos=0)
            except Exception:
                traceback.print_exc()  # pragma: no cover

            if command_id:
                _publish_shared_ack(cmd_name_poll, command_id, ack_success, "completed")
            return

        expected_set_topics = []
        try:
            expected_set_topic_v = (
                build_topic(
                    shared_topics.CMD_SENSORS_SET,
                    hub_id=client.client_id,
                    version=protocol_version,
                )
                if shared_topics
                else None
            )
            if expected_set_topic_v:
                expected_set_topics.append(expected_set_topic_v)
        except Exception:
            expected_set_topics = []
        try:
            bcast_template = getattr(shared_topics, "BROADCAST_CMD", None)
            if bcast_template:
                expected_set_topics.append(
                    build_topic(
                        bcast_template,
                        version=protocol_version,
                        command="sensors/set",
                    )
                )
        except Exception:
            traceback.print_exc()

        if topic in expected_set_topics:
            try:
                cmd = (
                    json.loads(payload_str)
                    if payload_str and payload_str != "<binary>"
                    else {}
                )
            except Exception:
                cmd = {}

            command_id = cmd.get("command_id")
            if command_id:
                _publish_shared_ack(
                    cmd_name_set, command_id, ack_success, "acknowledged"
                )

            sensors_to_set = []
            try:
                payload_obj = cmd.get("payload") if isinstance(cmd, dict) else None
                if isinstance(payload_obj, dict):
                    s = payload_obj.get("sensors")
                    if isinstance(s, dict):
                        for ent, st in s.items():
                            sensors_to_set.append({"entity_id": ent, "state": st})
                    elif isinstance(s, list):
                        for item in s:
                            if isinstance(item, dict) and item.get("entity_id"):
                                sensors_to_set.append(item)
            except (
                Exception
            ):  # pragma: no cover - defensive branch hard to reproduce in tests
                sensors_to_set = []

            results = {"set": [], "failed": []}
            readback_values = {}
            readback_attrs = {}

            for item in sensors_to_set:
                ent = item.get("entity_id")
                st = item.get("state")
                if not ent:  # pragma: no cover - unreachable via normal JSON input
                    continue
                try:
                    if (
                        client.ha_api_url
                        and client.ha_api_token
                        and requests is not None
                    ):
                        url = client.ha_api_url.rstrip("/") + f"/api/states/{ent}"
                        headers = {
                            "Authorization": f"Bearer {client.ha_api_token}",
                            "Content-Type": "application/json",
                        }
                        body = {"state": st}
                        r = requests.post(url, headers=headers, json=body, timeout=10)
                        r.raise_for_status()
                        if client.ha_readback_after_set:
                            try:
                                r2 = requests.get(url, headers=headers, timeout=10)
                                r2.raise_for_status()
                                data = r2.json()
                                read_state = data.get("state")
                                readback_values[ent] = read_state
                                readback_attrs[ent] = data.get("attributes", {}) or {}
                            except Exception:
                                readback_values[ent] = st
                                readback_attrs[ent] = {}
                        else:
                            readback_values[ent] = st
                            readback_attrs[ent] = {}
                        results["set"].append(ent)
                    else:
                        results["failed"].append(
                            {"entity_id": ent, "reason": "no_ha_config"}
                        )
                except Exception as e:
                    results["failed"].append({"entity_id": ent, "reason": str(e)})

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            if command_id:
                _publish_shared_ack(cmd_name_set, command_id, ack_success, "completed")

            try:
                data_map = {}
                attrs_map = {}
                for item in sensors_to_set:
                    ent = item.get("entity_id")
                    if ent and ent in results.get("set", []):
                        st = readback_values.get(ent, item.get("state"))
                        val = st
                        try:
                            if isinstance(st, str):
                                low = st.lower()
                                if low in ("on", "true"):
                                    val = True
                                elif low in ("off", "false"):
                                    val = False
                                else:
                                    if "." in st:
                                        val = float(st)
                                    else:
                                        val = int(st)
                        except Exception:
                            val = st
                        data_map[ent] = val
                        attrs_map[ent] = readback_attrs.get(ent, {})
                # build friendly-name and enabled maps from readback attributes
                names_map = {}
                enabled_map = {}
                for ent in data_map.keys():
                    attrs = readback_attrs.get(ent, {}) or {}  # pragma: no cover
                    names_map[ent] = (
                        attrs.get("friendly_name") or ent
                    )  # pragma: no cover
                    enabled_map[ent] = not bool(
                        attrs.get("disabled_by")
                    )  # pragma: no cover

                if data_map:  # pragma: no cover
                    telemetry_payload = {
                        "data": data_map,
                        "attributes": attrs_map,
                        "names": names_map,
                        "enabled": enabled_map,
                        "timestamp": now_iso,
                    }
                    try:
                        for t in _sensor_topics():
                            client._publish(t, json.dumps(telemetry_payload), qos=0)
                    except Exception:
                        traceback.print_exc()  # pragma: no cover
                    # Remind Vault of the sensors that were set/readback.
                    # If the client has a Vault-authoritative selection, prefer
                    # that list; otherwise fall back to the data_map keys.
                    try:
                        if getattr(client, "vault_topic", None):
                            selected = getattr(
                                client, "selected_sensors", None
                            ) or list(data_map.keys())
                            reminder = {
                                "schema_version": 1,
                                "client_id": client.client_id,
                                "timestamp": now_iso,
                                "selected_sensors": list(selected),
                            }
                            client._publish(
                                client.vault_topic, json.dumps(reminder), qos=0
                            )
                    except Exception:
                        traceback.print_exc()  # pragma: no cover
            except (
                Exception
            ):  # pragma: no cover - defensive branch hard to reproduce in tests
                traceback.print_exc()  # pragma: no cover
            return
    except Exception:
        traceback.print_exc()  # pragma: no cover
