#!/usr/bin/env python3
"""
Message dispatch handlers extracted from `mqtt_client` to make the
command lifecycles testable independently.
"""

import json
import threading
import os
import traceback
from datetime import datetime, timezone

_LOCAL_TZ = datetime.now().astimezone().tzinfo


def _normalize_ts(ts_str):
    """Normalize a HA timestamp to hub's local timezone ISO format.

    Returns ts_str unchanged if it is not a parseable string.
    """
    if not ts_str or not isinstance(ts_str, str):
        return ts_str
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_LOCAL_TZ)
        else:
            dt = dt.astimezone(_LOCAL_TZ)
        return dt.isoformat()
    except ValueError:
        return ts_str


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


# One update or check at a time, off paho's network thread: an update can take
# minutes, and while that thread is busy the hub sends nothing (no keepalives,
# no sensor changes, not even this command's own replies).
_update_lock = threading.Lock()
_update_thread = None


def wait_for_update_worker(timeout=None):
    """Wait for the running update/check to finish (used by tests and shutdown)."""
    t = _update_thread
    if t is not None:
        t.join(timeout)


def _run_update_command(client, action, command_id, run):
    """Run an updater call and publish its result as the command's completion ACK.

    `run(send_started)` returns the result dict. For an update, the updater
    calls `send_started` before installing, because the add-on restarts during
    the install and could not send anything afterwards.
    """
    sent = {"done": False}

    def publish(result):
        if not command_id or sent["done"]:
            return
        payload = {
            "status": "failed" if result.get("outcome") == "failed" else "completed",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        try:
            topic = client.build_ack_topic(action, command_id)
        except Exception:
            topic = f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"
        try:
            info = client._publish(topic, json.dumps(payload), qos=1)
            sent["done"] = True
        except Exception:
            return
        # Home Assistant stops the add-on for its own install; make sure the
        # reply has actually left before that happens.
        wait = getattr(info, "wait_for_publish", None)
        if callable(wait):
            try:
                wait(timeout=5)
            except Exception:
                pass

    updater = None
    try:
        updater = client.addon_updater()
    except Exception:
        updater = None
    if updater is None:
        publish({"outcome": "failed", "installed": None, "latest": None, "auto_update": None,
                 "reason": "ha_unreachable"})
        return
    if not _update_lock.acquire(blocking=False):
        publish({"outcome": "failed", "installed": None, "latest": None, "auto_update": None,
                 "reason": "update_already_running"})
        return

    def work():
        try:
            try:
                result = run(updater, publish)
            except Exception as exc:
                result = {"outcome": "failed", "installed": None, "latest": None, "auto_update": None,
                          "reason": str(exc)}
            publish(result)
        finally:
            _update_lock.release()

    global _update_thread
    _update_thread = threading.Thread(target=work, name="addon-update", daemon=True)
    _update_thread.start()


def _sanitize(attrs):
    import ha_client

    return ha_client.sanitize_attributes(attrs)


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ack_topic(client, action, command_id):
    try:
        return client.build_ack_topic(action, command_id)
    except Exception:
        return f"hubs/{client.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"


def _send_ack(client, action, command_id, payload):
    if not command_id:
        return
    try:
        client._publish(_ack_topic(client, action, command_id), json.dumps(payload), qos=1)
    except Exception:
        pass


def _persist_selection(selected):
    """Write the selection so it survives restarts (atomic replace)."""
    import pathlib
    import tempfile

    try:
        import mqtt_client as _mc
    except Exception:
        _mc = None
    target = getattr(_mc, "SELECTED_SENSORS_FILE", None) if _mc is not None else None
    target = pathlib.Path(str(target)) if target else pathlib.Path(__file__).parent / "SELECTED_SENSORS.json"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=str(target.parent), delete=False) as tf:
            tf.write(json.dumps(list(selected), indent=2))
            tmpname = tf.name
        pathlib.Path(tmpname).replace(target)
    except Exception:
        pass


def _states_report(states):
    """The per-entity maps the vault stores with a sensors/set completion."""
    report = {
        "data": {},
        "raw": {},
        "names": {},
        "enabled": {},
        "attributes": {},
        "observed": {},
        "device_classes": {},
    }
    for s in states:
        ent = s.get("entity_id")
        if not ent:
            continue
        attrs = _sanitize(s.get("attributes"))
        report["data"][ent] = s.get("state")
        report["raw"][ent] = s.get("state")
        report["names"][ent] = attrs.get("friendly_name") or s.get("name") or ent
        report["enabled"][ent] = not bool(attrs.get("disabled_by"))
        report["attributes"][ent] = attrs
        obs = s.get("last_changed") or s.get("last_updated")
        report["observed"][ent] = _normalize_ts(obs) or datetime.now().astimezone().isoformat()
        if attrs.get("device_class"):
            report["device_classes"][ent] = attrs.get("device_class")
    return report


