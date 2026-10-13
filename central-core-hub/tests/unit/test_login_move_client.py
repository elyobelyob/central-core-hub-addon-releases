"""The parts of the hub's MQTT client and command handlers that move it to a new broker login."""

import importlib.util
import json
import pathlib
import types
import uuid

import pytest

import login_move as lm

BASE = pathlib.Path(__file__).parents[2]
NEW_PW, OLD_PW = f"new-{uuid.uuid4().hex[:12]}", f"old-{uuid.uuid4().hex[:12]}"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, str(BASE / filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mc():
    return _load("mqtt_client_login_test", "mqtt_client.py")


@pytest.fixture
def handlers():
    return _load("handlers_login_test", "handlers.py")


class FakePaho:
    def __init__(self):
        self.calls = []
        self.fail = set()

    def _step(self, name):
        def run(*a, **k):
            self.calls.append((name, a, k))
            if name in self.fail:
                raise RuntimeError(name)
        return run

    def __getattr__(self, name):
        if name in ("disconnect", "loop_stop", "username_pw_set", "connect_async", "loop_start", "connect"):
            return self._step(name)
        raise AttributeError(name)


@pytest.mark.parametrize("rc,failed", [
    (None, False), (0, False), (5, True), ("x", False),
    (types.SimpleNamespace(is_failure=True), True), (types.SimpleNamespace(is_failure=False), False)])
def test_connack_failed(mc, rc, failed):
    assert mc._connack_failed(rc) is failed


@pytest.mark.parametrize("args,kwargs,code", [
    ((), {}, None), ((0,), {}, 0), (({}, 5, None), {}, 5), (({}, 7), {}, 7),
    (({},), {"reason_code": 3}, 3), (({},), {"reasonCode": 4}, 4), ((), {"rc": 2}, 2)])
def test_connack_code(mc, args, kwargs, code):
    assert mc._connack_code(args, kwargs) == code


def test_a_refused_connection_is_not_a_connection(mc):
    c = mc.CentralCoreClient({"client_id": "demo-home-001"})
    subscribed = []
    fake = types.SimpleNamespace(subscribe=lambda *a, **k: subscribed.append(a))
    c.on_connect(fake, None, {}, types.SimpleNamespace(is_failure=True), None)
    assert c._connected is False and c.connect_refused() is True and not subscribed
    c.on_connect(fake, None, {}, 0, None)
    assert c._connected is True and subscribed


def test_switch_login_restarts_the_network_loop_with_the_new_login(mc):
    c = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker.example", "mqtt_port": 1883,
                              "mqtt_username": "old", "mqtt_password": OLD_PW})
    fake = FakePaho()
    c._client = fake
    c._connected = True
    c._connack_refusals = 3
    c._tls_error = None
    c.switch_login("new", NEW_PW)
    assert [n for n, _, _ in fake.calls] == ["disconnect", "loop_stop", "username_pw_set", "connect_async", "loop_start"]
    assert fake.calls[2][1] == ("new", NEW_PW) and fake.calls[3][1] == ("broker.example", 1883)
    assert (c.mqtt_username, c.mqtt_password, c._connected, c.connect_refused(), c._loop_started) == (
        "new", NEW_PW, False, False, True)


def test_switch_login_copes_with_a_client_that_fails_to_close_and_has_no_connect_async(mc):
    c = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker.example"})

    class Old:
        calls = []

        def disconnect(self):
            raise RuntimeError("closed")

        def loop_stop(self):
            raise RuntimeError("closed")

        def username_pw_set(self, u, p):
            self.calls.append(("u", u, p))

        def connect(self, host, port, keepalive=0):
            self.calls.append(("connect", host))

        def loop_start(self):
            self.calls.append(("loop",))

    c._client = Old()
    c.switch_login("", "")
    assert Old.calls == [("u", None, None), ("connect", "broker.example"), ("loop",)]


def test_the_mover_is_made_once_and_not_before_it_is_needed(mc, monkeypatch, tmp_path):
    monkeypatch.setenv(lm.DATA_DIR_ENV, str(tmp_path))
    c = mc.CentralCoreClient({"client_id": "demo-home-001"})
    assert not hasattr(c, "_login_mover")
    first = c.login_mover()
    assert first is c.login_mover() and first.client is c


