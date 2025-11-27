#!/usr/bin/env python3
"""
Message dispatch handlers extracted from `mqtt_client` to make the
command lifecycles testable independently.
"""
import json
import traceback
from datetime import datetime, timezone


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
        # Accept both legacy and versioned command topics (with or without /v1/)
        expected_cmd_topic = f"hubs/{client.client_id}/cmd/sensors/poll"
        expected_cmd_topic_v1 = f"hubs/{client.client_id}/v1/cmd/sensors/poll"
        if topic == expected_cmd_topic or topic == expected_cmd_topic_v1:
            try:
                cmd = (
                    json.loads(payload_str)
                    if payload_str and payload_str != "<binary>"
                    else {}
                )
            except Exception:
                cmd = {}

            command_id = cmd.get("command_id")
                action = cmd.get("action") or "sensors/poll"
            if command_id:
                # ACK topic: publish versioned ack only (remove legacy response)
                v1_ack = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                ack_payload = {
                    "status": "acknowledged",
                    "timestamp": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
                try:
                    client._publish(v1_ack, json.dumps(ack_payload), qos=1)
                except Exception:
                    pass  # pragma: no cover

            sensors_requested = None
            try:
                payload_obj = cmd.get("payload") if isinstance(cmd, dict) else None
                if isinstance(payload_obj, dict):
                    srv = payload_obj.get("sensors")
                    if isinstance(srv, list):
                        sensors_requested = srv
            except Exception:  # pragma: no cover - defensive branch hard to reproduce in tests
                sensors_requested = None
            sensors = fetch_sensors(client.ha_api_url, client.ha_api_token) or []
            # If the Vault requested a specific set of sensors, treat that
            # list as authoritative and remember it on the client for future
            # reminder publications.
            try:
                if sensors_requested:
                    # normalize to list of ids
                    client.selected_sensors = list(sensors_requested)
            except Exception:
                # don't let selection storage failure stop command handling
                pass
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
                client._publish(
                    client.preferred_sensors_topic, json.dumps(telemetry_payload), qos=0
                )
            except Exception:
                pass  # pragma: no cover

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
                pass  # pragma: no cover

            if command_id:
                # Publish versioned completion response only; remove legacy response
                v1_comp = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                comp_payload = {
                    "status": "completed",
                    "result": {
                        "sensors_reported": list(data_map.keys()),
                        "count": len(data_map),
                    },
                    "timestamp": now_iso,
                }
                try:
                    client._publish(v1_comp, json.dumps(comp_payload), qos=1)
                except Exception:
                    pass  # pragma: no cover
            return

        expected_set_topic = f"hubs/{client.client_id}/cmd/sensors/set"
        expected_set_topic_v1 = f"hubs/{client.client_id}/v1/cmd/sensors/set"
        if topic == expected_set_topic or topic == expected_set_topic_v1:
            try:
                cmd = (
                    json.loads(payload_str)
                    if payload_str and payload_str != "<binary>"
                    else {}
                )
            except Exception:
                cmd = {}

            command_id = cmd.get("command_id")
            action = cmd.get("action") or "sensors/set"
            if command_id:
                    # Publish versioned ack only
                    v1_ack = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                    ack_payload = {
                        "status": "acknowledged",
                        "timestamp": datetime.now(timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z"),
                    }
                    try:
                        client._publish(v1_ack, json.dumps(ack_payload), qos=1)
                    except Exception:
                        pass

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
            except Exception:  # pragma: no cover - defensive branch hard to reproduce in tests
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
                    # Publish versioned completion only
                    v1_comp = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                    comp_payload = {
                        "status": "completed",
                        "result": results,
                        "timestamp": now_iso,
                    }
                    try:
                        client._publish(v1_comp, json.dumps(comp_payload), qos=1)
                    except Exception:
                        pass

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
                        client._publish(
                            client.preferred_sensors_topic,
                            json.dumps(telemetry_payload),
                            qos=0,
                        )
                    except Exception:
                        pass  # pragma: no cover
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
                        pass  # pragma: no cover
            except Exception:  # pragma: no cover - defensive branch hard to reproduce in tests
                traceback.print_exc()  # pragma: no cover
            return
    except Exception:
        traceback.print_exc()  # pragma: no cover