def _handle_sensors_set(client, cmd, fetch_sensors):
    """sensors/set: replace the list of entities the hub watches.

    The only accepted form is `{"sensors": ["sensor.a", ...]}` (what the vault
    sends). The hub never writes state to Home Assistant: any other shape is
    refused, and every id must be a well-formed entity id before it is kept.
    """
    import ha_client

    action = "sensors/set"
    command_id = cmd.get("command_id")
    _send_ack(client, action, command_id, {"status": "acknowledged", "timestamp": _utc_now_iso()})

    payload_obj = cmd.get("payload")
    requested = payload_obj.get("sensors") if isinstance(payload_obj, dict) else None
    if not isinstance(requested, list) or not all(isinstance(x, str) for x in requested):
        _send_ack(
            client,
            action,
            command_id,
            {"status": "failed", "result": {"reason": "invalid_payload"}, "timestamp": _utc_now_iso()},
        )
        return

    accepted, rejected = [], []
    for ent in requested:
        if ha_client.is_selectable_entity(ent):
            if ent not in accepted:
                accepted.append(ent)
        else:
            rejected.append(ent)

    try:
        client.selected_sensors = list(accepted)
    except Exception:
        pass

    # Report which of the watched entities Home Assistant has right now, so
    # the vault can show the ones it cannot find.
    states = []
    try:
        wanted = set(accepted)
        states = [
            s
            for s in (fetch_sensors(getattr(client, "ha_api_url", None), getattr(client, "ha_api_token", None)) or [])
            if s.get("entity_id") in wanted and _is_entity_allowed(s.get("entity_id"))
        ]
    except Exception:
        states = []
    report = _states_report(states)

    now_iso = _utc_now_iso()
    try:
        if getattr(client, "vault_topic", None):
            reminder = {
                "schema_version": 1,
                "client_id": client.client_id,
                "timestamp": now_iso,
                "selected_sensors": list(accepted),
            }
            client._publish(client.vault_topic, json.dumps(reminder), qos=0)
    except Exception:
        pass
    _persist_selection(accepted)

    result = {
        "selected": list(accepted),
        "sensors_reported": list(report["data"].keys()),
        "count": len(report["data"]),
        **report,
    }
    if rejected:
        result["rejected"] = rejected
    _send_ack(client, action, command_id, {"status": "completed", "result": result, "timestamp": now_iso})


def _registry_token(client):
    """The token registry/set must carry, or None when updates are disabled."""
    token = getattr(client, "registry_token", None)
    if not token:
        opts = getattr(client, "options", None)
        if isinstance(opts, dict):
            token = opts.get("registry_token") or opts.get("registryToken")
    if not token:
        token = os.environ.get("REGISTRY_TOKEN")
    return token if isinstance(token, str) and token else None


def _valid_registry_doc(doc):
    if not isinstance(doc, dict):
        return False
    if doc.get("registry_mode") not in (None, "allow", "deny", "ALLOW", "DENY"):
        return False
    entries = doc.get("entries", [])
    if not isinstance(entries, list):
        return False
    return all(isinstance(e, dict) and isinstance(e.get("entity_id"), str) for e in entries)


def _handle_registry_set(client, cmd):
    """registry/set: replace the local SENSOR_REGISTRY (privacy allow/deny list).

    Refused unless a registry token is configured (client.registry_token, the
    `registry_token` option or REGISTRY_TOKEN) and the payload carries the same
    token. The token itself is never written to the registry file.
    """
    import hmac
    import pathlib
    import tempfile

    action = "registry/set"
    command_id = cmd.get("command_id")
    _send_ack(client, action, command_id, {"status": "acknowledged"})

    def finish(result):
        status = "completed" if result.get("success") else "failed"
        _send_ack(client, action, command_id, {"status": status, "result": result})

    payload_obj = cmd.get("payload")
    if not payload_obj:
        return finish({"success": False, "reason": "missing_payload"})
    expected = _registry_token(client)
    if expected is None:
        return finish({"success": False, "reason": "registry_updates_disabled"})
    provided = payload_obj.get("token") if isinstance(payload_obj, dict) else None
    if not isinstance(provided, str) or not hmac.compare_digest(provided.encode(), expected.encode()):
        return finish({"success": False, "reason": "auth_failed"})
    doc = {k: v for k, v in payload_obj.items() if k != "token"}
    if not _valid_registry_doc(doc):
        return finish({"success": False, "reason": "invalid_registry"})

    try:
        import mqtt_client as _mc
    except Exception:
        _mc = None
    target = getattr(_mc, "SENSOR_REGISTRY", None) if _mc is not None else None
    target = pathlib.Path(str(target)) if target else pathlib.Path(__file__).parent / "SENSOR_REGISTRY_from_mqtt.json"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=str(target.parent), delete=False) as tf:
            tf.write(json.dumps(doc, indent=2))
            tmpname = tf.name
        pathlib.Path(tmpname).replace(target)
    except Exception as e:
        return finish({"success": False, "reason": str(e)})
    for owner in (_mc, client):
        reload_fn = getattr(owner, "reload_sensor_registry", None) if owner is not None else None
        if callable(reload_fn):
            try:
                reload_fn()
            except Exception:
                pass
    return finish({"success": True, "entries": len(doc.get("entries", []))})


