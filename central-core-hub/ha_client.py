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
import typing
from datetime import datetime, timezone
from typing import Optional

try:
    import ha_safety as _safety
except ImportError:  # loaded by path without the add-on directory on sys.path
    import importlib.util as _ilu
    import pathlib as _pl
    import sys as _sys

    _spec = _ilu.spec_from_file_location("ha_safety", str(_pl.Path(__file__).with_name("ha_safety.py")))
    assert _spec is not None and _spec.loader is not None
    _safety = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_safety)
    _sys.modules["ha_safety"] = _safety

# re-exported for callers of ha_client
SELECTABLE_DOMAINS = _safety.SELECTABLE_DOMAINS
check_token_transport = _safety.check_token_transport
is_selectable_entity = _safety.is_selectable_entity
is_valid_entity_id = _safety.is_valid_entity_id
sanitize_attributes = _safety.sanitize_attributes

# Path to the add-on options file. Tests can monkeypatch this variable to
# redirect writes to a temporary location.
OPTIONS_PATH = "/data/options.json"

# In-memory cache for the discovered Home Assistant version. Store a
# small struct with the version string and the timestamp it was set so
# consumers can apply a TTL without hitting the filesystem.
_HA_VERSION_CACHE: typing.Optional[dict] = None

# Get the local timezone for timestamp normalization


def _normalize_timestamp(ts_str: Optional[str]) -> Optional[str]:
    """Normalize a timestamp string to UTC ISO format.

    Parses ISO timestamp strings and converts them to UTC.
    If parsing fails, returns the original string.
    """
    if not ts_str:
        return ts_str
    try:
        # Handle 'Z' suffix by replacing with +00:00 for parsing
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            # A naive time is local, with that date's rules (DST included)
            dt = dt.astimezone()
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return ts_str


def set_ha_version(version: str, ts: float | None = None):
    """Set the in-memory cached HA version with optional timestamp.

    If `ts` is not provided, the current time is used.
    """
    global _HA_VERSION_CACHE
    try:
        if version is None:
            _HA_VERSION_CACHE = None
            return
        ver = str(version)
        _HA_VERSION_CACHE = {"version": ver, "ts": float(ts or time.time())}
    except Exception:
        _HA_VERSION_CACHE = None


def get_ha_version(ttl_seconds: float | None = None):
    """Return the in-memory cached HA version or None.

    If `ttl_seconds` is provided, return None when the cached value is
    older than the TTL.
    """
    global _HA_VERSION_CACHE
    if not _HA_VERSION_CACHE:
        return None
    try:
        ver = _HA_VERSION_CACHE.get("version")
        ts = _HA_VERSION_CACHE.get("ts")
        if ttl_seconds is not None and ts is not None:
            try:
                if (time.time() - float(ts)) > float(ttl_seconds):
                    return None
            except Exception:
                # If timestamp arithmetic fails, be conservative and
                # return None so callers will re-resolve.
                return None
        return ver
    except Exception:
        return None


try:
    import requests
except Exception:
    requests = None

try:
    import websocket
    from websocket._exceptions import (
        WebSocketAddressException,
        WebSocketTimeoutException,
        WebSocketConnectionClosedException,
    )
