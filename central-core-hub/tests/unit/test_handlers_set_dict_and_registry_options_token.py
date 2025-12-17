import importlib.util
import pathlib
import json
import sys
import types


def _load_handlers():
    base = pathlib.Path(__file__).parents[2]
    src = base / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load handlers spec")
    spec.loader.exec_module(mod)
    return mod


handlers = _load_handlers()


class DummyClient:
    def __init__(self, client_id="cid"):
        self.client_id = client_id
        self.published = []
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.ha_readback_after_set = False
        self.preferred_sensors_topic = "pref/topic"
        self.vault_topic = "vault/topic"

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


class _FakeResp:
    def __init__(self, data=None):
        self._data = data or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_sensors_set_accepts_dict_mapping_and_publishes_completion():
    client = DummyClient("unit-dict")
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps({"command_id": "d1", "payload": {"sensors": {"sensor.a": "on"}}})

    class FakeReq:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            return _FakeResp({})

    handlers.handle_message(client, Msg(topic), payload, None, None, None, requests=FakeReq)

    comp = None
    for t, p, qos in client.published:
        try:
            o = json.loads(p)
        except Exception:
            continue
        if o.get("status") == "completed":
            comp = o
            break
    assert comp is not None
    res = comp.get("result") or {}
    # results may be in result['set'] or detailed data_map - accept presence of entity
    found = False
    if isinstance(res.get("set"), list):
        found = "sensor.a" in res.get("set")
    if not found and isinstance(res.get("data"), dict):
        found = "sensor.a" in res.get("data")
    assert found


def test_registry_set_with_options_registryToken_writes_file_and_reloads(tmp_path):
    # prepare fake mqtt_client module with SENSOR_REGISTRY path and reload helper
    mc = types.ModuleType("mqtt_client")
    target = tmp_path / "SENSOR_REGISTRY.json"
    mc.SENSOR_REGISTRY = str(target)

    def _reload():
        mc._reloaded = True

    mc.reload_sensor_registry = _reload
    orig = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = mc

    try:
        client = DummyClient("unit-reg2")
        # place token under 'registryToken' in options to cover that key
        client.options = {"registryToken": "opt-secret"}

        topic = f"hubs/{client.client_id}/v1/cmd/registry/set"
        payload = json.dumps({"command_id": "r2", "payload": {"token": "opt-secret", "entries": []}})

        handlers.handle_message(client, Msg(topic), payload, None, None, None)

        # ensure file written and reload called
        assert target.exists()
        assert getattr(mc, "_reloaded", False) is True

        # completion ack indicates success
        comp = None
        for t, p, qos in client.published:
            try:
                o = json.loads(p)
            except Exception:
                continue
            if o.get("status") == "completed":
                comp = o
                break
        assert comp is not None
        assert comp.get("result", {}).get("success") is True
    finally:
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig
