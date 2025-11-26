import sys
import time
import types
import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_shim(connect_ok=True, publish_ok=True):
    class Shim:
        def __init__(self):
            self.started = False

        def username_pw_set(self, u, p=None):
            return None

        def tls_set(self, **kw):
            return None

        def publish(self, topic, payload, qos=0):
            class R:
                rc = 0

            if not publish_ok:
                raise RuntimeError("publish failed")
            return R()

        def subscribe(self, topic, qos=0):
            return (0, 1)

        def connect(self, *a, **k):
            if not connect_ok:
                raise RuntimeError("connect fail")
            return 0

        def loop_start(self):
            self.started = True

        def loop_stop(self):
            self.started = False

        def disconnect(self):
            return None

    return Shim()


def test_exercise_mqtt_client_branches(monkeypatch):
    mc = _load_module()

    # instantiate with minimal options
    opts = {"client_id": "unit-test-client"}
    c = mc.CentralCoreClient(opts)

    # Replace client with a shim that fails connect to hit exception path
    c._client = make_shim(connect_ok=False)
    assert not c.connect_once()

    # Now a shim that connects
    c._client = make_shim(connect_ok=True)
    assert c.connect_once()

    # wait_for_connected: false then true
    c._connected = False
    assert c.wait_for_connected(timeout=0.1) is False
    c._connected = True
    assert c.wait_for_connected(timeout=0.1) is True

    # Test publish_telemetry vault branches
    c.vault_topic = "vault/topic"

    # Case: build_vault_payload raises -> should be caught
    monkeypatch.setattr(
        mc,
        "build_vault_payload",
        lambda raw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    # ensure _publish works
    c._client = make_shim(publish_ok=True)
    c.publish_telemetry()

    # Case: build_vault_payload returns None -> fallback branch
    monkeypatch.setattr(mc, "build_vault_payload", lambda raw: None)
    c.publish_telemetry()

    # Case: build_vault_payload returns bytes/string -> normal
    monkeypatch.setattr(mc, "build_vault_payload", lambda raw: "v")
    c.publish_telemetry()

    # publish_sensors: no HA configured -> early return
    c.ha_api_url = ""
    c.ha_api_token = ""
    c.publish_sensors()  # should simply return

    # Now configure HA and simulate fetch_sensors returning a list
    c.ha_api_url = "http://ha"
    c.ha_api_token = "tok"
    monkeypatch.setattr(
        mc,
        "fetch_sensors",
        lambda u, t: [
            {"entity_id": "sensor.foo", "state": "1", "name": "foo", "attributes": {}}
        ],
    )
    c._client = make_shim(publish_ok=True)
    c.publish_sensors()

    # on_message: simulate handlers import and handle_message raising
    msg = types.SimpleNamespace(topic="hubs/unit/v1/cmd/sensors/poll", payload=b"{}")

    # Insert a fake handlers module into sys.modules with a handle_message that raises
    fake_handlers = types.ModuleType("handlers")

    def fake_handle_message(*a, **k):
        raise RuntimeError("handler boom")

    fake_handlers.handle_message = fake_handle_message
    sys.modules["handlers"] = fake_handlers

    # Should not raise despite handler raising (on_message guards exceptions)
    c.on_message(None, None, msg)

    # run_iteration: cover reconnect branch and telemetry/sensors exception handling
    # Make publish_telemetry raise
    def bad_pub():
        raise RuntimeError("telemetry fail")

    monkeypatch.setattr(c, "publish_telemetry", bad_pub)

    # Make publish_sensors raise when called
    def bad_sensors():
        raise RuntimeError("sensors fail")

    monkeypatch.setattr(c, "publish_sensors", bad_sensors)

    # Ensure not connected so reconnect is attempted; monkeypatch connect to set connected
    c._connected = False

    def fake_connect():
        c._connected = True

    monkeypatch.setattr(c, "connect", fake_connect)

    # Force last sensors sent to long ago to trigger sensors path
    c._last_sensors_sent = int(time.time()) - 3600 - 10
    c.run_iteration()
