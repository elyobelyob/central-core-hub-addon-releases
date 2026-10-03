"""Edge behaviour of mqtt_runtime client setup, mqtt_topics defaults,
privacy fail-closed inputs and the vault telemetry payload."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

import mqtt_runtime
import privacy
import telemetry

_HUB = Path(__file__).resolve().parents[2]


class _Ctx:
    client_id = "hub-1"
    mqtt_username = None
    mqtt_tls = False
    status_offline_topic = "hubs/hub-1/v1/status/offline"

    def on_connect(self, *a):
        pass

    def on_disconnect(self, *a):
        pass

    def on_message(self, *a):
        pass


# --- mqtt_runtime: paho Client signature fallbacks ---------------------------


def _mod_accepting(accepted):
    """A fake paho module whose Client only accepts the keyword set `accepted`."""

    class Client:
        made_with = None

        def __init__(self, **kw):
            if set(kw) != accepted:
                raise TypeError(f"unexpected {sorted(kw)}")
            self.kw = kw

    return type("FakePaho", (), {"Client": Client})


@pytest.mark.parametrize(
    "accepted",
    [{"client_id", "clean_session"}, {"client_id"}, set()],
    ids=["no-callback-api", "no-clean-session", "no-arguments"],
)
def test_client_falls_back_to_older_paho_signatures(accepted):
    mod = _mod_accepting(accepted)
    mod.CallbackAPIVersion = type("V", (), {"VERSION2": 2})
    ctx = _Ctx()
    client = mqtt_runtime.setup_mqtt_client(ctx, mod) or ctx._client
    assert set(client.kw) == accepted
    if "client_id" in accepted:
        assert client.kw["client_id"] == "hub-1"
    assert ctx._client.on_message == ctx.on_message


class _FlakyClient:
    def __init__(self, **kw):
        self.on_connect = self.on_disconnect = self.on_message = None

    def will_set(self, *a, **k):
        raise ValueError("payload too large")

    def reconnect_delay_set(self, **k):
        raise RuntimeError("not supported")


def test_last_will_and_backoff_failures_are_not_fatal(capsys):
    ctx = _Ctx()
    mqtt_runtime.setup_mqtt_client(ctx, type("P", (), {"Client": _FlakyClient}))
    assert isinstance(ctx._client, _FlakyClient)
    assert ctx._tls_error is None
    assert "Could not set MQTT Last Will: payload too large" in capsys.readouterr().err
    assert ctx._client.on_connect == ctx.on_connect  # callbacks still attached


# --- mqtt_topics -------------------------------------------------------------


def test_topics_use_defaults_when_shared_package_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "central_core_mqtt_shared", None)  # import raises ImportError
    spec = importlib.util.spec_from_file_location("mqtt_topics_missing", str(_HUB / "mqtt_topics.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._shared is None
    assert mod.CMD_SUB_TMPL == "hubs/{client_id}/v1/cmd/+"
    assert mod.TELEMETRY_TOPIC_TMPL == "telemetry/{client_id}"


# --- privacy: malformed input denies, never allows ---------------------------


@pytest.mark.parametrize("entries", ["sensor.a", {"entity_id": "sensor.a"}, 5])
def test_registry_with_non_list_entries_denies_everything(entries):
    allowed, problem = privacy.registry_rule({"registry_mode": "all", "entries": entries})
    assert allowed("sensor.a") is False
    assert "not a list" in problem


@pytest.mark.parametrize("device", [None, "mobile_app", ["mobile_app", "x"], 1])
def test_non_dict_device_is_not_a_phone(device):
    assert privacy.is_phone_device(device) is False


def test_phone_entities_skips_malformed_entities():
    devices = [{"id": "p1", "identifiers": [["mobile_app", "abc"]]}]
    entities = ["sensor.x", None, {"ei": "sensor.p1_battery", "di": "p1"}, {"ei": 7, "di": "p1"}]
    assert privacy.phone_entities(devices, entities) == {"sensor.p1_battery"}


@pytest.mark.phone_guard
def test_phone_guard_treats_a_crashing_read_as_unknown_and_backs_off():
    calls = []
    now = [0.0]

    def listener():
        calls.append(1)
        raise RuntimeError("socket closed")

    guard = privacy.PhoneGuard(listener, retry=30.0, clock=lambda: now[0])
    assert guard.excluded() is None  # unknown phone set: callers send nothing
    now[0] = 10.0
    assert guard.excluded() is None
    assert len(calls) == 1  # backing off: no second read within `retry`
    now[0] = 31.0
    guard.excluded()
    assert len(calls) == 2


# --- telemetry: vault payload --------------------------------------------------


def test_vault_payload_takes_ha_version_from_plain_string():
    raw = json.dumps({"client_id": "h", "home_assistant": "2026.9.4"})
    out = json.loads(telemetry.build_vault_payload(raw))
    assert out["home_assistant"] == "2026.9.4"
    assert out["ha_version"] == "2026.9.4"


def test_vault_payload_rejects_invalid_json():
    assert telemetry.build_vault_payload("{nope") is None


def test_telemetry_without_core_version_has_no_ha_version():
    out = json.loads(telemetry.build_telemetry("h", home_assistant={"supervisor": "2026.9.0"},
                                               uptime_fn=lambda: 1, loadavg_fn=lambda: [0.1],
                                               mem_info_fn=lambda: (1, 1), disk_info_fn=lambda: (1, 1),
                                               get_cpu_percent=lambda: 1.0))
    assert out["home_assistant"] == {"supervisor": "2026.9.0"}
    assert "ha_version" not in out


def test_malformed_registry_entries_are_skipped_not_trusted():
    doc = {"registry_mode": "allow", "entries": ["sensor.a", {"entity_id": 5, "provide": True},
                                                 {"entity_id": "sensor.b", "provide": True}]}
    allowed, problem = privacy.registry_rule(doc)
    assert problem is None
    assert allowed("sensor.b") is True
    assert allowed("sensor.a") is False
