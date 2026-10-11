"""F8: the long-lived admin HA token is not sent over plaintext to another machine.

The add-on runs on the Home Assistant host, so Home Assistant is always local.
http:// (and ws://) is accepted only for loopback, the Supervisor's internal
names, or an address of this host; https:// is always accepted.
"""

import importlib
import pathlib
import types

import pytest

import ha_safety


def _resolver(mapping):
    def resolve(host):
        if host not in mapping:
            raise OSError("unresolvable")
        return mapping[host]

    return resolve


@pytest.fixture(autouse=True)
def fake_network(monkeypatch):
    monkeypatch.setattr(
        ha_safety,
        "_resolve_host",
        _resolver({"homeassistant.local": ["192.168.1.10"], "nas.lan": ["192.168.1.99"], "attacker.example": ["203.0.113.5"]}),
    )
    monkeypatch.setattr(ha_safety, "_is_local_address", lambda ip: ip.startswith("127.") or ip in ("::1", "192.168.1.10"))


@pytest.mark.parametrize(
    "url",
    [
        "https://anything.example:8123",
        "http://localhost:8123",
        "http://127.0.0.1:8123",
        "http://[::1]:8123",
        "http://homeassistant:8123",
        "http://supervisor/core",
        "http://192.168.1.10:8123",
        "http://homeassistant.local:8123",
        # https needs no resolution: the token is encrypted whoever answers
        "https://does-not-resolve.example",
    ],
)
def test_allowed(url):
    ok, reason = ha_safety.check_token_transport(url)
    assert ok, reason


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.99:8123",
        "http://nas.lan:8123",
        "http://attacker.example:8123",
        "ws://attacker.example:8123",
        "ftp://localhost",
        "localhost:8123",
        "",
        # fail closed: a name that does not resolve cannot be shown to be this
        # machine, and could resolve elsewhere later
        "http://does-not-resolve.example",
        "ws://does-not-resolve.example:8123",
    ],
)
def test_refused(url):
    ok, reason = ha_safety.check_token_transport(url)
    assert not ok
    assert reason


def test_a_plain_http_address_is_judged_at_each_connection_not_at_start(monkeypatch, tmp_path):
    """Home Assistant's address may only arrive (DHCP) after the add-on starts:
    an address that is not this machine yet is refused per connection, and
    used as soon as it is, instead of switching Home Assistant off for good."""
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    monkeypatch.setattr(mc, "HA_RESOLVE_CACHE_S", 0)
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    c = mc.CentralCoreClient({"client_id": "hub1", "ha_api_url": "http://192.168.1.20:8123", "ha_api_token": "tok"})
    _made.append(c)
    assert c.ha_api_token == "tok" and c.ha_api_url == "http://192.168.1.20:8123"
    assert c._ha_base() == ""  # not this machine (yet): no token sent
    assert any("not sending the Home Assistant token" in m for m in lines)
    assert not any("tok" == m for m in lines)
    monkeypatch.setattr(ha_safety, "_is_local_address", lambda ip: ip == "192.168.1.20")  # DHCP arrives
    assert c._ha_base() == "http://192.168.1.20:8123"


