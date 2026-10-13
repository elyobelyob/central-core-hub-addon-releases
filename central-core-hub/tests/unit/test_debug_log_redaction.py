"""Debug logs show a short preview of every message; secrets in it are blanked."""

import importlib
import json
import types

import pytest


@pytest.fixture
def mc():
    return importlib.import_module("mqtt_client")


SECRET = "s3cr3t-value-123"


@pytest.mark.parametrize(
    "key", ["token", "ha_api_token", "mqtt_password", "password", "secret", "client_secret", "private_key",
            "privateKey", "api_key", "apiKey", "Authorization", "access_token", "Token"]
)
def test_secret_fields_are_blanked(mc, key):
    out = mc._preview(json.dumps({"command_id": "c1", "payload": {key: SECRET, "entries": []}}))
    assert SECRET not in out
    assert "[REDACTED]" in out
    assert "c1" in out and "entries" in out


def test_the_registry_set_token_never_reaches_the_log(mc):
    body = json.dumps({"command_id": "r1", "action": "registry/set", "payload": {"token": SECRET, "entries": []}})
    assert SECRET not in mc._preview(body)
    assert SECRET not in mc._preview(body.encode())
    assert SECRET not in mc._preview(bytearray(body.encode()))


def test_nested_lists_and_non_string_values_are_blanked(mc):
    out = mc._preview(json.dumps({"a": [{"password": 12345678}, {"private_key": {"d": SECRET}}], "ok": 1}))
    assert "12345678" not in out and SECRET not in out
    assert '"ok":1' in out


def test_other_fields_are_kept(mc):
    out = mc._preview(json.dumps({"sensors": ["binary_sensor.front_door"], "count": 3}))
    assert out == '{"sensors":["binary_sensor.front_door"],"count":3}'


def test_secrets_are_blanked_before_the_text_is_cut(mc):
    # the secret sits right at the start, long text follows: no part of it may survive the cut
    body = json.dumps({"token": SECRET, "filler": "x" * 1000})
    out = mc._preview(body, limit=40)
    assert SECRET not in out and SECRET[:6] not in out
    assert "chars)" in out


@pytest.mark.parametrize(
    "text",
    [
        '{"token": "%s", "entr' % SECRET,  # cut off: not valid JSON
        "{'token': '%s'}" % SECRET,  # single quotes
        '[{"x": 1}, {"password": "%s"' % SECRET,
        '{"api_key": %s}' % SECRET,
        '{"command_id": "r1", "payload": {"token": "%s' % SECRET,  # cut off inside the secret
    ],
)
def test_text_that_is_not_valid_json_is_still_scrubbed(mc, text):
    assert SECRET not in mc._preview(text)


def test_pem_blocks_are_still_redacted(mc):
    pem = "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----"
    assert mc._preview("x " + pem) == "x [PEM REDACTED]"


@pytest.mark.parametrize("value", [None, b"\xff\xfe", 12, ["a"]])
def test_odd_payloads_do_not_raise(mc, value):
    assert isinstance(mc._preview(value), str)


def test_unprintable_payload(mc):
    class Bad:
        def __str__(self):
            raise RuntimeError("no")

    assert mc._preview(Bad()) == "<unprintable>"


def test_inbound_and_outbound_debug_lines_are_scrubbed(mc, monkeypatch):
    lines = []
    monkeypatch.setattr(mc, "_DEBUG_LOGGING", True)
    monkeypatch.setattr(mc, "_log", lambda m, file=None: lines.append(m))
    client = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker"})
    client._client = types.SimpleNamespace(publish=lambda *a, **k: types.SimpleNamespace(rc=0))
    client._submit = lambda fn, *a: None
    body = json.dumps({"command_id": "r1", "payload": {"token": SECRET}})
    msg = types.SimpleNamespace(topic="hubs/demo-home-001/v1/cmd/registry/set", payload=body.encode(), retain=False)
    client.on_message(None, None, msg)
    client._publish("hubs/demo-home-001/v1/telemetry/system", json.dumps({"password": SECRET}))
    assert any("MQTT <-" in line and "payload=" in line for line in lines)
    assert any("PUBLISH" in line and "payload=" in line for line in lines)
    assert not any(SECRET in line for line in lines)


def test_nothing_is_rendered_when_debug_logging_is_off(mc, monkeypatch):
    monkeypatch.setattr(mc, "_DEBUG_LOGGING", False)
    monkeypatch.setattr(mc, "_log", lambda m, file=None: None)
    monkeypatch.setattr(mc, "_preview", lambda *a, **k: pytest.fail("preview built with debug logging off"))
    client = mc.CentralCoreClient({"client_id": "demo-home-001", "mqtt_host": "broker"})
    client._client = types.SimpleNamespace(publish=lambda *a, **k: types.SimpleNamespace(rc=0))
    client._submit = lambda fn, *a: None
    msg = types.SimpleNamespace(topic="hubs/demo-home-001/v1/cmd/x/y", payload=b"{}", retain=False)
    client.on_message(None, None, msg)
    client._publish("hubs/demo-home-001/v1/telemetry/system", "{}")