def test_main_logs_the_login_name_and_source_but_never_the_password(mc, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv(lm.DATA_DIR_ENV, str(tmp_path))
    store = lm.LoginStore(data_dir=tmp_path)
    opts = tmp_path / "options.json"
    opts.write_text(json.dumps({"mqtt_host": "", "client_id": "demo-home-001",
                                "mqtt_username": "hub-shared", "mqtt_password": OLD_PW}))  # ggignore
    store.save("hub-demo-home-001", NEW_PW)
    monkeypatch.setattr(mc, "load_options", lambda: json.loads(opts.read_text()))
    mc.main()
    out = capsys.readouterr()
    text = out.out + out.err
    assert "'hub-demo-home-001' (from override)" in text
    assert NEW_PW not in text and OLD_PW not in text


def test_main_goes_on_if_the_saved_login_cannot_be_read(mc, monkeypatch, capsys):
    monkeypatch.setattr(mc, "load_options", lambda: {"mqtt_host": "", "client_id": "demo-home-001"})
    real = mc._sibling
    monkeypatch.setattr(mc, "_sibling", lambda name: (_ for _ in ()).throw(ImportError("x")) if name == "login_move"
                        else real(name))
    mc.main()
    assert "Could not read the saved broker login" in capsys.readouterr().out


def test_run_checks_for_an_unconfirmed_move_before_connecting(mc):
    c = mc.CentralCoreClient({"client_id": "demo-home-001"})
    order = []
    c.start_worker = lambda: None
    c.start_outbox_sender = lambda: None
    c.connect = lambda: order.append("connect") or (_ for _ in ()).throw(KeyboardInterrupt())
    c._login_mover = types.SimpleNamespace(settle_pending_at_start=lambda: order.append("settle"))
    with pytest.raises(KeyboardInterrupt):
        c.run()
    assert order == ["settle", "connect"]


def test_run_goes_on_if_the_unconfirmed_move_check_fails(mc, capsys):
    c = mc.CentralCoreClient({"client_id": "demo-home-001"})
    c.start_worker = lambda: None
    c.start_outbox_sender = lambda: None
    c.connect = lambda: (_ for _ in ()).throw(KeyboardInterrupt())
    c._login_mover = types.SimpleNamespace(settle_pending_at_start=lambda: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(KeyboardInterrupt):
        c.run()
    assert "Could not check for an unconfirmed login move" in capsys.readouterr().out


# -- the command handlers -------------------------------------------------------------------------


class Mover:
    def __init__(self):
        self.calls = []

    def handle_key_request(self, command_id):
        self.calls.append(("key", command_id))

    def handle_change(self, command_id, fields):
        self.calls.append(("change", command_id, fields))


class HandlerClient:
    client_id = "demo-home-001"

    def __init__(self):
        self.mover = Mover()
        self.acks = []

    def login_mover(self):
        return self.mover

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"

    def _publish(self, topic, payload, qos=0, persist=None):
        self.acks.append((topic, json.loads(payload)))


def _msg(action, body, retain=False):
    return types.SimpleNamespace(topic=f"hubs/demo-home-001/v1/cmd/login/{action}", retain=retain,
                                 payload=json.dumps(body).encode())


def _send(handlers, client, action, body, **kw):
    msg = _msg(action, body, **kw)
    handlers.handle_message(client, msg, msg.payload.decode(), None, None, None, None)


def _cmd(n="c1", **extra):
    return {"command_id": n, "timestamp": lm._utc_now_iso(), **extra}


def test_key_request_reaches_the_mover(handlers):
    c = HandlerClient()
    _send(handlers, c, "key_request", _cmd("k1"))
    assert c.mover.calls == [("key", "k1")]


def test_change_fields_may_sit_in_the_command_or_in_a_payload_object(handlers):
    c = HandlerClient()
    _send(handlers, c, "change", _cmd("c1", request_id="r" * 16, ciphertext="x"))
    _send(handlers, c, "change", _cmd("c2", payload={"request_id": "q" * 16}))
    assert c.mover.calls[0][2]["ciphertext"] == "x" and c.mover.calls[1][2] == {"request_id": "q" * 16}


def test_old_retained_repeated_or_unsigned_login_commands_are_refused_like_any_other(handlers):
    c = HandlerClient()
    _send(handlers, c, "key_request", _cmd("k1"), retain=True)
    stale = {"command_id": "k2", "timestamp": "2020-01-01T00:00:00Z"}
    _send(handlers, c, "key_request", stale)
    _send(handlers, c, "key_request", {"command_id": "k3"})
    _send(handlers, c, "key_request", _cmd("k4"))
    _send(handlers, c, "key_request", _cmd("k4"))
    assert c.mover.calls == [("key", "k4")]
    assert {a["result"]["reason"] for _, a in c.acks} == {"stale_command", "bad_timestamp"}


def test_a_failing_mover_is_logged_without_its_message(handlers, capsys):
    c = HandlerClient()
    c.mover.handle_change = lambda *a: (_ for _ in ()).throw(RuntimeError(f"password is {NEW_PW}"))
    _send(handlers, c, "change", _cmd("c1", request_id="r" * 16))
    out = capsys.readouterr()
    assert "login/change failed: RuntimeError" in out.out + out.err and NEW_PW not in out.out + out.err


def test_a_binary_or_non_object_payload_is_handled(handlers):
    c = HandlerClient()
    handlers._handle_login(c, "<binary>", "change")
    handlers._handle_login(c, "[1]", "change")
    handlers._handle_login(c, "not json", "key_request")
    assert c.mover.calls == [("change", None, None), ("change", None, None), ("key", None)]


def test_switch_login_refuses_when_tls_is_on_but_not_set_up(mc):
    c = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker.example"})
    fake = FakePaho()
    c._client = fake
    c._tls_error = "boom"
    with pytest.raises(RuntimeError):
        c.switch_login("new", NEW_PW)
    assert fake.calls == [] and c.mqtt_username != "new"


def test_switch_login_that_fails_part_way_lets_the_main_loop_connect_afresh(mc):
    c = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker.example"})
    fake = FakePaho()
    fake.fail = {"loop_start"}
    c._client = fake
    c._loop_started = True
    with pytest.raises(RuntimeError):
        c.switch_login("new", NEW_PW)
    assert c._loop_started is False and c.mqtt_username == "new"


def test_the_old_connections_state_is_cleared_only_after_its_thread_has_stopped(mc):
    c = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker.example"})
    seen = []

    class Old(FakePaho):
        def _step(self, name):
            def run(*a, **k):
                seen.append((name, c._connected, c._connack_refusals))
            return run

    c._client = Old()
    c._tls_error = None
    c._connected = True
    c._connack_refusals = 2
    c.switch_login("new", NEW_PW)
    assert seen[0][1:] == (True, 2) and seen[1][1:] == (True, 2)  # disconnect, loop_stop: not cleared yet
    assert seen[2][1:] == (False, 0)  # username_pw_set: cleared


def test_a_first_connect_waits_for_a_switch_in_progress(mc):
    import threading

    c = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker.example"})
    c._tls_error = None
    c._client = FakePaho()
    c._loop_started = False
    started = threading.Event()
    done = []

    c._link_lock.acquire()
    try:
        t = threading.Thread(target=lambda: (started.set(), done.append(c.connect_once())))
        t.start()
        started.wait(1)
        t.join(0.2)
        assert t.is_alive()  # blocked on the lock
    finally:
        c._link_lock.release()
    t.join(2)
    assert done


def test_the_reset_option_is_in_the_add_on_schema():
    import yaml

    schema = yaml.safe_load((BASE / "config.yaml").read_text())["schema"]
    assert schema["reset_saved_login"] == "bool?"
    assert json.loads((BASE / "config.json").read_text())["schema"]["reset_saved_login"] == "bool?"


def test_switch_login_fails_if_the_network_loop_does_not_start(mc):
    c = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker.example"})

    class NoLoop(FakePaho):
        def __getattr__(self, name):
            if name == "loop_start":
                return lambda: 4
            return super().__getattr__(name)

    c._client = NoLoop()
    c._tls_error = None
    with pytest.raises(RuntimeError):
        c.switch_login("new", NEW_PW)
    assert c._loop_started is False