def test_a_name_that_is_not_this_machine_never_gets_the_token_but_stays_configured(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    c = mc.CentralCoreClient({"client_id": "hub1", "ha_api_url": "http://attacker.example:8123", "ha_api_token": "tok"})
    _made.append(c)
    assert c.ha_api_url == "http://attacker.example:8123" and c.ha_api_token == "tok"
    assert c._ha_base() == ""  # refused for every request while it points elsewhere
    assert any("not sending the Home Assistant token" in m and "203.0.113.5" in m for m in lines)


def test_a_name_that_does_not_resolve_at_boot_is_retried_not_switched_off(monkeypatch, tmp_path):
    """After a power cut the hub can start before DNS is up: Home Assistant must
    come back by itself, or night-door alerts stop while heartbeats look fine."""
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    monkeypatch.setattr(mc, "HA_RESOLVE_CACHE_S", 0)
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    monkeypatch.setattr(ha_safety, "_resolve_host", _resolver({}))  # nothing resolves yet
    c = mc.CentralCoreClient({"client_id": "hub1", "ha_api_url": "http://homeassistant.local:8123",
                              "ha_api_token": "tok"})
    _made.append(c)
    assert c.ha_api_token == "tok" and c._ha_ws_listener is not None
    assert c._ha_base() == ""
    assert any("does not resolve" in m for m in lines)
    monkeypatch.setattr(ha_safety, "_resolve_host", _resolver({"homeassistant.local": ["192.168.1.10"]}))
    assert c._ha_base() == "http://192.168.1.10:8123"  # DNS is up: back by itself


@pytest.mark.parametrize(
    "url,reason",
    [
        ("ftp://localhost", "unsupported scheme"),
        ("http://localhost:99999", "invalid port"),
        ("http://[fe80::1%25eth0]:8123", "zone"),
        ("http://", "no host"),
    ],
)
def test_the_startup_check_refuses_only_what_no_connection_can_fix(url, reason):
    ok, why = ha_safety.check_token_url(url)
    assert not ok and reason in why


@pytest.mark.parametrize("url", ["http://does-not-resolve.example:8123", "http://attacker.example:8123",
                                 "http://homeassistant.local:8123", "https://anything.example",
                                 "http://203.0.113.5:8123", "http://[2001:db8::1]:8123"])
def test_the_startup_check_does_not_resolve_or_judge_addresses(url, monkeypatch):
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: pytest.fail("resolved at startup"))
    monkeypatch.setattr(ha_safety, "_is_local_address", lambda ip: pytest.fail("judged at startup"))
    assert ha_safety.check_token_url(url)[0]


def test_client_keeps_local_config(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    c = mc.CentralCoreClient({"client_id": "hub1", "ha_api_url": "http://localhost:8123", "ha_api_token": "tok"})
    assert c.ha_api_token == "tok"


def test_secrets_are_password_fields_in_the_schema():
    base = pathlib.Path(__file__).resolve().parents[2]
    text = (base / "config.yaml").read_text()
    assert "ha_api_token: password?" in text
    assert "mqtt_password: password?" in text
    import json

    schema = json.loads((base / "config.json").read_text())["schema"]
    assert schema["ha_api_token"] == "password?"
    assert schema["mqtt_password"] == "password?"


# --- The checked address is the one used: no second look-up for the requests ---


@pytest.mark.parametrize(
    "url,pinned",
    [
        ("http://homeassistant.local:8123", "http://192.168.1.10:8123"),
        ("http://homeassistant.local:8123/", "http://192.168.1.10:8123/"),
        ("http://homeassistant.local", "http://192.168.1.10"),
        ("ws://homeassistant.local:8123/api/websocket", "ws://192.168.1.10:8123/api/websocket"),
        ("HTTP://HomeAssistant.Local:8123/a?b=1", "http://192.168.1.10:8123/a?b=1"),
        ("http://user:pw@homeassistant.local:8123", "http://user:pw@192.168.1.10:8123"),
    ],
)
def test_a_plain_http_host_name_is_replaced_by_the_checked_address(url, pinned):
    ok, reason, use = ha_safety.pin_token_url(url)
    assert ok, reason
    assert use == pinned
    assert "pinned to 192.168.1.10" in reason


def test_an_ipv6_address_is_bracketed_when_pinned(monkeypatch):
    monkeypatch.setattr(ha_safety, "_resolve_host", _resolver({"ha6.local": ["::1"]}))
    ok, _, use = ha_safety.pin_token_url("http://ha6.local:8123/x")
    assert ok and use == "http://[::1]:8123/x"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8123",
        "http://homeassistant:8123/core",
        "http://supervisor/core",
        "http://127.0.0.1:8123",
        "http://192.168.1.10:8123",
        "http://[::1]:8123",
        "https://homeassistant.local:8123",  # encrypted: no pinning needed
        "wss://homeassistant.local:8123",
    ],
)
def test_other_urls_are_not_rewritten(url):
    ok, reason, use = ha_safety.pin_token_url(url)
    assert ok, reason
    assert use == url


@pytest.mark.parametrize("url", ["http://nas.lan:8123", "http://does-not-resolve.example", "ftp://x", "", "http://"])
def test_a_refused_url_comes_back_unchanged(url):
    ok, reason, use = ha_safety.pin_token_url(url)
    assert not ok and reason
    assert use == url


def test_the_name_is_resolved_once_per_check(monkeypatch):
    calls = []

    def resolve(host):
        calls.append(host)
        return ["192.168.1.10"]

    monkeypatch.setattr(ha_safety, "_resolve_host", resolve)
    ha_safety.pin_token_url("http://homeassistant.local:8123")
    ha_safety.check_token_transport("http://homeassistant.local:8123")
    assert calls == ["homeassistant.local", "homeassistant.local"]  # one per call, never two within one


