#!/usr/bin/env python3
"""
Home Assistant integration helpers for Central Core Hub.

Responsibilities:
- Fetch sensors via REST (/api/states and per-entity /api/states/<id>)
- Stream state_changed events over the HA websocket API with ping/pong keepalive
"""
import json
import threading
import time
import traceback
# datetime/timezone not used in this module

try:
    import requests
except Exception:
    requests = None

try:
    import websocket
    from websocket._exceptions import (
        WebSocketAddressException,
        WebSocketTimeoutException,
    )
except Exception:
    websocket = None
    WebSocketAddressException = None
    WebSocketTimeoutException = None


def fetch_sensors(ha_api_url, ha_api_token, requests_mod=None):
    req = requests_mod or requests
    if not ha_api_url or not ha_api_token or req is None:
        return None
    try:
        url = ha_api_url.rstrip("/") + "/api/states"
        headers = {
            "Authorization": f"Bearer {ha_api_token}",
            "Content-Type": "application/json",
        }
        r = req.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        sensors = []
        for ent in data:
            ent_id = ent.get("entity_id")
            if ent_id and ent_id.startswith("sensor."):
                sensors.append(
                    {
                        "entity_id": ent_id,
                        "state": ent.get("state"),
                        "name": ent.get("attributes", {}).get("friendly_name")
                        or ent_id,
                        "attributes": ent.get("attributes", {}) or {},
                        # Preserve HA timestamps when present so downstream systems
                        # can reason about data recency.
                        "last_changed": ent.get("last_changed"),
                        "last_updated": ent.get("last_updated"),
                    }
                )
        return sensors
    except Exception:
        return None


def fetch_sensors_by_ids(ha_api_url, ha_api_token, entity_ids, requests_mod=None):
    """Fetch specific sensors via per-entity /api/states/<entity_id> endpoints."""
    req = requests_mod or requests
    if not ha_api_url or not ha_api_token or req is None:
        return None
    results = []
    for ent_id in entity_ids or []:
        try:
            url = ha_api_url.rstrip("/") + f"/api/states/{ent_id}"
            headers = {
                "Authorization": f"Bearer {ha_api_token}",
                "Content-Type": "application/json",
            }
            r = req.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            if data.get("entity_id"):
                results.append(
                    {
                        "entity_id": data.get("entity_id"),
                        "state": data.get("state"),
                        "name": data.get("attributes", {}).get("friendly_name")
                        or data.get("entity_id"),
                        "attributes": data.get("attributes", {}) or {},
                        "last_changed": data.get("last_changed"),
                        "last_updated": data.get("last_updated"),
                    }
                )
        except Exception:
            continue
    return results


def fetch_ha_info(ha_api_url, ha_api_token, requests_mod=None):
    """Fetch basic Home Assistant instance information useful for telemetry.

    This is a best-effort helper that attempts a few well-known endpoints
    and maps likely keys to a small, stable dict. Returns None on error.
    """
    req = requests_mod or requests
    if not ha_api_url or not ha_api_token or req is None:
        return None
    endpoints = ["/api/config", "/api/info", "/api/"]
    base = ha_api_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {ha_api_token}",
        "Content-Type": "application/json",
    }
    for ep in endpoints:
        try:
            url = base + ep
            r = req.get(url, headers=headers, timeout=5)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                continue
            # Map a few likely fields to a compact shape used by telemetry
            info = {}
            # installation method
            info["installation_method"] = (
                data.get("installation_type")
                or data.get("installation_method")
                or data.get("installation")
                or None
            )
            # core version
            info["core"] = data.get("version") or data.get("core_version") or None
            # supervisor
            sup = data.get("supervisor")
            if isinstance(sup, dict):
                info["supervisor"] = sup.get("version")
            else:
                info["supervisor"] = data.get("supervisor_version") or data.get(
                    "supervisor"
                )
            # operating system
            # Build a readable operating system string from available fields.
            os_name = data.get("os_name")
            os_version = data.get("os_version")
            if os_name and os_version:
                os_combined = f"{os_name} {os_version}"
            else:
                os_combined = os_name or data.get("operating_system")
            info["operating_system"] = os_combined or None
            # frontend / frontend version
            info["frontend"] = (
                data.get("frontend")
                or data.get("frontend_version")
                or data.get("frontend_url")
                or None
            )
            # If at least one meaningful field present, return it
            if any(v for v in info.values()):
                return info
        except Exception:
            continue
    return None


