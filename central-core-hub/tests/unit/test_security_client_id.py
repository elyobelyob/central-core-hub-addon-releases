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