_made = []


@pytest.fixture(autouse=True)
def _stop_listeners():
    yield
    while _made:
        listener = getattr(_made.pop(), "_ha_ws_listener", None)
        if listener is not None:
            listener.stop()


def _client(monkeypatch, tmp_path, url, lines=None):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    monkeypatch.setattr(mc, "_log", lambda m, file=None: (lines if lines is not None else []).append(m))
    client = mc.CentralCoreClient({"client_id": "hub1", "ha_api_url": url, "ha_api_token": "tok"})
    _made.append(client)
    return client


def test_each_request_checks_and_pins_anew(monkeypatch, tmp_path):
    """Pinned per request, never for the life of the process: when Home
    Assistant's address changes (DHCP), the next request follows it; when the
    name points elsewhere, that request is refused."""
    lines = []
    monkeypatch.setattr(importlib.import_module("mqtt_client"), "HA_RESOLVE_CACHE_S", 0)
    c = _client(monkeypatch, tmp_path, "http://homeassistant.local:8123", lines)
    assert c.ha_api_url == "http://homeassistant.local:8123"  # the configured URL is kept
    assert c._ha_base() == "http://192.168.1.10:8123"
    # Home Assistant gets a new address from DHCP: followed on the next request
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: ["192.168.1.11"])
    monkeypatch.setattr(ha_safety, "_is_local_address", lambda ip: ip == "192.168.1.11")
    assert c._ha_base() == "http://192.168.1.11:8123"
    # the name now points at another machine: refused for this request, logged once
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: ["203.0.113.5"])
    assert c._ha_base() == ""
    assert c._ha_base() == ""
    warnings = [m for m in lines if "not sending the Home Assistant token" in m and "203.0.113.5" in m]
    assert len(warnings) == 1
    # and back again
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: ["192.168.1.11"])
    assert c._ha_base() == "http://192.168.1.11:8123"


def test_requests_use_the_address_pinned_for_them(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "HA_RESOLVE_CACHE_S", 0)
    c = _client(monkeypatch, tmp_path, "http://homeassistant.local:8123")
    seen = []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"version": "2026.10.0"}

    monkeypatch.setattr(mc, "requests", types.SimpleNamespace(get=lambda url, **kw: seen.append(url) or Resp()))
    c._fetch_ha_version_from_api()
    assert seen == ["http://192.168.1.10:8123/api/config"]
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: ["203.0.113.5"])
    assert c._fetch_ha_version_from_api() is None
    assert len(seen) == 1  # nothing sent to the other machine


def test_sensor_fetches_go_through_the_per_request_check(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    c = _client(monkeypatch, tmp_path, "http://homeassistant.local:8123")
    urls = []
    monkeypatch.setattr(mc, "fetch_sensors", lambda url, token: urls.append(url) or [])
    monkeypatch.setattr(mc, "fetch_selected_sensors", lambda url, token, wanted: urls.append(url) or [])
    c._publish = lambda *a, **k: None
    c.publish_sensors()
    c.publish_sensors_with_default_filter()
    assert urls == ["http://192.168.1.10:8123", "http://192.168.1.10:8123"]


def test_the_websocket_listener_checks_every_reconnect(monkeypatch, tmp_path):
    import ha_client

    c = _client(monkeypatch, tmp_path, "http://homeassistant.local:8123")
    listener = c._ha_ws_listener
    assert listener is not None and listener.url_guard is ha_safety.pin_token_url

    attempts = []
    answers = iter([["203.0.113.5"], ["192.168.1.10"], ["192.168.1.10"]])
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: next(answers))

    fresh = ha_client.HAWebSocketListener("http://homeassistant.local:8123", "tok", on_event=lambda *a: None)
    fresh.url_guard = ha_safety.pin_token_url
    logs = []
    fresh.log_fn = logs.append
    monkeypatch.setattr(fresh._stop, "wait", lambda t=None: False)

    def connect(url, timeout=None):
        attempts.append(url)
        if len(attempts) == 2:
            fresh._stop.set()
        raise OSError("refused")

    monkeypatch.setattr(ha_client, "websocket", types.SimpleNamespace(create_connection=connect))
    monkeypatch.setattr(fresh, "_log", lambda m: logs.append(m))
    monkeypatch.setattr(ha_client.traceback, "print_exc", lambda *a, **k: None)
    fresh._run()
    # first attempt refused before connecting (name pointed elsewhere); then each
    # reconnect resolved again and connected to the address checked for it
    assert attempts == ["ws://192.168.1.10:8123/api/websocket", "ws://192.168.1.10:8123/api/websocket"]
    assert any("HA WS not connecting" in m and "203.0.113.5" in m for m in logs)


