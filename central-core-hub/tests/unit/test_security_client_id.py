"""F7: hubs must not share a client_id.

"home-assistant" was the shipped default, so every hub left at the default
used one MQTT client id and one topic namespace. When client_id is unset the
hub now uses its certificate CN (the vault issues CN = hub id), else a
non-generic hostname, else a random id kept in /data.
"""

import importlib
import json
import pathlib
import socket

import pytest

FIXTURES = pathlib.Path(__file__).parent


@pytest.fixture
def mc(monkeypatch, tmp_path):
    mod = importlib.import_module("mqtt_client")
    monkeypatch.setattr(mod, "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    monkeypatch.setattr(mod, "CLIENT_ID_FILE", tmp_path / "client_id")
    return mod


def test_explicit_client_id_is_used(mc):
    assert mc.CentralCoreClient({"client_id": "hub-42"}).client_id == "hub-42"


def test_default_config_no_longer_ships_a_shared_id():
    base = pathlib.Path(__file__).resolve().parents[2]
    cfg = json.loads((base / "config.json").read_text())
    assert cfg["options"]["client_id"] == ""
    assert 'client_id: ""' in (base / "config.yaml").read_text()


def test_unset_id_uses_certificate_cn(mc, monkeypatch):
    monkeypatch.setattr(mc, "_certificate_common_name", lambda path: "vault-hub-7" if path else None)
    c = mc.CentralCoreClient({"mqtt_cert_bundle": "", "client_id": ""})
    # no cert configured -> CN helper sees no path
    assert c.client_id != "vault-hub-7"
    c2 = mc.CentralCoreClient({"client_id": ""})
    c2.mqtt_cert = "/some/cert.pem"
    assert mc._derive_client_id(c2.mqtt_cert) == "vault-hub-7"


@pytest.mark.parametrize("host", ["homeassistant", "localhost", "home-assistant", ""])
def test_generic_hostname_gets_a_persistent_random_id(mc, monkeypatch, host):
    monkeypatch.setattr(socket, "gethostname", lambda: host)
    first = mc.CentralCoreClient({}).client_id
    second = mc.CentralCoreClient({}).client_id
    assert first.startswith("hub-") and len(first) > 8
    assert first == second
    assert mc.CLIENT_ID_FILE.read_text().strip() == first


def test_specific_hostname_is_still_used(mc, monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "Kitchen Pi")
    assert mc.CentralCoreClient({}).client_id == "kitchen-pi"


def test_shared_default_is_kept_but_warned_about(mc, monkeypatch):
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    c = mc.CentralCoreClient({"client_id": "home-assistant"})
    # changing it would give an existing hub a new identity in the vault
    assert c.client_id == "home-assistant"
    assert any("shared default" in line for line in lines)


def test_certificate_common_name_reads_a_pem(mc, tmp_path):
    ssl = pytest.importorskip("ssl")
    if not hasattr(getattr(ssl, "_ssl", None), "_test_decode_cert"):
        pytest.skip("CPython test decoder not available")
    pem = (FIXTURES / "data" / "client_cn_hub-test-1.pem")
    assert mc._certificate_common_name(str(pem)) == "hub-test-1"
    assert mc._certificate_common_name(str(tmp_path / "missing.pem")) is None


# --- A client id is one MQTT topic level: it must never widen a subscription ---


@pytest.mark.parametrize(
    "bad",
    ["+", "#", "a/b", "hub/+", "hub+", "+/x", "a/#", "..", ".x", "-x", "has space", "ta\tb", "a\nb", "broadcast",
     "x" * 65, "café"],
)
def test_an_unsafe_client_id_stops_the_hub_before_it_subscribes(mc, monkeypatch, bad):
    lines = []
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    with pytest.raises(mc.InvalidClientId):
        mc.CentralCoreClient({"client_id": bad, "mqtt_host": "broker"})
    assert any(line.startswith("ERROR:") and "not a valid hub id" in line and "Not starting" in line for line in lines)


@pytest.mark.parametrize("good", ["hub-42", "larkspur_1.x", "a", "Hub7", "x" * 64, "demo-home-001"])
def test_ordinary_client_ids_are_accepted(mc, good):
    assert mc.CentralCoreClient({"client_id": good}).client_id == good
    assert mc.validate_client_id(good) == good


@pytest.mark.parametrize("bad", [None, 5, b"hub", ""])
def test_validate_client_id_rejects_non_strings_and_empty(mc, bad):
    with pytest.raises(mc.InvalidClientId):
        mc.validate_client_id(bad)


def test_the_error_message_is_short_and_escapes_control_characters(mc):
    with pytest.raises(mc.InvalidClientId) as err:
        mc.validate_client_id("evil\n[2026] fake log line" + "x" * 200)
    text = str(err.value)
    assert "\n" not in text
    assert len(text) < 300


def test_an_unsafe_derived_id_also_stops_the_hub(mc, monkeypatch):
    # a certificate common name is not trusted either
    monkeypatch.setattr(mc, "_derive_client_id", lambda cert=None: "+")
    with pytest.raises(mc.InvalidClientId):
        mc.CentralCoreClient({"mqtt_host": "broker"})


def test_a_hostname_with_other_characters_stops_the_hub(mc, monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "kitchen/pi")
    with pytest.raises(mc.InvalidClientId):
        mc.CentralCoreClient({})


def test_the_command_subscription_is_scoped_to_this_hub(mc):
    c = mc.CentralCoreClient({"client_id": "demo-home-001"})
    assert c.cmd_sub_topic == "hubs/demo-home-001/v1/cmd/+/+"
    assert c.store_ack_topic == "hubs/demo-home-001/v1/ack"


def test_main_exits_instead_of_connecting_with_an_unsafe_id(mc, monkeypatch):
    monkeypatch.setattr(mc, "load_options", lambda: {"client_id": "+", "mqtt_host": "broker"})
    monkeypatch.setattr(mc, "_log", lambda m, file=None: None)
    ran = []
    monkeypatch.setattr(mc.CentralCoreClient, "run", lambda self: ran.append(self))
    with pytest.raises(SystemExit) as stop:
        mc.main()
    assert stop.value.code == 1
    assert ran == []


def test_a_newer_shared_package_builds_the_wildcard_subscription_with_build_subscription(mc, monkeypatch):
    """central_core_mqtt_shared after this release refuses "+" in build_topic."""
    real = mc.topics

    def strict(template, **kw):
        assert "+" not in kw.values(), "build_topic must not be given a wildcard"
        return real.build_topic(template, **kw)

    def subscription(template, wildcards=(), **kw):
        assert tuple(wildcards) == ("domain", "action")
        assert kw["hub_id"] == "demo-home-001"
        return real.build_topic(template, domain="+", action="+", **kw)

    class Newer:
        build_topic = staticmethod(strict)
        build_subscription = staticmethod(subscription)

        def __getattr__(self, name):
            return getattr(real, name)

    monkeypatch.setattr(mc, "topics", Newer())
    c = mc.CentralCoreClient({"client_id": "demo-home-001"})
    assert c.cmd_sub_topic == "hubs/demo-home-001/v1/cmd/+/+"
