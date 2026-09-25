"""F3: registry/set rewrites the privacy allowlist, so it must be authenticated.

The vault never sends registry/set. Without a configured registry token the
command is refused; with one, the token must match (constant-time compare),
the document must be well formed, and the token is never written to disk.
"""

import itertools
import json
import types

import pytest

import handlers


def _mc():
    """The mqtt_client module handlers will import right now (tests may swap it)."""
    import importlib

    return importlib.import_module("mqtt_client")


@pytest.fixture
def registry(tmp_path, monkeypatch):
    target = tmp_path / "SENSOR_REGISTRY.yaml"
    monkeypatch.setattr(_mc(), "SENSOR_REGISTRY", target)
    monkeypatch.delenv("REGISTRY_TOKEN", raising=False)
    _mc().reload_sensor_registry()
    yield target
    _mc().reload_sensor_registry()


def _client(**attrs):
    published = []
    c = types.SimpleNamespace(client_id="hub1", options={}, **attrs)
    c.build_ack_topic = lambda action, cid: f"hubs/hub1/v1/ack/{action.replace('/', '.')}/{cid}"
    c._publish = lambda topic, payload, qos=0: published.append((topic, json.loads(payload)))
    return c, published


_ids = itertools.count(1)


def _send(c, payload):
    msg = types.SimpleNamespace(topic="hubs/hub1/v1/cmd/registry/set", retain=False)
    body = json.dumps({"command_id": f"r{next(_ids)}", "payload": payload})
    handlers.handle_message(c, msg, body, lambda *a: [], None, None, None)


def _final(published):
    return [p for t, p in published if p.get("status") in ("completed", "failed")][-1]


def test_refused_when_no_token_is_configured(registry):
    c, published = _client()
    _send(c, {"registry_mode": "allow", "entries": []})
    assert not registry.exists()
    final = _final(published)
    assert final["status"] == "failed"
    assert final["result"]["reason"] == "registry_updates_disabled"


def test_refused_with_wrong_or_missing_token(registry):
    c, published = _client(registry_token="s3cret")
    _send(c, {"token": "nope", "registry_mode": "allow", "entries": []})
    _send(c, {"registry_mode": "allow", "entries": []})
    _send(c, {"token": 12345, "registry_mode": "allow", "entries": []})
    assert not registry.exists()
    finals = [p for t, p in published if p.get("status") == "failed"]
    assert len(finals) == 3
    assert all(p["result"]["reason"] == "auth_failed" for p in finals)


def test_env_token_is_honoured(registry, monkeypatch):
    monkeypatch.setenv("REGISTRY_TOKEN", "envtok")
    c, published = _client()
    _send(c, {"token": "envtok", "registry_mode": "deny", "entries": [{"entity_id": "sensor.x", "provide": False}]})
    assert _final(published)["status"] == "completed"
    assert _mc().is_entity_allowed("sensor.x") is False


def test_accepted_with_token_and_token_not_persisted(registry):
    c, published = _client(registry_token="s3cret")
    doc = {"token": "s3cret", "registry_mode": "deny", "entries": [{"entity_id": "sensor.secret_*", "provide": False}]}
    _send(c, doc)
    final = _final(published)
    assert final["status"] == "completed", final
    assert final["result"] == {"success": True, "entries": 1}
    written = registry.read_text()
    assert "s3cret" not in written
    assert json.loads(written)["entries"] == doc["entries"]
    assert _mc().is_entity_allowed("sensor.secret_door") is False
    assert _mc().is_entity_allowed("sensor.hallway") is True


@pytest.mark.parametrize(
    "doc",
    [
        {"registry_mode": "sometimes", "entries": []},
        {"registry_mode": "deny", "entries": "sensor.*"},
        {"registry_mode": "deny", "entries": [{"entity_id": 5}]},
        {"registry_mode": "deny", "entries": ["sensor.x"]},
    ],
)
def test_malformed_documents_are_refused(registry, doc):
    c, published = _client(registry_token="s3cret")
    _send(c, dict(doc, token="s3cret"))
    assert not registry.exists()
    final = _final(published)
    assert final["status"] == "failed"
    assert final["result"]["reason"] == "invalid_registry"
