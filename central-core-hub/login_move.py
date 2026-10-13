#!/usr/bin/env python3
"""Move this hub onto a new MQTT broker login, sent by the vault (protocol 1.5).

The flow (docs/LOGIN_MOVE.md has the full description):

1. `login/key_request`: make a one-use X25519 key and answer with its public half
   and a request id. The key lives in memory only and expires after about 10 minutes.
2. `login/change`: decrypt the new username and password (the hub id and request
   id must match), test the login on a second MQTT connection, and only if the
   test passes save it and switch the main connection over. If the main
   connection is not up within about 2 minutes, go back to the old login.
3. Report the result on whichever login the hub ends up on. The password is never
   logged, reported or put in an exception message.

Saving: the login goes into an override file in /data (mode 0600) that wins over
options.json, and survives restarts. The add-on's options in Home Assistant are
NOT rewritten: the Supervisor would let us (an add-on may POST its own options),
but that call sends every option, so it can undo an edit the owner has not
restarted for yet, and options.json is only refreshed on a restart. The screen
therefore keeps showing the old login; the start-up log line and the vault show
the one in use. If a move is found unconfirmed at start-up (the process died
mid-move), the hub keeps whichever of the two logins connects.

Everything that touches paho or the clock is injectable, so the tests drive the
whole flow without a network.
"""

import base64
import hmac
import json
import os
import pathlib
import secrets
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

DATA_DIR_ENV = "MQTT_LOGIN_DIR"
DEFAULT_DATA_DIR = "/data"
OVERRIDE_NAME = "login_override.json"
PENDING_NAME = "login_pending.json"

# Mirrors central_core_mqtt_shared.login_change (v1.5.2): the add-on's own copy, so the
# timing holds even with an older shared package.
KEY_TTL_SECONDS = 600
TEST_TIMEOUT_SECONDS = 30
ROLLBACK_WINDOW_SECONDS = 120
KEYS_MAX = 4
MIN_STEP_SECONDS = 15  # never give up on a login faster than this when the broker answers at once
MAX_BACKOFF_SECONDS = 120
USED_IDS_MAX = 32
MAX_FIELD_CHARS = 8192

# The broker logins a hub accepts from the vault: `hub-<hub id>` and its two slots.
# Anything else (the shared login, another hub's login) is refused, so a forged
# message cannot move the hub back to a login that is about to lose its access.
LOGIN_NAME_PREFIX = "hub-"
LOGIN_NAME_SLOTS = ("", "-a", "-b")


def allowed_username(client_id, username):
    return isinstance(username, str) and username in {f"{LOGIN_NAME_PREFIX}{client_id}{slot}" for slot in LOGIN_NAME_SLOTS}


def _text(value):
    """`value` if it is a non-empty string of a sane size, else None."""
    return value if isinstance(value, str) and 0 < len(value) <= MAX_FIELD_CHARS else None


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(msg, file=None):
    ts = _utc_now_iso()
    print(f"[{ts}] {msg}", file=file or sys.stdout, flush=True)


def _data_dir():
    return pathlib.Path(os.environ.get(DATA_DIR_ENV) or DEFAULT_DATA_DIR)


def _load_crypto():
    """The shared package's login_change module (needs `cryptography`)."""
    from central_core_mqtt_shared import login_change

    return login_change


def _write_private(path, data):
    """Write JSON to `path` atomically, readable by the owner only, and flush it to disk."""
    path = pathlib.Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        os.unlink(tmp)  # a stale file would keep its old mode
    except FileNotFoundError:
        pass
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(tmp), flags, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, path)
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass  # the file is in place; only the directory entry's flush failed