def handle_message(
    client,
    msg,
    payload_str,
    fetch_sensors,
    build_telemetry,
    build_vault_payload,
    requests=None,
):
    """Handle an incoming MQTT message for Vault-style commands.

    Args:
        client: CentralCoreClient instance (for _publish and attributes)
        msg: original message object (with .topic)
        payload_str: decoded payload string (or '<binary>')
        fetch_sensors: callable to fetch sensors from HA
        build_telemetry: callable to build telemetry payloads
        build_vault_payload: callable to build vault payloads
        requests: requests module or None. If None, attempts to import requests.
    """
    if requests is None:
        try:
            import requests
        except Exception:
            requests = None
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
            version = None
            payload_obj = cmd.get("payload") if isinstance(cmd, dict) else None
            if isinstance(payload_obj, dict):
                version = payload_obj.get("version")
            _run_update_command(
                client, action, command_id,
                lambda updater, send: updater.update(expected_version=version, before_install=send),
            )
            return

        expected_check_topic = f"hubs/{client.client_id}/v1/cmd/config/check_update"
        if topic == expected_check_topic:
            try:
                cmd = json.loads(payload_str) if payload_str and payload_str != "<binary>" else {}
            except Exception:
                cmd = {}
            command_id = cmd.get("command_id")
            action = cmd.get("action") or "config/check_update"
            if command_id:
                try:
                    client._publish(client.build_ack_topic(action, command_id),
                                    json.dumps({"status": "acknowledged"}), qos=1)
                except Exception:
                    pass
            _run_update_command(client, action, command_id, lambda updater, send: updater.check())
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
                    "timestamp": datetime.now().astimezone().isoformat().replace("+00:00", "Z"),
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

            # Only publish telemetry if the Vault has requested specific sensors.
            # Without a vault request, we don't know what the user wants.
            if not sensors_requested:
                return

            sensors = fetch_sensors(client.ha_api_url, client.ha_api_token) or []
            # Always apply SENSOR_REGISTRY filtering at minimum
            sensors = [s for s in sensors if _is_entity_allowed(s.get("entity_id"))]

            # Store the selected sensors (vault-requested device classes) for reminder messages
            try:
                client.selected_sensors = list(sensors_requested)
            except Exception:
                # don't let selection storage failure stop command handling
                pass

            # Filter sensors by device_class (vault sends device class names, not entity IDs)
            requested_classes = {str(cls).lower().strip() for cls in sensors_requested if cls}
            sensors = [
                s for s in sensors if s.get("attributes", {}).get("device_class", "").lower() in requested_classes
            ]

            data_map = {}
            raw_map = {}
            for s in sensors:  # pragma: no cover
                ent = s.get("entity_id")  # pragma: no cover
                if not ent:
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
                if not ent:
                    continue
                attrs = _sanitize(s.get("attributes"))
                names_map[ent] = attrs.get("friendly_name") or s.get("name") or ent
                # consider entity disabled if 'disabled_by' attribute is set
                enabled_map[ent] = not bool(attrs.get("disabled_by"))
                attrs_map[ent] = attrs

            # build observed timestamps map (prefer HA-provided timestamps,
            # fall back to current time)
            observed_map = {}
            device_classes_map = {}
            for s in sensors:
                ent = s.get("entity_id")
                if not ent:
                    continue
                obs = s.get("last_changed") or s.get("last_updated")
                obs = _normalize_ts(obs) or datetime.now().astimezone().isoformat()
                observed_map[ent] = obs
                # Extract device_class from attributes
                attrs = s.get("attributes", {}) or {}
                dc = attrs.get("device_class")
                if dc:
                    device_classes_map[ent] = dc

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            telemetry_payload = {
                "data": data_map,
                "raw": raw_map,
                "names": names_map,
                "attributes": attrs_map,
                "enabled": enabled_map,
                "observed": observed_map,
                "device_classes": device_classes_map,
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
                        "device_classes": device_classes_map,
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
            if not isinstance(cmd, dict):
                cmd = {}
            _handle_sensors_set(client, cmd, fetch_sensors)
            return

        # Local override of the SENSOR_REGISTRY. The vault never sends this;
        # it is refused unless a registry token is configured on the hub.
        expected_registry_set = f"hubs/{client.client_id}/v1/cmd/registry/set"
        if topic == expected_registry_set:
            try:
                cmd = json.loads(payload_str) if payload_str and payload_str != "<binary>" else {}
            except Exception:
                cmd = {}
            if not isinstance(cmd, dict):
                cmd = {}
            _handle_registry_set(client, cmd)
            return
    except Exception:
        traceback.print_exc()  # pragma: no cover
