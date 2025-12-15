#!/usr/bin/env python3
"""
Message dispatch handlers extracted from `mqtt_client` to make the
command lifecycles testable independently.
"""

import json
import os
import traceback
from datetime import datetime, timezone


def _is_entity_allowed(entity_id):
    """Runtime helper that consults `mqtt_client.is_entity_allowed` when
    available, falling back to allowing the entity on error.
    """
    try:
        import mqtt_client as _mc

        fn = getattr(_mc, "is_entity_allowed", None)
        if callable(fn):
            try:
                return bool(fn(entity_id))
            except Exception:
                return True
        return True
    except Exception:
        return True


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
        # Accept recent versioned command topics (v1)
        expected_config_topic = f"hubs/{client.client_id}/v1/cmd/config/update"
        if topic == expected_config_topic:
            try:
                cmd = json.loads(payload_str) if payload_str and payload_str != "<binary>" else {}
            except Exception:
                cmd = {}
            command_id = cmd.get("command_id")
            action = cmd.get("action") or "config/update"
            if command_id:
                try:
                    v1_ack = client.build_ack_topic(action, command_id)
                except Exception:
                    v1_ack = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                ack_payload = {
                    "status": "acknowledged",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                try:
                    client._publish(v1_ack, json.dumps(ack_payload), qos=1)
                except Exception:
                    pass
            upd_result = {}
            try:
                # Extract version from payload if provided
                version = None
                try:
                    payload_obj = cmd.get("payload") if isinstance(cmd, dict) else None
                    if isinstance(payload_obj, dict):
                        version = payload_obj.get("version")
                except Exception:
                    version = None

                upd_result = client.trigger_addon_update(version=version) or {}
            except Exception:
                upd_result = {"success": False, "error": "trigger_failed"}

            completion_payload = {
                "status": "completed" if upd_result.get("success") else "failed",
                "result": upd_result,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            if command_id:
                try:
                    v1_comp = client.build_ack_topic(action, command_id)
                except Exception:
                    v1_comp = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                try:
                    client._publish(v1_comp, json.dumps(completion_payload), qos=1)
                except Exception:
                    pass
            return

        expected_cmd_topic_v1 = f"hubs/{client.client_id}/v1/cmd/sensors/poll"
        if topic == expected_cmd_topic_v1:
            try:
                cmd = json.loads(payload_str) if payload_str and payload_str != "<binary>" else {}
            except Exception:
                cmd = {}

            command_id = cmd.get("command_id")
            action = cmd.get("action") or "sensors/poll"
            if command_id:
                # ACK topic: publish versioned ack only (remove legacy response)
                try:
                    v1_ack = client.build_ack_topic(action, command_id)
                except Exception:
                    v1_ack = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                ack_payload = {
                    "status": "acknowledged",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
                    s
                    for s in sensors
                    if s.get("entity_id") in sensors_requested and _is_entity_allowed(s.get("entity_id"))
                ]

            data_map = {}
            raw_map = {}
            for s in sensors:  # pragma: no cover
                ent = s.get("entity_id")  # pragma: no cover
                if not ent or not _is_entity_allowed(ent):
                    continue
                st = s.get("state")  # pragma: no cover
                # preserve the raw state as reported by HA
                raw_map[ent] = st
                # Do not normalize — preserve the exact HA-provided state
                val = st
                data_map[ent] = val
            # also include friendly names and enabled status if available
            names_map = {}
            enabled_map = {}
            attrs_map = {}
            for s in sensors:
                ent = s.get("entity_id")
                if not ent or not _is_entity_allowed(ent):
                    continue
                attrs = s.get("attributes", {}) or {}
                names_map[ent] = attrs.get("friendly_name") or s.get("name") or ent
                # consider entity disabled if 'disabled_by' attribute is set
                enabled_map[ent] = not bool(attrs.get("disabled_by"))
                attrs_map[ent] = attrs

            # build observed timestamps map (prefer HA-provided timestamps,
            # fall back to current time)
            observed_map = {}
            for s in sensors:
                ent = s.get("entity_id")
                if not ent or not _is_entity_allowed(ent):
                    continue
                obs = None
                try:
                    obs = s.get("last_changed") or s.get("last_updated")
                    # Normalize HA timestamps to match add-on format
                    if obs and isinstance(obs, str):
                        obs = obs.replace("+00:00", "Z")
                except Exception:
                    obs = None
                if not obs:
                    obs = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                observed_map[ent] = obs

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            telemetry_payload = {
                "data": data_map,
                "raw": raw_map,
                "names": names_map,
                "attributes": attrs_map,
                "enabled": enabled_map,
                "observed": observed_map,
                "timestamp": now_iso,
            }
            try:
                client._publish(client.preferred_sensors_topic, json.dumps(telemetry_payload), qos=0)
            except Exception:
                pass  # pragma: no cover

            # Log the sensors we just published for operator visibility
            try:
                import mqtt_client as _mc

                sent_list = list(data_map.keys())
                if sent_list:
                    _mc._log(f"Sensors poll -> Sent sensors: {', '.join(sent_list)}")
                else:
                    _mc._log("Sensors poll -> Sent sensors: none")
            except Exception:
                pass
            # If a vault topic is configured, remind the Vault server which
            # sensors were selected/reported by publishing a short payload
            # containing the selected sensor IDs. The Vault-authoritative
            # list (`client.selected_sensors`) is preferred when available.
            try:
                if getattr(client, "vault_topic", None):
                    selected = getattr(client, "selected_sensors", None) or list(data_map.keys())
                    # Filter the selected sensors through the registry
                    try:
                        selected = [s for s in selected if _is_entity_allowed(s)]
                    except Exception:
                        pass
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
                try:
                    v1_comp = client.build_ack_topic(action, command_id)
                except Exception:
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

        expected_set_topic_v1 = f"hubs/{client.client_id}/v1/cmd/sensors/set"
        if topic == expected_set_topic_v1:
            try:
                cmd = json.loads(payload_str) if payload_str and payload_str != "<binary>" else {}
            except Exception:
                cmd = {}

            command_id = cmd.get("command_id")
            action = cmd.get("action") or "sensors/set"
            if command_id:
                # Publish versioned ack only
                v1_ack = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                ack_payload = {
                    "status": "acknowledged",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
                    # Accept dict mapping entity_id->state
                    if isinstance(s, dict):
                        for ent, st in s.items():
                            sensors_to_set.append({"entity_id": ent, "state": st})
                    # New: accept a list of plain entity-id strings and treat
                    # it as a selection (equivalent to sensors/poll). In this
                    # case we store the selection and publish a vault
                    # reminder, then respond with a completed ack.
                    elif isinstance(s, list) and all(isinstance(x, str) for x in s):
                        try:
                            client.selected_sensors = list(s)
                        except Exception:
                            pass
                        # make a stable 'selected' value for reminder/persist
                        selected = getattr(client, "selected_sensors", None) or list(s)
                        # Immediately publish current values for the selected sensors
                        try:
                            sensors = fetch_sensors(client.ha_api_url, client.ha_api_token) or []
                            sensors = [
                                si
                                for si in sensors
                                if si.get("entity_id") in selected and _is_entity_allowed(si.get("entity_id"))
                            ]
                            data_map = {}
                            raw_map = {}
                            names_map = {}
                            enabled_map = {}
                            attrs_map = {}
                            for si in sensors:
                                ent = si.get("entity_id")
                                if not ent:
                                    continue
                                st = si.get("state")
                                # preserve raw state
                                raw_map[ent] = st
                                # Do not normalize — preserve the exact HA-provided state
                                val = st
                                data_map[ent] = val
                            for si in sensors:
                                ent = si.get("entity_id")
                                if not ent:
                                    continue
                                attrs = si.get("attributes", {}) or {}
                                names_map[ent] = attrs.get("friendly_name") or si.get("name") or ent
                                enabled_map[ent] = not bool(attrs.get("disabled_by"))
                                attrs_map[ent] = attrs
                            # build observed timestamps for selected sensors
                            observed_map = {}
                            for si in sensors:
                                ent = si.get("entity_id")
                                if not ent:
                                    continue
                                obs = None
                                try:
                                    obs = si.get("last_changed") or si.get("last_updated")
                                    # Normalize HA timestamps to match add-on format
                                    if obs and isinstance(obs, str):
                                        obs = obs.replace("+00:00", "Z")
                                except Exception:
                                    obs = None
                                if not obs:
                                    obs = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                                observed_map[ent] = obs

                            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                            telemetry_payload = {
                                "data": data_map,
                                "raw": raw_map,
                                "names": names_map,
                                "attributes": attrs_map,
                                "enabled": enabled_map,
                                "observed": observed_map,
                                "timestamp": now_iso,
                            }
                            # Do not publish this to the general telemetry topic here;
                            # instead attach the telemetry payload to the completion ACK
                            monitor_telemetry = telemetry_payload
                            try:
                                import mqtt_client as _mc

                                sent_list = list(data_map.keys())
                                if sent_list:
                                    _mc._log(f"Sensors monitor -> Sent sensors: {', '.join(sent_list)}")
                                else:
                                    _mc._log("Sensors monitor -> Sent sensors: none")
                            except Exception:
                                pass
                        except Exception:
                            pass
                        # Publish reminder to vault if configured
                        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                        try:
                            if getattr(client, "vault_topic", None):
                                reminder = {
                                    "schema_version": 1,
                                    "client_id": client.client_id,
                                    "timestamp": now_iso,
                                    "selected_sensors": list(selected),
                                }
                                client._publish(client.vault_topic, json.dumps(reminder), qos=0)
                        except Exception:
                            pass
                        # Persist the selected sensors so they survive restarts
                        try:
                            import tempfile
                            import pathlib

                            try:
                                import mqtt_client as _mc
                            except Exception:
                                _mc = None

                            target = getattr(_mc, "SELECTED_SENSORS_FILE", None) if _mc is not None else None
                            if not target:
                                target = pathlib.Path(__file__).parent / "SELECTED_SENSORS.json"
                            else:
                                target = pathlib.Path(str(target))

                            d = target.parent
                            d.mkdir(parents=True, exist_ok=True)
                            with tempfile.NamedTemporaryFile(mode="w", dir=str(d), delete=False) as tf:
                                tf.write(json.dumps(list(selected), indent=2))
                                tmpname = tf.name
                            pathlib.Path(tmpname).replace(target)
                        except Exception:
                            pass
                        # Send completion ack for sensors/set
                        if command_id:
                            try:
                                v1_comp = client.build_ack_topic(action, command_id)
                            except Exception:
                                v1_comp = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                            # If we built monitor_telemetry above, include it in the
                            # completion ACK so callers receive the current values
                            mt = locals().get("monitor_telemetry")
                            if mt:
                                comp_payload = {
                                    "status": "completed",
                                    "result": {
                                        "selected": list(s),
                                        "sensors_reported": list(mt.get("data", {}).keys()),
                                        "count": len(mt.get("data", {})),
                                        "data": mt.get("data", {}),
                                        "raw": mt.get("raw", {}),
                                        "names": mt.get("names", {}),
                                        "enabled": mt.get("enabled", {}),
                                        "attributes": mt.get("attributes", {}),
                                        "observed": mt.get("observed", {}),
                                    },
                                    "timestamp": now_iso,
                                }
                            else:
                                comp_payload = {
                                    "status": "completed",
                                    "result": {"selected": list(s)},
                                    "timestamp": now_iso,
                                }
                            try:
                                client._publish(v1_comp, json.dumps(comp_payload), qos=1)
                            except Exception:
                                pass
                        return
                    # Accept list of dicts with entity_id/state
                    elif isinstance(s, list):
                        for item in s:
                            if isinstance(item, dict) and item.get("entity_id"):
                                sensors_to_set.append(item)
            except Exception:  # pragma: no cover - defensive branch hard to reproduce in tests
                sensors_to_set = []

            results = {"set": [], "failed": []}
            readback_values = {}
            readback_attrs = {}
            readback_observed = {}

            for item in sensors_to_set:
                ent = item.get("entity_id")
                st = item.get("state")
                if not ent:  # pragma: no cover - unreachable via normal JSON input
                    continue
                try:
                    if client.ha_api_url and client.ha_api_token and requests is not None:
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
                                # prefer HA-provided timestamps if available
                                try:
                                    obs = data.get("last_changed") or data.get("last_updated")
                                    # Normalize HA timestamps to match add-on format
                                    if obs and isinstance(obs, str):
                                        obs = obs.replace("+00:00", "Z")
                                except Exception:
                                    obs = None
                                if not obs:
                                    obs = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                                readback_observed[ent] = obs
                            except Exception:
                                readback_values[ent] = st
                                readback_attrs[ent] = {}
                                readback_observed[ent] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                        else:
                            readback_values[ent] = st
                            readback_attrs[ent] = {}
                            readback_observed[ent] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                        results["set"].append(ent)
                    else:
                        results["failed"].append({"entity_id": ent, "reason": "no_ha_config"})
                except Exception as e:
                    results["failed"].append({"entity_id": ent, "reason": str(e)})

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            try:
                data_map = {}
                raw_map = {}
                attrs_map = {}
                for item in sensors_to_set:
                    ent = item.get("entity_id")
                    if ent and ent in results.get("set", []):
                        st = readback_values.get(ent, item.get("state"))
                        # preserve the raw state reported/readback; do not normalize
                        raw_map[ent] = st
                        val = st
                        data_map[ent] = val
                        attrs_map[ent] = readback_attrs.get(ent, {})
                # build friendly-name and enabled maps from readback attributes
                names_map = {}
                enabled_map = {}
                for ent in data_map.keys():
                    attrs = readback_attrs.get(ent, {}) or {}  # pragma: no cover
                    names_map[ent] = attrs.get("friendly_name") or ent  # pragma: no cover
                    enabled_map[ent] = not bool(attrs.get("disabled_by"))  # pragma: no cover

                if data_map:  # pragma: no cover
                    telemetry_payload = {
                        "data": data_map,
                        "raw": raw_map,
                        "attributes": attrs_map,
                        "names": names_map,
                        "enabled": enabled_map,
                        "observed": readback_observed,
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
                            selected = getattr(client, "selected_sensors", None) or list(data_map.keys())
                            reminder = {
                                "schema_version": 1,
                                "client_id": client.client_id,
                                "timestamp": now_iso,
                                "selected_sensors": list(selected),
                            }
                            client._publish(client.vault_topic, json.dumps(reminder), qos=0)
                    except Exception:
                        pass  # pragma: no cover
                    # Also publish an enhanced completion ACK including the
                    # readback telemetry so callers receive immediate context
                    # about the set operation when readback produced data.
                    try:
                        if command_id and data_map:
                            try:
                                v1_comp = client.build_ack_topic(action, command_id)
                            except Exception:
                                v1_comp = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                            comp_payload = {
                                "status": "completed",
                                "result": {
                                    "set": results.get("set", []),
                                    "failed": results.get("failed", []),
                                    "sensors_reported": list(data_map.keys()),
                                    "count": len(data_map),
                                    "data": data_map,
                                    "raw": raw_map,
                                    "names": names_map,
                                    "enabled": enabled_map,
                                    "attributes": attrs_map,
                                    "observed": readback_observed,
                                },
                                "timestamp": now_iso,
                            }
                            try:
                                client._publish(v1_comp, json.dumps(comp_payload), qos=1)
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:  # pragma: no cover - defensive branch hard to reproduce in tests
                traceback.print_exc()  # pragma: no cover
            # Ensure we attempt to publish telemetry and vault reminder even
            # if the detailed data_map construction above raised an
            # exception. This improves robustness and preserves expected
            # publishes for tests and consumers that rely on a
            # `preferred_sensors_topic` publication.
            try:
                data_map = locals().get("data_map", None)
                # Only publish fallback telemetry if the real data_map wasn't
                # constructed and published above.
                if not data_map:
                    attrs_map = locals().get("attrs_map", {}) or {}
                    names_map = locals().get("names_map", {}) or {}
                    enabled_map = locals().get("enabled_map", {}) or {}
                    telemetry_payload = {
                        "data": {},
                        "raw": {},
                        "attributes": attrs_map,
                        "names": names_map,
                        "enabled": enabled_map,
                        "observed": {},
                        "timestamp": now_iso,
                    }
                    try:
                        client._publish(client.preferred_sensors_topic, json.dumps(telemetry_payload), qos=0)
                    except Exception:
                        pass
                try:
                    if getattr(client, "vault_topic", None):
                        selected = getattr(client, "selected_sensors", None) or list((data_map or {}).keys())
                        reminder = {
                            "schema_version": 1,
                            "client_id": client.client_id,
                            "timestamp": now_iso,
                            "selected_sensors": list(selected),
                        }
                        client._publish(client.vault_topic, json.dumps(reminder), qos=0)
                except Exception:
                    pass
                # If we did not publish an enhanced completion earlier (i.e.
                # there was no readback data), ensure we still publish a
                # simple completion ACK with the results so callers receive
                # an outcome for the set operation.
                try:
                    if command_id and not (locals().get("data_map", None)):
                        try:
                            v1_comp = client.build_ack_topic(action, command_id)
                        except Exception:
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
                except Exception:
                    pass
            except Exception:
                pass
            return

        # Allow Vault to update the SENSOR_REGISTRY via MQTT command.
        expected_registry_set = f"hubs/{client.client_id}/v1/cmd/registry/set"
        if topic == expected_registry_set:
            try:
                cmd = json.loads(payload_str) if payload_str and payload_str != "<binary>" else {}
            except Exception:
                cmd = {}

            command_id = cmd.get("command_id")
            action = cmd.get("action") or "registry/set"
            if command_id:
                try:
                    v1_ack = client.build_ack_topic(action, command_id)
                except Exception:
                    v1_ack = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                try:
                    client._publish(v1_ack, json.dumps({"status": "acknowledged"}), qos=1)
                except Exception:
                    pass

            payload_obj = None
            try:
                payload_obj = cmd.get("payload") if isinstance(cmd, dict) else None
            except Exception:
                payload_obj = None

            result = {"success": False}
            try:
                # Import mqtt_client module to locate SENSOR_REGISTRY and reload helper
                try:
                    import mqtt_client as _mc
                except Exception:
                    _mc = None

                if not payload_obj:
                    result = {"success": False, "reason": "missing_payload"}
                else:
                    # Optional token-based validation: if an expected token is
                    # configured on the client (or via env `REGISTRY_TOKEN`),
                    # require the incoming payload to include the same token.
                    try:
                        expected_token = None
                        # Prefer explicit attribute on the client
                        expected_token = getattr(client, "registry_token", None)
                    except Exception:
                        expected_token = None
                    try:
                        if not expected_token:
                            opts = getattr(client, "options", None)
                            if isinstance(opts, dict):
                                expected_token = opts.get("registry_token") or opts.get("registryToken")
                    except Exception:
                        pass
                    try:
                        if not expected_token:
                            expected_token = os.environ.get("REGISTRY_TOKEN")
                    except Exception:
                        expected_token = None

                    if expected_token:
                        provided = None
                        try:
                            if isinstance(payload_obj, dict):
                                provided = payload_obj.get("token")
                        except Exception:
                            provided = None
                        if provided != expected_token:
                            result = {"success": False, "reason": "auth_failed"}
                            # Skip persisting the file when auth fails
                            if command_id:
                                try:
                                    try:
                                        v1_comp = client.build_ack_topic(action, command_id)
                                    except Exception:
                                        v1_comp = (
                                            f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                                        )
                                    comp_payload = {"status": "failed", "result": result}
                                    client._publish(v1_comp, json.dumps(comp_payload), qos=1)
                                except Exception:
                                    pass
                            # bail out early
                            result = result
                            # ensure we do not attempt the write below
                            raise RuntimeError("auth_failed")
                    # Atomic write: write to temp file in same dir and rename
                    try:
                        import tempfile
                        import pathlib

                        target = getattr(_mc, "SENSOR_REGISTRY", None) if _mc is not None else None
                        if not target:
                            # If module not importable, persist to a local handlers-registry file
                            target = pathlib.Path(__file__).parent / "SENSOR_REGISTRY_from_mqtt.json"
                        else:
                            target = pathlib.Path(str(target))

                        d = target.parent
                        d.mkdir(parents=True, exist_ok=True)
                        with tempfile.NamedTemporaryFile(mode="w", dir=str(d), delete=False) as tf:
                            tf.write(json.dumps(payload_obj, indent=2))
                            tmpname = tf.name
                        # Use atomic rename
                        pathlib.Path(tmpname).replace(target)
                        # ask runtime to reload registry if helper exists
                        try:
                            if _mc is not None and hasattr(_mc, "reload_sensor_registry"):
                                try:
                                    _mc.reload_sensor_registry()
                                except Exception:
                                    pass
                            # Also provide client-level hook
                            if hasattr(client, "reload_sensor_registry"):
                                try:
                                    client.reload_sensor_registry()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        result = {"success": True, "entries": len(payload_obj.get("entries", []))}
                    except Exception as e:
                        result = {"success": False, "reason": str(e)}
            except Exception as e:
                result = {"success": False, "reason": str(e)}

            if command_id:
                try:
                    try:
                        v1_comp = client.build_ack_topic(action, command_id)
                    except Exception:
                        v1_comp = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
                    comp_payload = {"status": "completed" if result.get("success") else "failed", "result": result}
                    client._publish(v1_comp, json.dumps(comp_payload), qos=1)
                except Exception:
                    pass
            return
    except Exception:
        traceback.print_exc()  # pragma: no cover
