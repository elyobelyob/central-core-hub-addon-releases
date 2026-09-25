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
        # cannot be resolved now, so no connection (and no token) can go anywhere
        "http://does-not-resolve.example",
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