def test_a_pem_block_cut_off_by_the_limit_is_still_redacted(mc):
    pem = "-----BEGIN PRIVATE KEY-----\n" + "A" * 2000 + "\n-----END PRIVATE KEY-----"
    out = mc._preview("cert " + pem, limit=100)
    assert "AAAA" not in out
    assert out.startswith("cert [PEM REDACTED]")


def test_large_non_json_input_is_cheap(mc, monkeypatch):
    """The scrub runs only on the cut preview and is linear: a 60 KB message full
    of quotes takes milliseconds, not seconds, even on the paho thread of a small hub."""
    import time as _t

    nasty = ('"' + "a" * 50 + '" ' + "'b' : ") * 1200  # ~ 60 KB, many quotes, never valid JSON
    start = _t.perf_counter()
    for _ in range(20):
        mc._preview(nasty)
    assert (_t.perf_counter() - start) / 20 < 0.02
    # the regex itself is linear on long input too (in case someone raises the limit)
    start = _t.perf_counter()
    mc._QUOTED_FIELD_RE.sub(mc._redact_field, nasty[:40_000])
    assert _t.perf_counter() - start < 0.5


def test_deeply_nested_json_does_not_break_the_preview(mc):
    deep = "[" * 100_000 + "]" * 100_000
    out = mc._preview(deep, limit=50)
    assert out.startswith("[[[[") and "chars)" in out


# --- JSON inside JSON (a payload that is itself a JSON-encoded string) ---


def test_double_encoded_json_is_redacted(mc):
    inner = json.dumps({"token": SECRET, "entries": []})
    out = mc._preview(json.dumps(inner))  # "{\"token\": \"...\"}"
    assert SECRET not in out
    assert "[REDACTED]" in out and "entries" in out


def test_a_field_holding_json_is_redacted(mc):
    body = json.dumps({"command_id": "r1", "payload": json.dumps({"password": SECRET, "x": 1})})
    out = mc._preview(body)
    assert SECRET not in out and "[REDACTED]" in out and "r1" in out


@pytest.mark.parametrize(
    "text",
    [
        '"{\\"token\\": \\"%s\\", \\"entries\\": [' % SECRET,  # double-encoded and cut off
        '{\\"api_key\\":\\"%s\\"}' % SECRET,  # escaped quotes, not valid JSON
        '{\\"token\\": \\"%s' % SECRET,  # escaped and cut inside the secret
        '"{\\"secret\\": \\"a\\\\\\\\%s\\"}' % SECRET,  # a backslash inside the escaped value
    ],
)
def test_escaped_quotes_in_broken_text_are_scrubbed(mc, text):
    out = mc._preview(text)
    assert SECRET not in out
    assert "[REDACTED]" in out


def test_ordinary_strings_are_left_alone(mc):
    assert mc._preview(json.dumps("just text")) == '"just text"'
    assert mc._preview(json.dumps("[not json")) == '"[not json"'


def test_json_nested_three_deep_stops_unwrapping_safely(mc):
    level3 = json.dumps(json.dumps(json.dumps({"token": SECRET})))
    out = mc._preview(level3)
    assert SECRET not in out  # the text pass still catches the escaped key


def test_triple_escaped_broken_text_is_scrubbed(mc):
    text = json.dumps(json.dumps(json.dumps({"token": SECRET, "more": "x" * 50})))[:-20]  # not valid JSON
    out = mc._preview(text, limit=10_000)
    assert SECRET not in out and "[REDACTED]" in out


def test_long_runs_of_backslashes_stay_cheap(mc):
    import time as _t

    nasty = ('\\\\' * 50 + '"tok' + '\\\\' * 50 + '": ') * 300
    start = _t.perf_counter()
    mc._QUOTED_FIELD_RE.sub(mc._redact_field, nasty)
    assert _t.perf_counter() - start < 0.5


@pytest.mark.parametrize("body", [
    {"username": "hub-demo-home-001", "password": SECRET},
    {"command_id": "c1", "payload": {"login": {"username": "u", "password": SECRET}}},
    {"previous": {"username": "u", "mqtt_password": SECRET}, "confirm_key": "ok"},
])
def test_a_broker_login_never_reaches_the_log(mc, body):
    """login_move.py handles passwords; if one is ever put in a payload the preview blanks it."""
    out = mc._preview(json.dumps(body))
    assert SECRET not in out and "[REDACTED]" in out
    assert SECRET not in mc._preview(json.dumps({"inner": json.dumps(body)}))
