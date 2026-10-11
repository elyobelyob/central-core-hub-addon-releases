"""F8: the long-lived admin HA token is not sent over plaintext to another machine.

The add-on runs on the Home Assistant host, so Home Assistant is always local.
http:// (and ws://) is accepted only for loopback, the Supervisor's internal
names, or an address of this host; https:// is always accepted.
"""

import importlib
import pathlib

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


def test_client_disables_ha_integration_for_remote_plaintext(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    c = mc.CentralCoreClient({"client_id": "hub1", "ha_api_url": "http://attacker.example:8123", "ha_api_token": "tok"})
    assert c.ha_api_token == ""
    assert c.ha_api_url == ""
    assert c._ha_ws_listener is None
    assert any("not sending the Home Assistant token" in m for m in lines)
    assert not any("tok" == m for m in lines)


def test_client_disables_ha_integration_for_unresolvable_plaintext_host(monkeypatch, tmp_path):
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    c = mc.CentralCoreClient({"client_id": "hub1", "ha_api_url": "http://does-not-resolve.example:8123",
                              "ha_api_token": "tok"})
    assert c.ha_api_token == "" and c.ha_api_url == ""
    assert any("does not resolve" in m for m in lines)


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


def test_a_later_dns_answer_cannot_redirect_the_token(monkeypatch, tmp_path):
    """The name is looked up at startup only; every request after that uses the address checked then."""
    mc = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mc, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    monkeypatch.setattr(mc, "_log", lambda m, file=None: None)
    c = mc.CentralCoreClient(
        {"client_id": "hub1", "ha_api_url": "http://homeassistant.local:8123", "ha_api_token": "tok"}
    )
    assert c.ha_api_url == "http://192.168.1.10:8123"
    assert c.ha_api_token == "tok"
    # the name now resolves to someone else: nothing in the client looks it up again
    monkeypatch.setattr(ha_safety, "_resolve_host", lambda host: ["203.0.113.5"])
    assert c.ha_api_url == "http://192.168.1.10:8123"
    assert "homeassistant.local" not in c.ha_api_url


def test_a_name_with_one_remote_address_is_refused_even_if_another_is_local(monkeypatch):
    monkeypatch.setattr(ha_safety, "_resolve_host", _resolver({"mixed.local": ["192.168.1.10", "203.0.113.5"]}))
    ok, reason, use = ha_safety.pin_token_url("http://mixed.local:8123")
    assert not ok and "203.0.113.5" in reason
    assert use == "http://mixed.local:8123"
