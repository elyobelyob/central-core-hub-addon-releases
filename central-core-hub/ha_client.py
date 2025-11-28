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

# Path to the add-on options file. Tests can monkeypatch this variable to
# redirect writes to a temporary location.
OPTIONS_PATH = "/data/options.json"

# In-memory cache for the discovered Home Assistant version. This avoids
# filesystem reads on every telemetry publish; the websocket listener will
# populate this when it learns the version.
_HA_VERSION_CACHE = None


def set_ha_version(version: str):
    """Set the in-memory cached HA version."""
    global _HA_VERSION_CACHE
    try:
        _HA_VERSION_CACHE = str(version) if version is not None else None
    except Exception:
        _HA_VERSION_CACHE = None


def get_ha_version():
    """Return the in-memory cached HA version or None."""
    return _HA_VERSION_CACHE


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


# Note: REST-based info extraction was found to be unreliable for HA version
# in some deployments because the version is only exposed over the websocket
# API. The prior `fetch_ha_info` helper was removed in favor of reading a
# websocket-populated `ha_version` value from the add-on options file.


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
            # Request HA config/version once after auth. Some HA installations
            # expose version information only via the websocket API. We send a
            # `get_config` request (id=2) and handle the `result` message below.
            try:
                self._send_json(self._ws, {"id": 2, "type": "get_config"})
            except Exception:
                pass
            ha_version_written = False
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
                # Handle result responses such as the get_config reply (id=2)
                if msg.get("type") == "result" and msg.get("id") == 2 and not ha_version_written:
                    try:
                        res = msg.get("result") or {}
                        # Try several common keys where HA may publish its version
                        ha_version = None
                        if isinstance(res, dict):
                            ha_version = (
                                res.get("version")
                                or res.get("homeassistant_version")
                                or (res.get("config") or {}).get("version")
                            )
                        # Persist to the add-on options path (tests may override
                        # `OPTIONS_PATH`) similarly to `run.sh` so the main process
                        # can pick up the discovered HA version.
                        if ha_version:
                            try:
                                # Update in-memory cache first so telemetry can
                                # immediately pick up the value without reading
                                # the options file.
                                try:
                                    set_ha_version(ha_version)
                                except Exception:
                                    pass
                                opts_path = OPTIONS_PATH
                                try:
                                    with open(opts_path, "r") as f:
                                        opts = json.load(f)
                                except Exception:
                                    opts = {}
                                if not isinstance(opts, dict):
                                    opts = {}
                                opts["ha_version"] = str(ha_version)
                                try:
                                    with open(opts_path, "w") as f:
                                        json.dump(opts, f)
                                    self._log(f"Wrote ha_version={ha_version} to {opts_path}")
                                    ha_version_written = True
                                except Exception as e:
                                    self._log(f"Failed to write ha_version to {opts_path}: {e}")
                            except Exception:
                                pass
                    except Exception:
                        pass
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
