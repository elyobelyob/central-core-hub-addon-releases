"""sensors/set must only ever change the watch list; it never writes to Home Assistant.

The vault sends `{"sensors": ["sensor.a", ...]}` (a list of entity ids). Any
other shape used to be turned into POST /api/states/<id> calls with the admin
token, and `<id>` could be `../services/...`.
"""

import json
import types

import pytest

import ha_client
import handlers


def _mc():
    """The mqtt_client module handlers will import right now (tests may swap it)."""
    import importlib

    return importlib.import_module("mqtt_client")


class _Resp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class _RecordingRequests:
    """Fake `requests` that records every call and fails the test on a write."""

    def __init__(self, states=None):
        self.calls = []
        self.states = states or {}

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url))
        ent = url.rsplit("/api/states/", 1)[-1]
        if ent in self.states:
            return _Resp(self.states[ent])
        return _Resp({}, status=404)

    def post(self, url, *a, **k):  # pragma: no cover - must never be called
        self.calls.append(("POST", url))
        raise AssertionError(f"hub must not POST to Home Assistant: {url}")


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(_mc(), "SELECTED_SENSORS_FILE", tmp_path / "sel.json")
    published = []

    c = types.SimpleNamespace(
        client_id="hub1",
        ha_api_url="http://ha:8123",
        ha_api_token="tok",
        selected_sensors=[],
        preferred_sensors_topic="hubs/hub1/v1/telemetry/sensors",
    )
    c.build_ack_topic = lambda action, cid: f"hubs/hub1/v1/ack/{action.replace('/', '.')}/{cid}"
    c._publish = lambda topic, payload, qos=0: published.append((topic, json.loads(payload)))
    return c, published


def _states_fetcher(req):
    """A fetch_sensors stand-in backed by the recording fake: returns every known state."""

    def fetch(url, token):
        return [dict(v) for v in req.states.values()]

    return fetch


def _send(c, payload, req):
    msg = types.SimpleNamespace(topic="hubs/hub1/v1/cmd/sensors/set", retain=False)
    body = json.dumps({"command_id": "c1", "action": "sensors/set", "payload": payload})
    handlers.handle_message(c, msg, body, _states_fetcher(req), None, None, req)


@pytest.mark.parametrize(
    "payload",
    [
        {"sensors": {"../services/script/unlock_front_door": "x"}},
        {"sensors": {"lock.front_door": "unlocked"}},
        {"sensors": [{"entity_id": "../services/script/turn_on", "state": "x"}]},
        {"sensors": [{"entity_id": "sensor.a", "state": "1"}]},
    ],
)
def test_state_writing_forms_are_rejected(tmp_path, monkeypatch, payload):
    c, published = _client(tmp_path, monkeypatch)
    req = _RecordingRequests()
    _send(c, payload, req)
    assert not any(method == "POST" for method, _ in req.calls)
    assert req.calls == []
    assert c.selected_sensors == []
    final = [p for t, p in published if t.endswith("/c1") and p["status"] != "acknowledged"]
    assert final and final[-1]["status"] == "failed"
    assert final[-1]["result"]["reason"] == "invalid_payload"


@pytest.mark.parametrize(
    "bad",
    [
        "../services/script/turn_on",
        "sensor.a/../../services/x",
        "sensor.a?x=1",
        "sensor.a#frag",
        "Sensor.Upper",
        "sensor",
        "sensor.",
        ".a",
        "sensor.a b",
        "sensor.a%2f..",
        "",
    ],
)
def test_invalid_entity_ids_are_refused(tmp_path, monkeypatch, bad):
    c, published = _client(tmp_path, monkeypatch)
    req = _RecordingRequests({"sensor.ok": {"entity_id": "sensor.ok", "state": "1", "attributes": {}}})
    _send(c, {"sensors": ["sensor.ok", bad]}, req)
    # sensors/set never builds a per-entity Home Assistant URL
    assert req.calls == []
    assert c.selected_sensors == ["sensor.ok"]
    done = [p for t, p in published if t.endswith("/c1") and p["status"] == "completed"][-1]
    assert done["result"]["sensors_reported"] == ["sensor.ok"]
    assert bad in done["result"]["rejected"]


def test_valid_list_selects_and_reports(tmp_path, monkeypatch):
    c, published = _client(tmp_path, monkeypatch)
    req = _RecordingRequests(
        {
            "sensor.temp": {"entity_id": "sensor.temp", "state": "21", "attributes": {"friendly_name": "T"}},
            "binary_sensor.door": {"entity_id": "binary_sensor.door", "state": "off", "attributes": {}},
        }
    )
    _send(c, {"sensors": ["sensor.temp", "binary_sensor.door", "sensor.gone"]}, req)
    assert c.selected_sensors == ["sensor.temp", "binary_sensor.door", "sensor.gone"]
    done = [p for t, p in published if t.endswith("/c1") and p["status"] == "completed"][-1]
    assert sorted(done["result"]["sensors_reported"]) == ["binary_sensor.door", "sensor.temp"]
    assert "rejected" not in done["result"]
    assert json.loads((tmp_path / "sel.json").read_text()) == c.selected_sensors
    assert done["result"]["names"]["sensor.temp"] == "T"
    assert req.calls == []


def test_empty_list_clears_selection(tmp_path, monkeypatch):
    c, published = _client(tmp_path, monkeypatch)
    c.selected_sensors = ["sensor.a"]
    _send(c, {"sensors": []}, _RecordingRequests())
    assert c.selected_sensors == []
    done = [p for t, p in published if t.endswith("/c1") and p["status"] == "completed"][-1]
    assert done["result"]["selected"] == []


@pytest.mark.parametrize(
    "ent,ok",
    [
        ("sensor.temp", True),
        ("binary_sensor.front_door_2", True),
        ("sensor.a.b", False),
        ("../x", False),
        ("sensor/x", False),
        ("SENSOR.X", False),
        ("sensor." + "a" * 300, False),
        (None, False),
        (123, False),
    ],
)
def test_is_valid_entity_id(ent, ok):
    assert ha_client.is_valid_entity_id(ent) is ok


def test_fetch_by_ids_skips_invalid_ids():
    req = _RecordingRequests({"sensor.ok": {"entity_id": "sensor.ok", "state": "1", "attributes": {}}})
    out = ha_client.fetch_sensors_by_ids(
        "http://ha", "tok", ["../services/x", "sensor.ok", "sensor.ok/../../x"], requests_mod=req
    )
    assert [s["entity_id"] for s in out] == ["sensor.ok"]
    assert [u for _, u in req.calls] == ["http://ha/api/states/sensor.ok"]
