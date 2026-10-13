"""Moving the hub onto a new broker login, sent by the vault (login_move.py).

The conftest swaps the shared protocol package for a stand-in, so the real
crypto module is loaded here by hand. The vault's half is played with the
real `encrypt_login_change`. Logins in these tests are made up.
"""

import base64
import importlib
import importlib.util
import io
import pathlib
import json
import sys
import types
import uuid
from contextlib import redirect_stderr, redirect_stdout

import pytest

import login_move as lm

HUB = "demo-home-001"
def _fresh(prefix):
    """A made-up value that differs on every run, so no literal password sits in the file."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


OLD_USER, NEW_USER = "hub-shared", "hub-demo-home-001"
OLD_PW, NEW_PW = _fresh("old"), _fresh("new")
OTHER_PW, OWNER_PW, HA_TOKEN = _fresh("other"), _fresh("owner"), _fresh("token")


@pytest.fixture(scope="module")
def crypto():
    saved = {k: v for k, v in sys.modules.items() if k == "central_core_mqtt_shared" or k.startswith("central_core_mqtt_shared.")}
    for k in saved:
        del sys.modules[k]
    try:
        mod = importlib.import_module("central_core_mqtt_shared.login_change")
    finally:
        for k in [k for k in sys.modules if k == "central_core_mqtt_shared" or k.startswith("central_core_mqtt_shared.")]:
            del sys.modules[k]
        sys.modules.update(saved)
    return mod


def _load_handlers():
    src = pathlib.Path(__file__).parents[2] / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers_under_test", str(src))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeClient:
    """Just what LoginMover uses of CentralCoreClient."""

    def __init__(self, good_logins=()):
        self.client_id = HUB
        self.mqtt_username, self.mqtt_password = OLD_USER, OLD_PW
        self.mqtt_tls = True
        self.options = {}
        self.cmd_sub_topic = f"hubs/{HUB}/v1/cmd/+/+"
        self.store_ack_topic = f"hubs/{HUB}/v1/ack"
        self._connected = True
        self.published = []
        self.switches = []
        self.good = set(good_logins) | {(OLD_USER, OLD_PW)}
        self.refused = False
        self.switch_error = None

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"

    def _publish(self, topic, payload, qos=0, persist=None):
        self.published.append((topic, json.loads(payload)))

    def switch_login(self, username, password):
        self.switches.append((username, password))
        self.mqtt_username, self.mqtt_password = username, password
        if self.switch_error:
            raise self.switch_error
        ok = (username, password) in self.good
        self._connected = ok
        self.refused = not ok

    def connect_refused(self):
        return self.refused

    def results(self, name="login.change"):
        return [p for t, p in self.published if f"/ack/{name}/" in t]


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def env(tmp_path, crypto):
    (tmp_path / "options.json").write_text(json.dumps({
        "mqtt_host": "broker.example", "mqtt_username": OLD_USER, "mqtt_password": OLD_PW, "client_id": HUB,
        "ha_api_token": HA_TOKEN,
    }))

    class Env:
        pass

    e = Env()
    e.crypto = crypto
    e.dir = tmp_path
    e.client = FakeClient(good_logins={(NEW_USER, NEW_PW)})
    e.clock = Clock()
    e.store = lm.LoginStore(data_dir=tmp_path)
    e.probe_result = None
    e.probes = []

    def probe(owner, username, password, probe_topic, topics, timeout):
        e.probes.append((username, probe_topic, tuple(topics), timeout))
        return e.probe_result

    e.mover = lm.LoginMover(e.client, crypto=crypto, store=e.store, probe=probe, clock=e.clock, sleep=e.clock.sleep,
                            start_thread=lambda fn: fn(), max_steps=6)

    def key(command_id="k1"):
        e.mover.handle_key_request(command_id)
        return e.client.results("login.key_request")[-1]

    def change(k, username=NEW_USER, password=NEW_PW, command_id="c1", hub_id=HUB, request_id=None, **over):
        request_id = request_id or k["request_id"]
        fields, confirm = crypto.encrypt_login_change(k["public_key"], hub_id, request_id, username, password)
        e.confirm = confirm
        fields = {"request_id": request_id, **fields, **over}
        e.mover.handle_change(command_id, fields)
        return fields

    def last():
        return e.client.results()[-1]

    def options():
        return json.loads((tmp_path / "options.json").read_text())

    e.key, e.change, e.last, e.options = key, change, last, options
    return e


def _good(env, result):
    assert env.crypto.verify_result_confirmation(
        env.confirm, HUB, result["request_id"], result["status"], result["reason"], result["username"],
        result["confirmation"])


# -- the happy path ----------------------------------------------------------


def test_key_request_publishes_a_one_use_public_key(env):
    k = env.key()
    assert env.client.published[0][0] == f"hubs/{HUB}/v1/ack/login.key_request/k1"
    assert k["algorithm"] == env.crypto.ALGORITHM and k["command_id"] == "k1"
    assert env.crypto.is_valid_request_id(k["request_id"])
    assert k["fingerprint"] == env.crypto.key_fingerprint(k["public_key"])
    assert k["expires_at"].endswith("Z")


def test_a_good_login_is_tested_saved_switched_and_confirmed(env):
    env.change(env.key())
    result = env.last()
    assert (result["status"], result["reason"], result["username"]) == ("ok", None, NEW_USER)
    _good(env, result)
    assert env.client.switches == [(NEW_USER, NEW_PW)]
    user, probe_topic, topics, timeout = env.probes[0]
    assert user == NEW_USER and probe_topic.startswith(f"hubs/{HUB}/v1/ack/login.probe/")
    assert env.client.cmd_sub_topic in topics and env.client.store_ack_topic in topics
    assert not (env.dir / lm.PENDING_NAME).exists()
    saved = json.loads((env.dir / lm.OVERRIDE_NAME).read_text())
    assert saved == {"username": NEW_USER, "password": NEW_PW}


def test_the_saved_files_are_private_and_the_options_are_left_alone(env):
    before = env.options()
    env.change(env.key())
    assert (env.dir / lm.OVERRIDE_NAME).stat().st_mode & 0o077 == 0
    assert env.options() == before


@pytest.mark.parametrize("slot", ["", "-a", "-b"])
def test_the_hubs_own_login_names_are_accepted(env, slot):
    env.client.good.add((NEW_USER + slot, NEW_PW))
    env.change(env.key(), username=NEW_USER + slot)
    assert env.last()["status"] == "ok"


@pytest.mark.parametrize("username", ["hub-shared", "hub-demo-home-002", "hub-demo-home-001-c", "demo-home-001",
                                      "hub-demo-home-001-a-a", "admin"])
def test_any_other_login_is_refused_and_the_key_survives(env, username):
    k = env.key()
    env.change(k, username=username)
    assert env.last()["reason"] == "bad_login" and "confirmation" not in env.last()
    assert not env.probes and not env.client.switches
    env.change(k, command_id="c2")
    assert env.last()["status"] == "ok"


def test_same_login_changes_nothing(env):
    env.client.mqtt_username = NEW_USER
    env.client.mqtt_password = NEW_PW
    env.change(env.key())
    result = env.last()
    assert (result["status"], result["reason"]) == ("ok", "unchanged")
    _good(env, result)
    assert not env.probes and not env.client.switches and not (env.dir / lm.OVERRIDE_NAME).exists()


def test_the_vault_can_send_the_fields_inside_a_payload_object(env):
    k = env.key()
    fields, env.confirm = env.crypto.encrypt_login_change(k["public_key"], HUB, k["request_id"], NEW_USER, NEW_PW)
    handlers = _load_handlers()
    cmd = {"command_id": "c9", "timestamp": lm._utc_now_iso(), "payload": {"request_id": k["request_id"], **fields}}
    c = env.client
    c.login_mover = lambda: env.mover
    handlers._handle_login(c, json.dumps(cmd), "change")
    assert env.last()["status"] == "ok"


def test_an_unencrypted_connection_never_gets_a_password(env):
    env.client.mqtt_tls = False
    k = env.key()
    env.change(k)
    assert env.last()["reason"] == "tls_required" and not env.probes and not env.client.switches
    env.client.mqtt_tls = True
    env.change(k, command_id="c2")
    assert env.last()["status"] == "ok"


# -- refusals before anything is decrypted ---------------------------------------


def test_no_key_made_yet(env):
    k = {"public_key": env.crypto.public_key_b64(env.crypto.generate_hub_private_key())}
    env.change(k, request_id="req_0123456789abcdef")
    assert env.last()["reason"] == "unknown_request" and "confirmation" not in env.last()


def test_wrong_request_id(env):
    k = env.key()
    env.change(k, request_id="req_other_0123456789")
    assert env.last()["reason"] == "unknown_request"
    assert not env.client.switches


def test_a_request_id_cannot_be_used_twice(env):
    k = env.key()
    env.change(k)
    assert env.last()["status"] == "ok"
    env.change(k, command_id="c2")
    assert env.last()["reason"] == "used"
    assert env.client.switches == [(NEW_USER, NEW_PW)]


def test_the_key_expires(env):
    k = env.key()
    env.clock.now += lm.KEY_TTL_SECONDS + 1
    env.change(k)
    assert env.last()["reason"] == "expired"
    env.change(k, command_id="c2")
    assert env.last()["reason"] == "unknown_request"


def test_a_new_key_request_does_not_cancel_the_earlier_key(env):
    first = env.key("k1")
    second = env.key("k2")
    env.change(first)
    assert env.last()["status"] == "ok"
    env.change(second, command_id="c2")
    assert env.last()["status"] == "ok"


def test_only_a_few_keys_are_kept(env):
    keys = [env.key(f"k{i}") for i in range(lm.KEYS_MAX + 1)]
    env.change(keys[0])
    assert env.last()["reason"] == "unknown_request"
    env.change(keys[-1], command_id="c2")
    assert env.last()["status"] == "ok"


def test_expired_keys_are_dropped_when_a_new_one_is_made(env):
    old = env.key("k1")
    env.clock.now += lm.KEY_TTL_SECONDS + 1
    env.key("k2")
    assert old["request_id"] not in env.mover._keys


@pytest.mark.parametrize("fields", [None, "text", [], {}, {"request_id": "short"}])
def test_malformed_commands(env, fields):
    env.key()
    env.mover.handle_change("c1", fields)
    assert env.last()["reason"] == "bad_request"


def test_missing_or_oversized_fields_are_bad_requests(env):
    k = env.key()
    env.change(k, ciphertext="")
    assert env.last()["reason"] == "bad_request"
    env.change(k, nonce="A" * (lm.MAX_FIELD_CHARS + 1), command_id="c2")
    assert env.last()["reason"] == "bad_request"
    env.change(k, ciphertext=5, command_id="c3")
    assert env.last()["reason"] == "bad_request"
    assert not env.client.switches


def test_a_message_made_for_another_hub_does_not_decrypt_and_does_not_burn_the_key(env):
    k = env.key()
    env.change(k, hub_id="demo-home-002")
    assert env.last()["reason"] == "bad_ciphertext" and "confirmation" not in env.last()
    assert not env.probes and not env.client.switches
    env.change(k, command_id="c2")  # the real message still works
    assert env.last()["status"] == "ok"


def test_garbage_ciphertext_is_refused(env):
    k = env.key()
    env.change(k, ciphertext=base64.b64encode(b"x" * 40).decode())
    assert env.last()["reason"] == "bad_ciphertext"


def test_a_login_with_a_bad_shape_is_refused(env, monkeypatch):
    k = env.key()
    with monkeypatch.context() as m:  # only so the vault side will make such a message
        m.setattr(env.crypto, "is_valid_username", lambda u: True)
        fields, _ = env.crypto.encrypt_login_change(
            k["public_key"], HUB, k["request_id"], "evil\nINFO fake line", NEW_PW)
    env.mover.handle_change("c1", {"request_id": k["request_id"], **fields})
    assert env.last()["reason"] == "bad_login" and "evil" not in json.dumps(env.last())
    assert not env.client.switches


# -- the test connection ----------------------------------------------------------


@pytest.mark.parametrize("failure", ["connect_failed", "access_failed"])
def test_a_login_that_fails_the_test_keeps_the_old_one_and_the_key(env, failure):
    env.probe_result = failure
    k = env.key()
    env.change(k)
    result = env.last()
    assert (result["status"], result["reason"], result["username"]) == ("failed", failure, OLD_USER)
    _good(env, result)
    assert not env.client.switches
    assert not (env.dir / lm.OVERRIDE_NAME).exists() and not (env.dir / lm.PENDING_NAME).exists()
    assert env.client.mqtt_username == OLD_USER
    env.probe_result = None  # the vault fixes the login and tries the same key again
    env.change(k, command_id="c2")
    assert env.last()["status"] == "ok"


# -- switching and rolling back ----------------------------------------------------


def test_a_main_connection_that_fails_after_switching_rolls_back(env):
    env.client.good.discard((NEW_USER, NEW_PW))  # passes the test, then fails for real
    env.change(env.key())
    result = env.last()
    assert (result["status"], result["reason"], result["username"]) == ("failed", "rolled_back", OLD_USER)
    _good(env, result)
    assert env.client.switches == [(NEW_USER, NEW_PW), (OLD_USER, OLD_PW)]
    assert not (env.dir / lm.OVERRIDE_NAME).exists()  # options.json already has the old login
    assert not (env.dir / lm.PENDING_NAME).exists()
    assert env.store.effective(env.options()) == (OLD_USER, OLD_PW, "options")


def test_a_refused_connection_rolls_back_at_once_without_waiting_the_whole_window(env):
    env.client.good.discard((NEW_USER, NEW_PW))
    start = env.clock.now
    env.change(env.key())
    assert env.last()["reason"] == "rolled_back"
    assert env.clock.now - start < lm.ROLLBACK_WINDOW_SECONDS


def test_with_no_refusal_the_whole_window_is_waited(env):
    env.client.good.discard((NEW_USER, NEW_PW))
    env.client.connect_refused = lambda: False
    start = env.clock.now
    env.change(env.key())
    assert env.clock.now - start >= lm.ROLLBACK_WINDOW_SECONDS
    assert env.last()["reason"] == "rolled_back"


def test_rollback_to_a_login_that_was_not_the_one_in_options(env):
    (env.dir / lm.OVERRIDE_NAME).write_text(json.dumps({"username": OLD_USER, "password": OLD_PW}))  # ggignore
    opts = env.options()
    opts["mqtt_username"], opts["mqtt_password"] = "x", "y"
    (env.dir / "options.json").write_text(json.dumps(opts))
    env.client.good.discard((NEW_USER, NEW_PW))
    env.change(env.key())
    assert env.last()["reason"] == "rolled_back"
    assert json.loads((env.dir / lm.OVERRIDE_NAME).read_text()) == {"username": OLD_USER, "password": OLD_PW}


def test_when_the_old_login_no_longer_works_either_the_new_one_is_tried_again(env):
    env.client.good = {(NEW_USER, NEW_PW)}
    original = env.client.switch_login
    calls = []

    def flaky(u, p):
        calls.append((u, p))
        original(u, p)
        if len(calls) == 1:  # the first connect on the new login is refused
            env.client._connected, env.client.refused = False, True

    env.client.switch_login = flaky
    env.change(env.key())
    result = env.last()
    assert calls == [(NEW_USER, NEW_PW), (OLD_USER, OLD_PW), (NEW_USER, NEW_PW)]
    assert (result["status"], result["username"]) == ("ok", NEW_USER)
    assert json.loads((env.dir / lm.OVERRIDE_NAME).read_text())["username"] == NEW_USER
    assert not (env.dir / lm.PENDING_NAME).exists()


def test_when_nothing_connects_the_record_is_kept_and_no_false_report_is_sent(env):
    env.client.good = set()
    start = env.clock.now
    env.change(env.key())
    assert env.client.results()[-1:] == [] or env.client.results()[-1].get("status") != "ok"
    assert (env.dir / lm.PENDING_NAME).exists()
    assert env.mover._busy is False
    assert [u for u, _ in env.client.switches] == [NEW_USER, OLD_USER, NEW_USER, OLD_USER, NEW_USER, OLD_USER]
    assert env.clock.now - start >= 2 * lm.MIN_STEP_SECONDS  # refusals that come at once are not rushed through


def test_it_keeps_alternating_until_the_add_on_stops(env):
    env.client.good = set()
    env.mover.max_steps = None
    env.client._stop_event = types.SimpleNamespace(is_set=lambda: len(env.client.switches) >= 3)
    env.change(env.key())
    assert len(env.client.switches) == 3 and (env.dir / lm.PENDING_NAME).exists()


def test_a_login_that_comes_back_later_is_found_and_reported(env):
    env.client.good = {(OLD_USER, OLD_PW)}  # the new login is refused at first
    original = env.client.switch_login

    def switch(u, p):
        original(u, p)
        if len(env.client.switches) >= 3:  # the broker accepts the new login by now
            env.client.good.add((NEW_USER, NEW_PW))
            env.client._connected, env.client.refused = (u, p) in env.client.good, (u, p) not in env.client.good

    env.client.switch_login = switch
    env.client.good.discard((NEW_USER, NEW_PW))
    env.change(env.key())
    assert env.last()["status"] in ("ok", "failed")
    assert not (env.dir / lm.PENDING_NAME).exists()


def test_a_switch_that_raises_goes_through_the_same_rollback(env):
    env.client.switch_error = RuntimeError("no thread")
    env.change(env.key())
    assert env.client.switches[0] == (NEW_USER, NEW_PW)
    assert env.client.switches[-1] in [(NEW_USER, NEW_PW), (OLD_USER, OLD_PW)]


def test_rollback_that_cannot_save_still_switches_back_but_does_not_report(env, monkeypatch):
    env.client.good.discard((NEW_USER, NEW_PW))
    calls = []

    def broken(username, password):
        calls.append(username)
        raise PermissionError("denied")

    monkeypatch.setattr(env.store, "restore", broken)
    env.change(env.key())
    assert env.client.switches[1] == (OLD_USER, OLD_PW) and calls
    # the saved login is still the new one: no signed word, the record stays for the next start
    assert not env.client.results() or env.client.results()[-1].get("reason") != "rolled_back"
    assert (env.dir / lm.PENDING_NAME).exists()


def test_a_new_login_that_cannot_be_saved_after_a_rollback_is_not_reported_ok(env, monkeypatch):
    # both refused at first, then the new one is fine; but it cannot be saved again when it is retried
    env.client.good = set()
    original = env.client.switch_login
    seen = []

    def switch(u, p):
        seen.append(u)
        original(u, p)
        if len(seen) == 2:
            env.client.good.add((NEW_USER, NEW_PW))

    env.client.switch_login = switch
    real_save = env.store.save
    saves = []

    def save(u, p):
        saves.append(u)
        if len(saves) >= 2:
            raise lm.LoginSaveError("full")
        return real_save(u, p)

    monkeypatch.setattr(env.store, "save", save)
    env.change(env.key())
    assert not [r for r in env.client.results() if r.get("status") == "ok"]
    assert (env.dir / lm.PENDING_NAME).exists()


def test_connected_on_a_login_that_is_neither_is_not_reported(env):
    env.client.mqtt_username, env.client.mqtt_password = "hub-other", OTHER_PW  # ggignore
    env.client._connected = True
    env.store.write_pending(_pending())
    env.mover.settle_pending_at_start()
    assert not env.client.results() and (env.dir / lm.PENDING_NAME).exists()


def test_nothing_is_switched_if_the_login_cannot_be_saved(env, monkeypatch):
    def broken(username, password):
        raise lm.LoginSaveError("disk full")

    monkeypatch.setattr(env.store, "save", broken)
    env.change(env.key())
    result = env.last()
    assert (result["status"], result["reason"], result["username"]) == ("failed", "save_failed", OLD_USER)
    _good(env, result)
    assert not env.client.switches and not (env.dir / lm.PENDING_NAME).exists()


def test_an_error_before_anything_is_saved_is_reported_and_the_mover_is_free_again(env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret " + NEW_PW)

    monkeypatch.setattr(env.mover, "_probe", boom)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        env.change(env.key())
    assert env.last()["reason"] == "save_failed" and env.last()["username"] == OLD_USER
    assert NEW_PW not in out.getvalue() + err.getvalue()
    assert env.mover._busy is False


def test_an_error_after_the_login_was_saved_sends_no_untrue_report(env, monkeypatch):
    monkeypatch.setattr(env.mover, "_settle", lambda p: (_ for _ in ()).throw(RuntimeError("EIO")))
    env.change(env.key())
    assert not env.client.results()  # nothing claims "nothing was saved"
    assert (env.dir / lm.PENDING_NAME).exists() and env.mover._busy is False


def test_no_move_while_reset_saved_login_is_on(env):
    env.client.options = {"reset_saved_login": True}
    k = env.key()
    env.change(k)
    assert env.last()["reason"] == "save_failed" and not env.probes and not env.client.switches
    env.client.options = {"reset_saved_login": False}
    env.change(k, command_id="c2")
    assert env.last()["status"] == "ok"


def test_only_one_move_at_a_time(env):
    k = env.key()
    env.mover._busy = True
    env.change(k)
    assert env.last()["reason"] == "busy"
    env.mover.handle_key_request("k2")
    answer = env.client.results("login.key_request")[-1]
    assert answer["status"] == "failed" and answer["result"] == {"reason": "busy"}


def test_busy_set_between_the_check_and_the_decrypt(env, monkeypatch):
    k = env.key()
    real = env.crypto.decrypt_login_change

    def sneaky(*a, **kw):
        assert env.mover._busy is True  # claimed under the lock before the slow part
        return real(*a, **kw)

    monkeypatch.setattr(env.crypto, "decrypt_login_change", sneaky)
    env.change(k)
    assert env.last()["status"] == "ok"


def test_a_thread_that_cannot_start_frees_the_mover(env):
    def no_thread(fn):
        raise RuntimeError("no threads")

    env.mover._start_thread = no_thread
    env.change(env.key())
    assert env.last()["reason"] == "save_failed" and env.mover._busy is False


# -- restarts --------------------------------------------------------------------------


def test_a_restart_picks_up_the_saved_login(env):
    env.change(env.key())
    options = env.options()
    merged, source = lm.apply_saved_login(options, store=env.store)
    assert (merged["mqtt_username"], merged["mqtt_password"], source) == (NEW_USER, NEW_PW, "override")
    assert merged["ha_api_token"] == HA_TOKEN and options["mqtt_username"] == OLD_USER


def test_the_saved_login_wins_even_if_the_options_login_changes(env):
    env.change(env.key())
    options = env.options()
    options["mqtt_username"], options["mqtt_password"] = "typed-by-owner", OWNER_PW
    assert lm.apply_saved_login(options, store=env.store)[1] == "override"


def test_reset_saved_login_in_the_options_throws_the_saved_login_away(env, capsys):
    env.change(env.key())
    options = {**env.options(), "reset_saved_login": True}
    merged, source = lm.apply_saved_login(options, store=env.store)
    assert source == "options" and merged["mqtt_username"] == OLD_USER
    assert not (env.dir / lm.OVERRIDE_NAME).exists() and not (env.dir / lm.PENDING_NAME).exists()
    assert "reset_saved_login is on" in capsys.readouterr().out


def test_with_no_move_the_options_are_used_unchanged(env):
    options = env.options()
    merged, source = lm.apply_saved_login(options, store=env.store)
    assert merged is options and source == "options"
    assert not (env.dir / lm.OVERRIDE_NAME).exists() and not (env.dir / lm.PENDING_NAME).exists()
    assert not hasattr(env.client, "_login_mover")


def test_apply_saved_login_makes_its_own_store_from_a_directory(env):
    options = env.options()
    assert lm.apply_saved_login(options, data_dir=env.dir) == (options, "options")


@pytest.mark.parametrize("content", ["not json", "[]", json.dumps({"username": "", "password": "x"}),
                                     json.dumps({"username": "u", "password": 5})])
def test_a_broken_override_file_is_ignored(env, content):
    (env.dir / lm.OVERRIDE_NAME).write_text(content)
    options = env.options()
    assert lm.apply_saved_login(options, store=env.store) == (options, "options")


def _pending(request_id="req_0123456789abcdef"):
    return {
        "command_id": "c1", "request_id": request_id,
        "new": {"username": NEW_USER, "password": NEW_PW},
        "previous": {"username": OLD_USER, "password": OLD_PW},
        "confirm_key": base64.b64encode(b"k" * 32).decode(), "started": 1.0}


def test_a_move_that_died_after_saving_is_undone_at_start_if_the_new_login_fails(env):
    # the process died after saving the new login; the hub starts on it and it is refused
    env.client.good.discard((NEW_USER, NEW_PW))
    env.client.mqtt_username, env.client.mqtt_password = NEW_USER, NEW_PW
    env.client._connected, env.client.refused = False, True
    env.store.write_pending(_pending())
    env.store.save(NEW_USER, NEW_PW)
    assert env.mover.settle_pending_at_start() is True
    assert env.client.switches == [(OLD_USER, OLD_PW)]
    assert not (env.dir / lm.PENDING_NAME).exists() and not (env.dir / lm.OVERRIDE_NAME).exists()
    result = env.last()
    assert (result["status"], result["reason"], result["username"]) == ("failed", "rolled_back", OLD_USER)
    assert env.mover._busy is False


def test_a_move_that_died_after_saving_is_kept_at_start_if_the_new_login_connects(env):
    env.client.mqtt_username, env.client.mqtt_password = NEW_USER, NEW_PW
    env.client._connected = True
    env.store.write_pending(_pending())
    assert env.mover.settle_pending_at_start() is True
    assert not env.client.switches and not (env.dir / lm.PENDING_NAME).exists()
    assert env.last()["status"] == "ok" and env.last()["username"] == NEW_USER


def test_a_move_that_died_before_saving_is_not_reported_as_ok(env):
    # the pending record exists but the hub is on the old login (the override was never written)
    env.client._connected = True
    env.store.write_pending(_pending())
    env.mover.settle_pending_at_start()
    result = env.last()
    assert (result["status"], result["reason"], result["username"]) == ("failed", "rolled_back", OLD_USER)
    assert not env.client.switches and not (env.dir / lm.PENDING_NAME).exists()


def test_on_the_old_login_that_does_not_connect_the_new_one_is_tried(env):
    env.client.good = {(NEW_USER, NEW_PW)}
    env.client._connected, env.client.refused = False, True
    env.store.write_pending(_pending())
    env.mover.settle_pending_at_start()
    assert env.client.switches == [(NEW_USER, NEW_PW)]
    assert env.last()["status"] == "ok"
    assert json.loads((env.dir / lm.OVERRIDE_NAME).read_text())["username"] == NEW_USER


def test_start_up_with_nothing_pending_does_nothing(env):
    assert env.mover.settle_pending_at_start() is False
    assert not env.client.published


def test_a_start_up_check_that_errors_frees_the_mover(env, monkeypatch):
    env.store.write_pending(_pending())
    monkeypatch.setattr(env.mover, "_settle", lambda p: (_ for _ in ()).throw(RuntimeError("x")))
    env.mover.settle_pending_at_start()
    assert env.mover._busy is False


def test_a_thread_that_cannot_start_at_start_up_frees_the_mover(env):
    env.store.write_pending(_pending())

    def no_thread(fn):
        raise RuntimeError("no threads")

    env.mover._start_thread = no_thread
    with pytest.raises(RuntimeError):
        env.mover.settle_pending_at_start()
    assert env.mover._busy is False


@pytest.mark.parametrize("record", [
    "junk", "[]", json.dumps({"previous": 5}),
    json.dumps({"previous": {"username": "a", "password": 3}, "new": {"username": "a", "password": "b"}}),
    json.dumps({**_pending(), "command_id": 5}),
    json.dumps({**_pending(), "confirm_key": "***"}),
    json.dumps({**_pending(), "confirm_key": None}),
    json.dumps({**_pending(), "confirm_key": base64.b64encode(b"short").decode()}),
    json.dumps({"command_id": "c", "request_id": "r", "confirm_key": "", "previous": {"username": "a", "password": "b"},
                "new": 5}),
])
def test_a_broken_pending_record_is_ignored(env, record):
    (env.dir / lm.PENDING_NAME).write_text(record)
    assert env.store.read_pending() is None


# -- the files --------------------------------------------------------------------------------


def test_restore_removes_the_override_when_options_hold_that_login(env):
    env.store.save(NEW_USER, NEW_PW)
    env.store.restore(OLD_USER, OLD_PW)
    assert not (env.dir / lm.OVERRIDE_NAME).exists()


def test_restore_writes_the_login_when_options_do_not_hold_it(env):
    env.store.restore("someone", OTHER_PW)
    assert json.loads((env.dir / lm.OVERRIDE_NAME).read_text()) == {"username": "someone", "password": OTHER_PW}


def test_restore_reports_a_file_it_cannot_remove(env, monkeypatch):
    monkeypatch.setattr(lm, "_remove", lambda p: (_ for _ in ()).throw(PermissionError("denied")))
    with pytest.raises(lm.LoginSaveError) as exc:
        env.store.restore(OLD_USER, OLD_PW)
    assert OLD_PW not in str(exc.value)


def test_the_files_cannot_be_written(env, monkeypatch):
    monkeypatch.setattr(lm, "_write_private", lambda *a: (_ for _ in ()).throw(OSError("read-only")))
    with pytest.raises(lm.LoginSaveError) as exc:
        env.store.save(NEW_USER, NEW_PW)
    assert NEW_PW not in str(exc.value)
    with pytest.raises(lm.LoginSaveError):
        env.store.write_pending({"x": 1})


def test_write_private_cleans_up(tmp_path, monkeypatch):
    monkeypatch.setattr(lm.json, "dump", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(ValueError):
        lm._write_private(tmp_path / "x.json", {})
    assert list(tmp_path.iterdir()) == []


def test_write_private_survives_a_failed_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(lm.json, "dump", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad")))
    real = lm.os.unlink
    calls = []

    def unlink(p):
        calls.append(p)
        if len(calls) > 1:
            raise OSError("gone")
        return real(p)

    monkeypatch.setattr(lm.os, "unlink", unlink)
    with pytest.raises(ValueError):
        lm._write_private(tmp_path / "x.json", {})


def test_write_private_replaces_a_stale_temp_file_with_a_private_one(tmp_path):
    stale = tmp_path / "x.json.tmp"
    stale.write_text("old")
    stale.chmod(0o666)
    lm._write_private(tmp_path / "x.json", {"a": 1})
    assert json.loads((tmp_path / "x.json").read_text()) == {"a": 1}
    assert (tmp_path / "x.json").stat().st_mode & 0o077 == 0 and not stale.exists()


def test_write_private_does_not_follow_a_planted_link(tmp_path):
    target = tmp_path / "elsewhere"
    target.write_text("keep")
    (tmp_path / "x.json.tmp").symlink_to(target)
    lm._write_private(tmp_path / "x.json", {"a": 1})
    assert target.read_text() == "keep"


def test_write_private_tolerates_a_directory_that_cannot_be_flushed(tmp_path, monkeypatch):
    real = lm.os.open

    def opener(path, flags, *a):
        if flags == lm.os.O_RDONLY:
            raise OSError("no")
        return real(path, flags, *a)

    monkeypatch.setattr(lm.os, "open", opener)
    lm._write_private(tmp_path / "x.json", {"a": 1})
    assert (tmp_path / "x.json").exists()


def test_remove_ignores_a_missing_file(tmp_path):
    lm._remove(tmp_path / "nothing")


# -- nothing secret in logs or results ------------------------------------------------------------


def test_the_password_never_appears_in_logs_or_results(env):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        env.change(env.key())
        env.client.good.discard((NEW_USER, NEW_PW + "x"))
        env.client.good.discard((NEW_USER, NEW_PW))
        env.change(env.key("k2"), command_id="c2", username=NEW_USER + "-a", password=NEW_PW + "x")
    everything = out.getvalue() + err.getvalue() + json.dumps(env.client.published)
    assert NEW_PW not in everything and OLD_PW not in everything
    assert NEW_PW not in repr(env.mover.__dict__)


def test_a_failed_decrypt_does_not_put_the_login_in_the_log(env):
    k = env.key()
    out = io.StringIO()
    with redirect_stdout(out):
        env.change(k, hub_id="demo-home-002")
    assert NEW_PW not in out.getvalue() and "refused" in out.getvalue()


def test_the_result_has_no_password_field(env):
    env.change(env.key())
    assert not [k for k in env.last() if "pass" in k.lower()]


# -- the paho test connection ---------------------------------------------------------------------


class RC:
    def __init__(self, bad=False):
        self.is_failure = bad


class FakePaho:
    """A scripted stand-in for paho.mqtt.client."""

    MQTTv5 = 5
    CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)
    script = {}
    last = None

    class Client:
        def __init__(self, **kw):
            FakePaho.last = self
            self.kw = kw
            self.subscribed, self.published, self.closed = [], [], []
            self.tls = None

        def username_pw_set(self, u, p):
            self.creds = (u, p)

        def tls_set(self, **kw):
            self.tls = kw

        def connect_async(self, host, port, keepalive=0):
            self.addr = (host, port)

        def loop_start(self):
            s = FakePaho.script
            if s.get("raise"):
                raise OSError("no route")
            if "connack" in s:
                self.on_connect(self, None, {}, s["connack"], None)

        def subscribe(self, topic, qos=0):
            self.subscribed.append(topic)
            if "suback" in FakePaho.script:
                self.on_subscribe(self, None, 1, FakePaho.script["suback"], None)

        def publish(self, topic, payload, qos=0):
            self.published.append((topic, payload))
            if "puback" in FakePaho.script:
                self.on_publish(self, None, 2, FakePaho.script["puback"], None)

        def disconnect(self):
            self.closed.append("disconnect")

        def loop_stop(self):
            self.closed.append("loop_stop")


class Owner:
    client_id = HUB
    mqtt_host, mqtt_port = "broker.example", 8883
    mqtt_tls, mqtt_ca, mqtt_cert, mqtt_key = True, "/ca", "/cert", "/key"


def _probe(**script):
    FakePaho.script = script
    return lm.paho_probe(Owner(), NEW_USER, NEW_PW, "probe/topic", ["t/one", "t/two"], 0.05, mqtt_mod=FakePaho)


def test_probe_success():
    assert _probe(connack=RC(), suback=[RC()], puback=RC()) is None
    c = FakePaho.last
    assert c.subscribed == ["t/one", "t/two"] and c.published[0][0] == "probe/topic"
    assert c.closed == ["disconnect", "loop_stop"]
    assert c.kw["client_id"].startswith(f"{HUB}-lt-") and c.kw["client_id"] != HUB
    assert c.tls == {"ca_certs": "/ca", "certfile": "/cert", "keyfile": "/key"} and c.creds == (NEW_USER, NEW_PW)


def test_probe_refused_login():
    assert _probe(connack=RC(bad=True)) == "connect_failed"


def test_probe_no_answer():
    assert _probe() == "connect_failed"


def test_probe_subscribe_denied_or_unanswered():
    assert _probe(connack=RC(), suback=[RC(bad=True)]) == "access_failed"
    assert _probe(connack=RC(), suback=[]) == "access_failed"
    assert _probe(connack=RC(), suback=RC(bad=True)) == "access_failed"
    assert _probe(connack=RC()) == "access_failed"


def test_probe_publish_denied_or_unanswered():
    assert _probe(connack=RC(), suback=[RC()], puback=RC(bad=True)) == "access_failed"
    assert _probe(connack=RC(), suback=[RC()]) == "access_failed"


def test_probe_numeric_reason_codes():
    assert _probe(connack=0, suback=[1], puback=0x10) is None
    assert _probe(connack=0, suback=[0x80], puback=0) == "access_failed"
    assert _probe(connack=0, suback=["x"], puback=0) == "access_failed"


def test_probe_error_is_a_reason_not_an_exception():
    out = io.StringIO()
    with redirect_stdout(out):
        assert _probe(**{"raise": True}) == "connect_failed"
    assert NEW_PW not in out.getvalue()


def test_probe_does_not_run_when_tls_could_not_be_set_up():
    class Broken(Owner):
        _tls_error = "boom"

    assert lm.paho_probe(Broken(), "u", "p", "t", [], 1, mqtt_mod=FakePaho) == "connect_failed"


def test_probe_without_tls_or_client_certificate():
    class Plain(Owner):
        mqtt_tls = False

    FakePaho.script = {"connack": RC(), "suback": [RC()], "puback": RC()}
    assert lm.paho_probe(Plain(), "u", "p", "t", ["a"], 0.05, mqtt_mod=FakePaho) is None
    assert FakePaho.last.tls is None

    class CaOnly(Owner):
        mqtt_cert = mqtt_key = ""

    lm.paho_probe(CaOnly(), "u", "p", "t", ["a"], 0.05, mqtt_mod=FakePaho)
    assert FakePaho.last.tls == {"ca_certs": "/ca"}


def test_probe_close_errors_are_swallowed():
    class Messy(FakePaho.Client):
        def disconnect(self):
            raise OSError("closed")

    class Mod(FakePaho):
        Client = Messy

    FakePaho.script = {"connack": RC(), "suback": [RC()], "puback": RC()}
    assert lm.paho_probe(Owner(), "u", "p", "t", ["a"], 0.05, mqtt_mod=Mod) is None


def test_probe_imports_paho_when_none_is_given(monkeypatch):
    paho = types.ModuleType("paho")
    mqtt = types.ModuleType("paho.mqtt")
    client = FakePaho
    monkeypatch.setitem(sys.modules, "paho", paho)
    monkeypatch.setitem(sys.modules, "paho.mqtt", mqtt)
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", client)
    paho.mqtt, mqtt.client = mqtt, client
    FakePaho.script = {"connack": RC(), "suback": [RC()], "puback": RC()}
    assert lm.paho_probe(Owner(), "u", "p", "t", ["a"], 0.05) is None


# -- small helpers -------------------------------------------------------------------------------------


def test_crypto_loads_lazily_from_the_shared_package(monkeypatch, crypto):
    shared = types.ModuleType("central_core_mqtt_shared")
    monkeypatch.setitem(sys.modules, "central_core_mqtt_shared", shared)
    shared.login_change = crypto
    mover = lm.LoginMover(FakeClient(), store=lm.LoginStore(data_dir="/nonexistent"))
    assert mover.crypto is crypto and mover.crypto is crypto


def test_the_default_thread_starter_runs_the_work():
    import threading

    done = []
    ev = threading.Event()
    lm.LoginMover._default_start_thread(lambda: (done.append(1), ev.set()))
    assert ev.wait(2) and done


def test_unusable_command_ids_are_not_answered(env):
    env.client.build_ack_topic = lambda a, c: (_ for _ in ()).throw(ValueError("bad"))
    env.mover.handle_key_request(None)
    assert not env.client.published


def test_a_publish_error_is_logged_not_raised(env):
    def broken(*a, **k):
        raise OSError("down")

    env.client._publish = broken
    env.mover.handle_key_request("k1")


def test_data_dir_comes_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(lm.DATA_DIR_ENV, str(tmp_path))
    assert lm.LoginStore().dir == tmp_path
    monkeypatch.delenv(lm.DATA_DIR_ENV)
    assert str(lm._data_dir()) == "/data"


def test_a_failure_while_reporting_a_failure_is_swallowed(env, monkeypatch):
    monkeypatch.setattr(env.mover, "_probe", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(env.mover, "_result", lambda *a: (_ for _ in ()).throw(RuntimeError("y")))
    env.change(env.key())
    assert env.mover._busy is False