class HAWebSocketListener:
    """Minimal HA websocket listener to stream state_changed events for selected sensors."""

    def __init__(self, ha_api_url, ha_api_token, on_event, log_fn=None, selectors=None):
        self.ha_api_url = ha_api_url
        self.ha_api_token = ha_api_token
        self.on_event = on_event
        self.log_fn = log_fn or (lambda m: None)
        self.selectors = set(selectors or [])
        self._thread = None
        self._stop = threading.Event()
        self._ws = None

    def update_selectors(self, selectors):
        self.selectors = set(selectors or [])

    def _ws_url(self):
        base = (self.ha_api_url or "").strip().rstrip("/")
        if not base:
            return None
        if base.startswith("https://"):
            base = "wss://" + base[len("https://"):]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://"):]
        return f"{base}/api/websocket"

    def start(self):
        if websocket is None:
            self._log("websocket-client not installed; HA WS disabled")
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            traceback.print_exc()

    def _send_json(self, sock, obj):
        try:
            sock.send(json.dumps(obj))
        except Exception:
            traceback.print_exc()

    def _log(self, msg):
        try:
            self.log_fn(msg)
        except Exception:
            pass

    def _run(self):
        timeout_exc_cls = (
            WebSocketTimeoutException
            or (websocket and getattr(websocket, "WebSocketTimeoutException", None))
        )
        addr_exc_cls = (
            WebSocketAddressException
            or (websocket and getattr(websocket, "WebSocketAddressException", None))
        )

        try:
            ws_url = self._ws_url()
            if not ws_url:
                return
            self._log(f"HA WS connecting to {ws_url}")
            if websocket is None or getattr(websocket, "create_connection", None) is None:
                self._log("websocket client not available")
                return
            self._ws = websocket.create_connection(ws_url, timeout=15)
            # Expect auth_required, then send auth
            hello_raw = self._ws.recv()
            hello = json.loads(hello_raw or "{}")
            if hello.get("type") != "auth_required":
                self._log("HA WS unexpected hello")
                return
            self._send_json(
                self._ws, {"type": "auth", "access_token": self.ha_api_token}
            )
            auth_resp = json.loads(self._ws.recv() or "{}")
            if auth_resp.get("type") != "auth_ok":
                self._log("HA WS auth failed")
                return
            # Subscribe to state_changed events
            self._send_json(
                self._ws,
                {"id": 1, "type": "subscribe_events", "event_type": "state_changed"},
            )
            last_ping = time.time()
            while not self._stop.is_set():
                now = time.time()
                if now - last_ping > 20:
                    self._send_json(self._ws, {"type": "ping"})
                    last_ping = now
                try:
                    raw = self._ws.recv()
                except Exception as exc:
                    if timeout_exc_cls and isinstance(exc, timeout_exc_cls):
                        continue
                    traceback.print_exc()
                    break
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "pong":
                    continue
                if msg.get("type") != "event":
                    continue
                data = msg.get("event", {}).get("data", {}) or {}
                ent_id = data.get("entity_id")
                if self.selectors and ent_id not in self.selectors:
                    continue
                new_state = data.get("new_state") or {}
                if self.on_event:
                    try:
                        self.on_event(ent_id, new_state)
                    except Exception:
                        traceback.print_exc()
        except Exception as exc:
            if addr_exc_cls and isinstance(exc, addr_exc_cls):
                self._log(f"HA WS connection error: {exc}")
            else:
                traceback.print_exc()
        finally:
            try:
                if self._ws:
                    self._ws.close()
            except Exception:
                pass
            self._ws = None