def _read_json(path):
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _remove(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class LoginSaveError(Exception):
    """The login could not be saved. Never carries the login."""


def _login_ok(value):
    return (isinstance(value, dict) and isinstance(value.get("username"), str)
            and isinstance(value.get("password"), str))


class LoginStore:
    """Where the hub's broker login is kept between runs.

    `override` (login_override.json) holds the login last saved by the vault and
    wins over options.json. `pending` (login_pending.json) exists from the moment a
    new login is about to be saved until a login has connected; it holds both the
    new and the old login so a start-up can finish or undo the move.
    """

    def __init__(self, data_dir=None, options_path=None):
        self.dir = pathlib.Path(data_dir) if data_dir else _data_dir()
        env_path = os.environ.get("MQTT_OPTIONS_PATH")
        self.options_path = pathlib.Path(options_path or env_path or self.dir / "options.json")
        self.override_path = self.dir / OVERRIDE_NAME
        self.pending_path = self.dir / PENDING_NAME

    def effective(self, options):
        """(username, password, source) the hub should connect with: the override, else `options`."""
        options = options if isinstance(options, dict) else {}
        data = _read_json(self.override_path)
        if data and _login_ok(data) and data["username"]:
            return data["username"], data["password"], "override"
        return str(options.get("mqtt_username") or ""), str(options.get("mqtt_password") or ""), "options"

    def save(self, username, password):
        """Use this login from now on and after restarts. Raises LoginSaveError (without the login)."""
        try:
            _write_private(self.override_path, {"username": username, "password": password})
        except OSError as exc:
            raise LoginSaveError(f"could not write the override file: {type(exc).__name__}") from None

    def restore(self, username, password):
        """Put an earlier login back: no override at all if options.json already holds it."""
        opts = _read_json(self.options_path) or {}
        if (str(opts.get("mqtt_username") or ""), str(opts.get("mqtt_password") or "")) == (username, password):
            try:
                _remove(self.override_path)
            except OSError as exc:
                raise LoginSaveError(f"could not remove the override file: {type(exc).__name__}") from None
            return
        self.save(username, password)

    def reset(self):
        """Forget the saved login and any unconfirmed move (the owner asked, in the add-on options)."""
        for path in (self.override_path, self.pending_path):
            _remove(path)

    def write_pending(self, record):
        try:
            _write_private(self.pending_path, record)
        except OSError as exc:
            raise LoginSaveError(f"could not write the pending record: {type(exc).__name__}") from None

    def read_pending(self):
        data = _read_json(self.pending_path)
        if not data or not _login_ok(data.get("previous")) or not _login_ok(data.get("new")):
            return None
        if not isinstance(data.get("command_id"), str) or not isinstance(data.get("request_id"), str):
            return None
        try:
            if len(base64.b64decode(data.get("confirm_key") or "", validate=True)) != 32:
                return None
        except (ValueError, TypeError):
            return None
        return data

    def clear_pending(self):
        _remove(self.pending_path)


def apply_saved_login(options, data_dir=None, store=None):
    """The add-on options with the vault-saved login applied. Returns (options, source).

    `reset_saved_login: true` in the add-on options throws the saved login away first
    (the way to undo a move on site, without touching files)."""
    store = store or LoginStore(data_dir=data_dir)
    if options.get("reset_saved_login") is True:
        store.reset()
        _log("reset_saved_login is on: the login saved by the vault was removed. "
             "Turn the option off again, or every restart removes a login the vault saves.")
    user, pw, source = store.effective(options)
    if source == "options":
        return options, source
    merged = dict(options)
    merged["mqtt_username"] = user
    merged["mqtt_password"] = pw
    return merged, source


def paho_probe(owner, username, password, probe_topic, subscribe_topics, timeout, mqtt_mod=None):
    """Try a login on a second MQTT connection (MQTT v5, so the broker's refusals are visible).

    Connects with a client id that cannot collide with the live one, subscribes
    to `subscribe_topics`, and publishes one message to `probe_topic`, then checks
    the broker accepted all three. Returns None on success or a reason string:
    "connect_failed" or "access_failed". Never raises, never logs the login."""
    if mqtt_mod is None:
        import paho.mqtt.client as mqtt_mod
    if getattr(owner, "_tls_error", None):
        return "connect_failed"
    state = {"connack": None, "suback": None, "puback": None}
    got = {"connect": threading.Event(), "sub": threading.Event(), "pub": threading.Event()}

    def bad(code):
        failure = getattr(code, "is_failure", None)
        if failure is not None:
            return bool(failure)
        try:
            return int(code) >= 0x80  # MQTT v5 reason codes from 0x80 up are failures
        except (TypeError, ValueError):
            return True

    def on_connect(_c, _u, _flags, reason_code, _props=None):
        state["connack"] = reason_code
        got["connect"].set()

    def on_subscribe(_c, _u, _mid, reason_codes, _props=None):
        state["suback"] = reason_codes
        got["sub"].set()

    def on_publish(_c, _u, _mid, reason_code=None, _props=None):
        state["puback"] = reason_code
        got["pub"].set()

    client = None
    try:
        client_id = f"{owner.client_id}-lt-{secrets.token_hex(3)}"
        client = mqtt_mod.Client(
            callback_api_version=getattr(mqtt_mod, "CallbackAPIVersion").VERSION2,
            client_id=client_id,
            protocol=mqtt_mod.MQTTv5,
        )
        client.username_pw_set(username, password)
        if getattr(owner, "mqtt_tls", False):
            tls_kwargs = {}
            if getattr(owner, "mqtt_ca", None):
                tls_kwargs["ca_certs"] = owner.mqtt_ca
            if getattr(owner, "mqtt_cert", None) and getattr(owner, "mqtt_key", None):
                tls_kwargs["certfile"] = owner.mqtt_cert
                tls_kwargs["keyfile"] = owner.mqtt_key
            client.tls_set(**tls_kwargs)
        client.on_connect = on_connect
        client.on_subscribe = on_subscribe
        client.on_publish = on_publish
        deadline = time.monotonic() + timeout
        client.connect_async(owner.mqtt_host, owner.mqtt_port, keepalive=30)
        client.loop_start()
        if not got["connect"].wait(max(0.0, deadline - time.monotonic())) or bad(state["connack"]):
            return "connect_failed"
        for topic in subscribe_topics:
            got["sub"].clear()
            client.subscribe(topic, qos=1)
            if not got["sub"].wait(max(0.0, deadline - time.monotonic())):
                return "access_failed"
            codes = state["suback"]
            if not isinstance(codes, (list, tuple)):
                codes = [codes]
            if not codes or any(bad(c) for c in codes):
                return "access_failed"
        client.publish(probe_topic, json.dumps({"probe": True}), qos=1)
        if not got["pub"].wait(max(0.0, deadline - time.monotonic())) or bad(state["puback"]):
            return "access_failed"
        return None
    except Exception as exc:
        _log(f"Login test failed to run: {type(exc).__name__}")
        return "connect_failed"
    finally:
        if client is not None:
            for step in (getattr(client, "disconnect", None), getattr(client, "loop_stop", None)):
                try:
                    if step:
                        step()
                except Exception:
                    pass


class LoginMover:
    """Handles `login/key_request` and `login/change` for one CentralCoreClient.

    `client` must offer: client_id, mqtt_username, mqtt_password, mqtt_tls, cmd_sub_topic,
    store_ack_topic, build_ack_topic(action, command_id), _publish(topic, payload, qos, persist),
    switch_login(username, password), connect_refused() and a truthy `_connected` while the
    main connection is up.
    """

    def __init__(self, client, crypto=None, store=None, probe=None, clock=time.monotonic, sleep=time.sleep,
                 start_thread=None, key_ttl=KEY_TTL_SECONDS, test_timeout=TEST_TIMEOUT_SECONDS,
                 rollback_window=ROLLBACK_WINDOW_SECONDS, max_steps=None):
        self.client = client
        self._crypto = crypto
        self.store = store or LoginStore()
        self._probe = probe or paho_probe
        self._clock = clock
        self._sleep = sleep
        self._start_thread = start_thread or self._default_start_thread
        self.key_ttl = key_ttl
        self.test_timeout = test_timeout
        self.rollback_window = rollback_window
        self.max_steps = max_steps  # None: keep trying until a login connects or the add-on stops
        self._saved = False  # the current move has saved the new login
        self._lock = threading.Lock()
        self._keys = OrderedDict()  # request id -> {"private", "created"}; a few at once
        self._used = []  # request ids already used (oldest first)
        self._busy = False

    @staticmethod
    def _default_start_thread(fn):
        threading.Thread(target=fn, name="login-move", daemon=True).start()

    @property
    def crypto(self):
        if self._crypto is None:
            self._crypto = _load_crypto()
        return self._crypto

    # -- helpers ------------------------------------------------------------
    def _publish(self, action, command_id, payload):
        try:
            topic = self.client.build_ack_topic(action, command_id)
        except Exception:
            _log(f"Not answering a login command: unusable command id ({action})")
            return
        try:
            self.client._publish(topic, json.dumps(payload), qos=1, persist=False)
        except Exception as exc:
            _log(f"Could not publish the answer to {action}: {type(exc).__name__}")

    def _fail(self, command_id, request_id, reason):
        """A failed answer sent before anything was decrypted: it carries no confirmation,
        so the vault treats it as advice only."""
        self._publish("login/change", command_id, {
            "command_id": command_id, "request_id": request_id, "status": "failed", "reason": reason,
            "username": self.client.mqtt_username or None, "timestamp": _utc_now_iso(),
        })

    def _result(self, command_id, request_id, status, reason, confirm_key):
        crypto = self.crypto
        username = self.client.mqtt_username or None
        payload = {
            "command_id": command_id, "request_id": request_id, "status": status, "reason": reason,
            "username": username, "timestamp": _utc_now_iso(),
            "confirmation": crypto.result_confirmation(
                confirm_key, self.client.client_id, request_id, status, reason, username),
        }
        self._publish("login/change", command_id, payload)

    def _burn(self, request_id):
        with self._lock:
            self._keys.pop(request_id, None)
            self._used.append(request_id)
            del self._used[:-USED_IDS_MAX]

    # -- login/key_request ----------------------------------------------
    def handle_key_request(self, command_id):
        with self._lock:
            busy = self._busy
        if busy:
            self._publish("login/key_request", command_id,
                          {"status": "failed", "result": {"reason": "busy"}, "timestamp": _utc_now_iso()})
            return
        crypto = self.crypto
        private = crypto.generate_hub_private_key()
        request_id = crypto.new_request_id()
        public = crypto.public_key_b64(private)
        now = self._clock()
        with self._lock:
            for rid in [r for r, k in self._keys.items() if now - k["created"] > self.key_ttl]:
                del self._keys[rid]
            self._keys[request_id] = {"private": private, "created": now}
            while len(self._keys) > KEYS_MAX:
                self._keys.popitem(last=False)
        expires = datetime.fromtimestamp(time.time() + self.key_ttl, timezone.utc).isoformat().replace("+00:00", "Z")
        fingerprint = crypto.key_fingerprint(public)
        _log(f"Login key {request_id} made for a login move; fingerprint {fingerprint}; "
             f"valid for {self.key_ttl // 60} minutes. Check this fingerprint matches the one the vault shows.")
        self._publish("login/key_request", command_id, {
            "command_id": command_id, "request_id": request_id, "algorithm": crypto.ALGORITHM,
            "public_key": public, "fingerprint": fingerprint, "expires_at": expires, "timestamp": _utc_now_iso(),
        })

    # -- login/change -----------------------------------------------------
    def handle_change(self, command_id, fields):
        """Check the request, then run the move on its own thread (it can take minutes).

        The one-use key is only used up once the new login has passed the test, so a forged or
        wrong message cannot burn the key the vault is about to use."""
        crypto = self.crypto
        if not isinstance(fields, dict):
            return self._fail(command_id, None, "bad_request")
        request_id = fields.get("request_id")
        eph, nonce, sealed = (_text(fields.get(k)) for k in ("ephemeral_public_key", "nonce", "ciphertext"))
        if not isinstance(request_id, str) or not crypto.is_valid_request_id(request_id):
            return self._fail(command_id, None, "bad_request")
        if eph is None or nonce is None or sealed is None:
            return self._fail(command_id, request_id, "bad_request")
        with self._lock:
            if self._busy:
                return self._fail(command_id, request_id, "busy")
            if request_id in self._used:
                return self._fail(command_id, request_id, "used")
            key = self._keys.get(request_id)
            if key is None:
                return self._fail(command_id, request_id, "unknown_request")
            if self._clock() - key["created"] > self.key_ttl:
                del self._keys[request_id]
                return self._fail(command_id, request_id, "expired")
            private = key["private"]
            self._busy = True
        launched = False
        try:
            if (getattr(self.client, "options", None) or {}).get("reset_saved_login") is True:
                # A restart would delete what this move saves and fall back to the old login.
                _log(f"Login change {request_id} refused: reset_saved_login is on in the add-on options")
                return self._fail(command_id, request_id, "save_failed")
            if not getattr(self.client, "mqtt_tls", False):
                # The login would travel in the clear on the new connection: never.
                _log(f"Login change {request_id} refused: MQTT TLS is off on this hub")
                return self._fail(command_id, request_id, "tls_required")
            try:
                login = crypto.decrypt_login_change(private, self.client.client_id, request_id, eph, nonce, sealed)
            except crypto.LoginChangeCryptoError as exc:
                _log(f"Login change {request_id} refused: {exc}")
                reason = "bad_login" if "not a login" in str(exc) else "bad_ciphertext"
                return self._fail(command_id, request_id, reason)
            if not allowed_username(self.client.client_id, login.username):
                _log(f"Login change {request_id} refused: the username is not one of this hub's own logins")
                return self._fail(command_id, request_id, "bad_login")
            self._start_thread(lambda: self._run_change(command_id, request_id, login))
            launched = True
        except Exception as exc:
            _log(f"Login change {request_id} could not start: {type(exc).__name__}")
            self._fail(command_id, request_id, "save_failed")
        finally:
            if not launched:
                with self._lock:
                    self._busy = False

    def _run_change(self, command_id, request_id, login):
        self._saved = False
        try:
            self._move(command_id, request_id, login)
        except Exception as exc:  # never leave the hub half-moved without saying so
            _log(f"Login move {request_id} stopped by an error: {type(exc).__name__}")
            if self._saved:
                # The new login is saved and the hub may be on it: the record stays, and the next
                # start settles it and reports. A "nothing was saved" answer would be untrue.
                _log(f"Login move {request_id}: the unconfirmed record is kept for the next start")
            else:
                try:
                    self._result(command_id, request_id, "failed", "save_failed", login.confirm_key)
                except Exception:
                    pass
        finally:
            with self._lock:
                self._busy = False

    def _move(self, command_id, request_id, login):
        client = self.client
        old = {"username": client.mqtt_username or "", "password": client.mqtt_password or ""}
        new = {"username": login.username, "password": login.password}
        confirm = login.confirm_key
        if hmac.compare_digest(f"{old['username']}\x00{old['password']}".encode(),
                               f"{new['username']}\x00{new['password']}".encode()):
            self._burn(request_id)
            _log(f"Login move {request_id}: the hub already uses this login")
            return self._result(command_id, request_id, "ok", "unchanged", confirm)
        _log(f"Login move {request_id}: testing the new login {login.username!r} on a second connection")
        probe_topic = f"hubs/{client.client_id}/v1/ack/login.probe/{request_id}"
        topics = [t for t in (getattr(client, "cmd_sub_topic", None), getattr(client, "store_ack_topic", None)) if t]
        failure = self._probe(client, login.username, login.password, probe_topic, topics, self.test_timeout)
        if failure:
            _log(f"Login move {request_id}: the new login did not pass the test ({failure}); keeping the old login")
            return self._result(command_id, request_id, "failed", failure, confirm)
        self._burn(request_id)
        pending = {
            "command_id": command_id, "request_id": request_id, "new": new, "previous": old,
            "confirm_key": base64.b64encode(confirm).decode("ascii"), "started": time.time(),
        }
        try:
            self.store.write_pending(pending)
            self.store.save(new["username"], new["password"])
        except LoginSaveError as exc:
            self.store.clear_pending()
            _log(f"Login move {request_id}: could not save the new login ({exc}); keeping the old login")
            return self._result(command_id, request_id, "failed", "save_failed", confirm)
        self._saved = True
        _log(f"Login move {request_id}: new login saved; switching the main connection")
        self._try_switch(new)
        self._settle(pending)

    # -- switching and settling ----------------------------------------------
    def _try_switch(self, login):
        try:
            self.client.switch_login(login["username"], login["password"])
            return True
        except Exception as exc:
            _log(f"Switching the main connection failed: {type(exc).__name__}")
            return False

    def _commit(self, login, previous):
        """Make `login` the one used after a restart, before trying it. False if that failed."""
        try:
            if previous:
                self.store.restore(login["username"], login["password"])
            else:
                self.store.save(login["username"], login["password"])
            return True
        except Exception as exc:
            _log(f"Could not save the login before trying it ({type(exc).__name__}); trying it anyway")
            return False

    def _wait_connected(self, window):
        deadline = self._clock() + window
        while self._clock() < deadline:
            if self.client._connected:
                return True
            if self.client.connect_refused():
                return False
            self._sleep(0.5)
        return bool(self.client._connected)

    def _stopped(self):
        stop = getattr(self.client, "_stop_event", None)
        return bool(stop is not None and stop.is_set())

    def _on(self, login):
        return ((self.client.mqtt_username or ""), (self.client.mqtt_password or "")) == (
            login["username"], login["password"])

    def _settle(self, pending):
        """After a switch (or at start-up): keep the new login if it connects, else go back,
        and keep alternating between the two until one connects. The pending record stays
        until one does, and also if a login could not be saved before it was tried."""
        new, prev = pending["new"], pending["previous"]
        command_id, request_id = pending["command_id"], pending["request_id"]
        confirm = base64.b64decode(pending["confirm_key"])
        dirty = False  # the saved login is not the one the hub is on
        # The login the hub is on first, then the other two logins in turn, over and over.
        order = [prev, new] if self._on(new) else [new, prev]
        login, step, connected = None, 0, False
        while True:
            started = self._clock()
            if login is not None:
                _log(f"Login move {request_id}: the main connection did not come up; trying the "
                     f"{'old' if login is prev else 'new'} login")
                dirty = not self._commit(login, previous=login is prev)
                self._try_switch(login)
            if self._wait_connected(self.rollback_window):
                connected = True
                break
            step += 1
            if self._stopped() or (self.max_steps is not None and step >= self.max_steps):
                break
            # a refusal comes at once: do not burn through the logins in seconds
            pause = min(MIN_STEP_SECONDS * (2 ** (step // 2)), MAX_BACKOFF_SECONDS) - (self._clock() - started)
            if pause > 0:
                self._sleep(pause)
            login = order[(step - 1) % 2]
        if not connected:
            _log(f"Login move {request_id}: no login connected; the unconfirmed record is kept for the next start")
            return
        if dirty:
            _log(f"Login move {request_id}: connected, but the login could not be saved; "
                 "the unconfirmed record is kept for the next start")
            return
        if self._on(new):
            self.store.clear_pending()
            _log(f"Login move {request_id}: the main connection is up on the new login")
            self._result(command_id, request_id, "ok", None, confirm)
        elif self._on(prev):
            self.store.clear_pending()
            _log(f"Login move {request_id}: the main connection is up on the old login")
            self._result(command_id, request_id, "failed", "rolled_back", confirm)
        else:
            _log(f"Login move {request_id}: connected on a login that is neither the old nor the new one; "
                 "the unconfirmed record is kept")

    # -- start-up -------------------------------------------------------------
    def settle_pending_at_start(self):
        """If the last run died between saving a new login and confirming it, finish the job
        on its own thread: keep whichever login connects."""
        pending = self.store.read_pending()
        if not pending:
            return False
        _log(f"An unconfirmed login move ({pending.get('request_id')}) was found; checking which login connects")
        with self._lock:
            self._busy = True

        def run():
            try:
                self._settle(pending)
            except Exception as exc:
                _log(f"Settling the unconfirmed login move failed: {type(exc).__name__}")
            finally:
                with self._lock:
                    self._busy = False

        try:
            self._start_thread(run)
        except Exception:
            with self._lock:
                self._busy = False
            raise
        return True