@pytest.mark.parametrize("url", ["http://localhost:99999", "http://homeassistant:0x50", "http://[::1"])
def test_a_bad_ha_url_disables_home_assistant_but_not_the_hub(monkeypatch, tmp_path, url):
    lines = []
    c = _client(monkeypatch, tmp_path, url, lines)
    assert c.ha_api_url == "" and c.ha_api_token == ""
    assert c.client_id == "hub1"  # the hub (MQTT) still starts
    assert any("not sending the Home Assistant token" in m for m in lines)


def test_an_out_of_range_port_is_refused_not_raised():
    assert ha_safety.check_token_transport("http://localhost:99999") == (False, "invalid port")
    assert ha_safety.pin_token_url("ws://homeassistant.local:70000")[:2] == (False, "invalid port")


def test_ipv4_is_preferred_when_both_families_resolve(monkeypatch):
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: ["::1", "127.0.0.1"])
    ok, _, use = ha_safety.pin_token_url("http://dual.local:8123")
    assert ok and use == "http://127.0.0.1:8123"


@pytest.mark.parametrize("url", ["http://[fe80::1%25eth0]:8123", "ws://[fe80::1%eth0]:8123"])
def test_ipv6_zone_ids_are_refused(url):
    ok, reason, use = ha_safety.pin_token_url(url)
    assert not ok and "zone" in reason and use == url


def test_a_name_with_only_zone_scoped_addresses_is_refused(monkeypatch):
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: ["fe80::1%eth0"])
    monkeypatch.setattr(ha_safety, "_is_local_address", lambda ip: True)
    ok, reason, _ = ha_safety.pin_token_url("http://linklocal.local:8123")
    assert not ok and "zone id" in reason


def test_zone_scoped_addresses_are_skipped_when_another_exists(monkeypatch):
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: ["fe80::1%eth0", "::1"])
    monkeypatch.setattr(ha_safety, "_is_local_address", lambda ip: True)
    ok, _, use = ha_safety.pin_token_url("http://linklocal.local:8123")
    assert ok and use == "http://[::1]:8123"


def test_a_name_with_a_remote_answer_uses_its_local_address(monkeypatch):
    """The token only ever goes to the pinned local address, so an extra answer
    that is not this machine is ignored (and named) rather than refusing for
    good where earlier versions connected."""
    monkeypatch.setattr(ha_safety, "_resolve_host", _resolver({"mixed.local": ["203.0.113.5", "192.168.1.10"]}))
    ok, reason, use = ha_safety.pin_token_url("http://mixed.local:8123")
    assert ok and use == "http://192.168.1.10:8123"
    assert "ignored 203.0.113.5" in reason


def test_ignored_answers_are_logged_once(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "HA_RESOLVE_CACHE_S", 0)
    monkeypatch.setattr(ha_safety, "_resolve_host", _resolver({"mixed.local": ["203.0.113.5", "192.168.1.10"]}))
    lines = []
    c = _client(monkeypatch, tmp_path, "http://mixed.local:8123", lines)
    for _ in range(3):
        assert c._ha_base() == "http://192.168.1.10:8123"
    assert len([m for m in lines if "ignored 203.0.113.5" in m]) == 1


def test_the_rest_address_is_reused_for_a_minute(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    calls = []

    def resolve(host):
        calls.append(host)
        return ["192.168.1.10"]

    monkeypatch.setattr(ha_safety, "_resolve_host", resolve)
    c = _client(monkeypatch, tmp_path, "http://homeassistant.local:8123")
    calls.clear()  # the websocket listener may have looked it up already
    now = [1000.0]
    monkeypatch.setattr(mc.time, "monotonic", lambda: now[0])
    assert c._ha_base() == "http://192.168.1.10:8123"
    now[0] += 59
    assert c._ha_base() == "http://192.168.1.10:8123"
    assert calls == ["homeassistant.local"]
    now[0] += 2
    c._ha_base()
    assert calls == ["homeassistant.local", "homeassistant.local"]