except Exception:
    websocket = None
    WebSocketAddressException = None
    WebSocketTimeoutException = None
    WebSocketConnectionClosedException = None


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
            # Include both sensor.* and binary_sensor.* entities
            if ent_id and (ent_id.startswith("sensor.") or ent_id.startswith("binary_sensor.")):
                # Return all sensors. Device class filtering is handled by vault/MQTT layer.
                attrs = sanitize_attributes(ent.get("attributes"))
                sensors.append(
                    {
                        "entity_id": ent_id,
                        "state": ent.get("state"),
                        "name": attrs.get("friendly_name") or ent_id,
                        "attributes": attrs,
                        # Preserve HA timestamps when present so downstream systems
                        # can reason about data recency.
                        "last_changed": _normalize_timestamp(ent.get("last_changed")),
                        "last_updated": _normalize_timestamp(ent.get("last_updated")),
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
        if not is_valid_entity_id(ent_id):
            continue
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
                attrs = sanitize_attributes(data.get("attributes"))
                results.append(
                    {
                        "entity_id": data.get("entity_id"),
                        "state": data.get("state"),
                        "name": attrs.get("friendly_name") or data.get("entity_id"),
                        "attributes": attrs,
                        "last_changed": _normalize_timestamp(data.get("last_changed")),
                        "last_updated": _normalize_timestamp(data.get("last_updated")),
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
    """Minimal HA websocket listener to stream state_changed events for selected sensors.

    Accepts an optional `on_ha_version` callback that will be invoked when
    the listener discovers/persists a Home Assistant version string. This
    allows the caller to perform one-shot actions (e.g. publish telemetry)
    when the HA core version becomes available.
    """

    def __init__(
        self,
        ha_api_url,
        ha_api_token,
        on_event,
        log_fn=None,
        selectors=None,
        on_ha_version=None,
        on_snapshot=None,
    ):
        self.ha_api_url = ha_api_url
        self.ha_api_token = ha_api_token
        self.on_event = on_event
        self.on_ha_version = on_ha_version
        # Called with the list of current states when a subscription starts
        # (HA sends them all at once); falls back to on_event per entity.
        self.on_snapshot = on_snapshot
        self.log_fn = log_fn or (lambda m: None)
        self.selectors = set(selectors or [])
        self._thread = None
        self._stop = threading.Event()
        self._ws = None
        self._prot_req_lock = threading.Lock()
        # Held from id allocation until the message is sent, so messages leave
        # in id order whichever thread sends them.
        self._send_order_lock = threading.RLock()
        self._next_request_id = 3
        self._pending_requests: dict[int, dict[str, typing.Any]] = {}
        # subscribe_entities state: the live subscription id, whether its
        # initial snapshot has arrived, and the expanded state per entity
        # (needed to apply HA's compressed diffs).
        self._authed = False
        self._sub_id = None
        self._streaming = threading.Event()
        self._states: dict[str, dict] = {}

    def update_selectors(self, selectors):
        """Watch a new set of entities; re-subscribes when connected."""
        new = set(selectors or [])
        if new == self.selectors:
            return
        self.selectors = new
        self._subscribe()

    def is_streaming(self):
        """True while a subscription is live and has delivered its snapshot."""
        return self._ws is not None and self._streaming.is_set()

    def _send_command(self, payload):
        """Send a command with the next message id. Ids are allocated and sent
        under one lock because Home Assistant requires them to increase."""
        ws = self._ws
        if ws is None:
            return None
        with self._send_order_lock:
            with self._prot_req_lock:
                req_id = self._next_request_id
                self._next_request_id += 1
            message = dict(payload)
            message["id"] = req_id
            ws.send(json.dumps(message))
        return req_id

    def _subscribe(self):
        """(Re)subscribe to state changes of the selected entities only."""
        if self._ws is None or not self._authed:
            return  # _run subscribes after authenticating
        old = self._sub_id
        self._sub_id = None
        self._streaming.clear()
        try:
            if old is not None:
                self._send_command({"type": "unsubscribe_events", "subscription": old})
            self._states = {k: v for k, v in self._states.items() if k in self.selectors}
            entity_ids = sorted(e for e in self.selectors if is_valid_entity_id(e))
            if entity_ids:
                self._sub_id = self._send_command({"type": "subscribe_entities", "entity_ids": entity_ids})
            self._log(f"HA WS watching {len(entity_ids)} entities")
        except Exception as exc:
            self._log(f"HA WS subscribe failed: {exc}")

    @staticmethod
    def _iso_from_epoch(value):
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            return None

    def _expand_state(self, entity_id, compressed):
        """A state dict from subscribe_entities' compressed form."""
        last_changed = self._iso_from_epoch(compressed.get("lc"))
        return {
            "entity_id": entity_id,
            "state": compressed.get("s"),
            "attributes": dict(compressed.get("a") or {}),
            "last_changed": last_changed,
            "last_updated": self._iso_from_epoch(compressed.get("lu")) or last_changed,
        }

    def _apply_diff(self, base, diff):
        """Apply a subscribe_entities change ({"+": additions, "-": removals})."""
        state = dict(base)
        attrs = dict(base.get("attributes") or {})
        plus = diff.get("+") or {}
        minus = diff.get("-") or {}
        if "s" in plus:
            state["state"] = plus["s"]
        if "lc" in plus:
            state["last_changed"] = state["last_updated"] = self._iso_from_epoch(plus["lc"])
        elif "lu" in plus:
            state["last_updated"] = self._iso_from_epoch(plus["lu"])
        attrs.update(plus.get("a") or {})
        for key in minus.get("a") or []:
            attrs.pop(key, None)
        state["attributes"] = attrs
        return state

    def _handle_entities_event(self, event):
        added = event.get("a")
        if isinstance(added, dict):
            snapshot = []
            for eid, compressed in added.items():
                st = self._expand_state(eid, compressed or {})
                self._states[eid] = st
                snapshot.append(st)
            self._streaming.set()
            if callable(self.on_snapshot):
                self.on_snapshot(snapshot)
            elif self.on_event:
                for st in snapshot:
                    self.on_event(st["entity_id"], st)
        for eid, diff in (event.get("c") or {}).items():
            base = self._states.get(eid)
            if base is None:
                continue
            st = self._apply_diff(base, diff or {})
            self._states[eid] = st
            if self.on_event:
                self.on_event(eid, st)
        for eid in event.get("r") or []:
            self._states.pop(eid, None)

    def _ws_url(self):
        base = (self.ha_api_url or "").strip().rstrip("/")
        if not base:
            return None
        if base.startswith("https://"):
            base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://") :]
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
        # Idempotent stop: if already requested, return immediately
        try:
            if self._stop.is_set():
                return
        except Exception:
            # If _stop is not a proper Event for some reason, continue
            pass

        self._stop.set()
        try:
            if self._ws:
                try:
                    self._ws.close()
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()
        # Attempt to join the thread (short timeout) and clear references
        try:
            thr = getattr(self, "_thread", None)
            if thr is not None and getattr(thr, "is_alive", lambda: False)():
                try:
                    thr.join(timeout=2)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self._ws = None
        except Exception:
            pass
        try:
            self._thread = None
        except Exception:
            pass

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

    def _register_request(self):
        event = threading.Event()
        with self._prot_req_lock:
            req_id = self._next_request_id
            self._next_request_id += 1
            self._pending_requests[req_id] = {"event": event, "result": None}
        return req_id, event

    def _set_pending_result(self, req_id, result):
        if req_id is None:
            return
        with self._prot_req_lock:
            pending = self._pending_requests.get(req_id)
        if pending is None:
            return
        pending["result"] = result
        try:
            pending["event"].set()
        except Exception:
            pass

    def call_service(
        self,
        domain: str,
        service: str,
        service_data: typing.Optional[typing.Dict[str, typing.Any]] = None,
        timeout: float = 15.0,
    ) -> typing.Optional[typing.Dict[str, typing.Any]]:
        """Call a Home Assistant service over the websocket connection."""
        if not self._ws:
            return None
        payload: typing.Dict[str, typing.Any] = {
            "type": "call_service",
            "domain": domain,
            "service": service,
        }
        if service_data:
            payload["service_data"] = dict(service_data)
        with self._send_order_lock:
            try:
                req_id, event = self._register_request()
            except Exception:
                return None
            payload["id"] = req_id
            try:
                self._send_json(self._ws, payload)
            except Exception:
                with self._prot_req_lock:
                    self._pending_requests.pop(req_id, None)
                return None
        completed = event.wait(timeout)
        with self._prot_req_lock:
            final = self._pending_requests.pop(req_id, None)
        if not completed or final is None:
            return None
        return final.get("result")

    def request(self, payload, timeout: float = 15.0):
        """Send any websocket command and return Home Assistant's full reply.

        The reply is the whole message ({"success", "result", "error"}), so a
        caller can tell "unauthorized" from "no answer" (None).
        """
        if not self._ws:
            return None
        with self._send_order_lock:
            try:
                req_id, event = self._register_request()
            except Exception:
                return None
            message = dict(payload)
            message["id"] = req_id
            try:
                self._send_json(self._ws, message)
            except Exception:
                with self._prot_req_lock:
                    self._pending_requests.pop(req_id, None)
                return None
        completed = event.wait(timeout)
        with self._prot_req_lock:
            final = self._pending_requests.pop(req_id, None)
        if not completed or final is None:
            return None
        return final.get("result")

    def _persist_ha_version(self, version):
        """Cache and persist the discovered HA version."""
        if version is None:
            return False
        try:
            version_str = str(version)
        except Exception:
            return False

        try:
            # Store with timestamp so callers may apply a TTL
            set_ha_version(version_str, ts=time.time())
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
        opts["ha_version"] = version_str
        write_ok = False
        try:
            with open(opts_path, "w") as f:
                json.dump(opts, f)
            self._log(f"Wrote ha_version={version_str} to {opts_path}")
            write_ok = True
        except Exception as e:
            self._log(f"Failed to write ha_version to {opts_path}: {e}")
        # Notify caller that we discovered a HA version even if writing
        # to disk fails so one-shot telemetry hooks still fire.
        try:
            cb = getattr(self, "on_ha_version", None)
            if callable(cb):
                try:
                    cb(version_str)
                except Exception:
                    traceback.print_exc()
        except Exception:
            pass
        return write_ok

    def _run(self):
        timeout_exc_cls = WebSocketTimeoutException or (
            websocket and getattr(websocket, "WebSocketTimeoutException", None)
        )
        addr_exc_cls = WebSocketAddressException or (
            websocket and getattr(websocket, "WebSocketAddressException", None)
        )
        closed_exc_cls = WebSocketConnectionClosedException or (
            websocket and getattr(websocket, "WebSocketConnectionClosedException", None)
        )

        # Reconnect loop with backoff: keep attempting to connect until stopped
        backoff = 1.0
        max_backoff = 30.0
        while not self._stop.is_set():
            ws_url = self._ws_url()
            if not ws_url:
                return
            self._log(f"HA WS connecting to {ws_url}")
            if websocket is None or getattr(websocket, "create_connection", None) is None:
                self._log("websocket client not available")
                return
            try:
                self._ws = websocket.create_connection(ws_url, timeout=15)
                # successful connect -> reset backoff
                backoff = 1.0
            except Exception as exc:
                if addr_exc_cls and isinstance(exc, addr_exc_cls):
                    self._log(f"HA WS connection error: {exc}")
                else:
                    traceback.print_exc()
                # Wait with backoff before retrying
                if self._stop.wait(backoff):
                    break
                backoff = min(backoff * 2, max_backoff)
                continue

            try:
                # Expect auth_required, then send auth
                ha_version_written = False
                hello_raw = self._ws.recv()
                hello = json.loads(hello_raw or "{}")
                if hello.get("type") != "auth_required":
                    self._log("HA WS unexpected hello")
                    # close and attempt reconnect
                    try:
                        self._ws.close()
                    except Exception:
                        pass
                    self._ws = None
                    if self._stop.wait(1.0):
                        break
                    continue
                if hello.get("ha_version"):
                    ha_version_written = self._persist_ha_version(hello.get("ha_version"))
                self._send_json(self._ws, {"type": "auth", "access_token": self.ha_api_token})
                auth_resp = json.loads(self._ws.recv() or "{}")
                if auth_resp.get("type") != "auth_ok":
                    self._log("HA WS auth failed")
                    try:
                        self._ws.close()
                    except Exception:
                        pass
                    self._ws = None
                    if self._stop.wait(1.0):
                        break
                    continue
                try:
                    self._send_json(self._ws, {"id": 2, "type": "get_config"})
                except Exception:
                    pass
                # Watch only the selected entities (not every state change).
                self._authed = True
                self._sub_id = None
                self._states = {}
                self._subscribe()

                last_ping = time.time()
                while not self._stop.is_set():
                    now = time.time()
                    if now - last_ping > 20:
                        self._send_json(self._ws, {"type": "ping"})
                        last_ping = now
                    try:
                        raw = self._ws.recv()
                    except Exception as exc:
                        # Ignore timeouts; attempt reconnect for closed connection
                        if timeout_exc_cls and isinstance(exc, timeout_exc_cls):
                            continue
                        if closed_exc_cls and isinstance(exc, closed_exc_cls):
                            self._log(f"HA WS connection closed: {exc}")
                            break
                        # For address errors, log and break to reconnect
                        if addr_exc_cls and isinstance(exc, addr_exc_cls):
                            self._log(f"HA WS connection error: {exc}")
                            break
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
                    if msg.get("type") == "result":
                        req_id = msg.get("id")
                        if req_id is not None and req_id == self._sub_id:
                            if not msg.get("success", True):
                                self._log(f"HA WS subscribe_entities refused: {msg.get('error')}")
                            continue
                        if req_id == 2 and not ha_version_written:
                            try:
                                res = msg.get("result") or {}
                                ha_version = None
                                if isinstance(res, dict):
                                    ha_version = (
                                        res.get("version")
                                        or res.get("homeassistant_version")
                                        or (res.get("config") or {}).get("version")
                                    )
                                if ha_version:
                                    ha_version_written = self._persist_ha_version(ha_version)
                            except Exception:
                                pass
                            continue
                        self._set_pending_result(req_id, msg)
                        continue
                    if msg.get("type") != "event":
                        continue
                    event = msg.get("event") or {}
                    if "data" not in event:
                        # subscribe_entities: only the live subscription counts
                        if msg.get("id") is not None and msg.get("id") == self._sub_id:
                            try:
                                self._handle_entities_event(event)
                            except Exception:
                                traceback.print_exc()
                        continue
                    # state_changed event format
                    data = event.get("data", {}) or {}
                    ent_id = data.get("entity_id")
                    if self.selectors and ent_id not in self.selectors:
                        continue
                    new_state = data.get("new_state") or {}
                    if self.on_event:
                        try:
                            self.on_event(ent_id, new_state)
                        except Exception:
                            traceback.print_exc()
            finally:
                self._authed = False
                self._sub_id = None
                self._streaming.clear()
                try:
                    if self._ws:
                        try:
                            self._ws.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                self._ws = None
                # Small backoff before reconnect attempt; record the result
                try:
                    should_break = self._stop.wait(1.0)
                except Exception:
                    # if wait fails for some reason, do not break
                    should_break = False

            # break must occur outside of the finally block to satisfy static
            # analyzers that forbid `break` inside `finally`.
            if should_break:
                break
