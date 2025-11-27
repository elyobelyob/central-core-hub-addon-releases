import json
import importlib
import importlib.util
import sys
from pathlib import Path
import types
from typing import Any, cast


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    return mod


def test_on_message_delegates_to_handlers_module():
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient

    called = []

    # create a fake handlers module in sys.modules so `from handlers import` succeeds
    def fake_handle(
        client,
        msg,
        payload,
        fetch_sensors,
        build_telemetry,
        build_vault_payload,
        requests,
    ):
        called.append((msg.topic, payload))

    fake_mod = types.ModuleType("handlers")
    cast(Any, fake_mod).handle_message = fake_handle
    cast(Any, fake_mod).handle_message_alias = fake_handle
    sys.modules["handlers"] = fake_mod

    c = CentralCoreClient({"client_id": "unit-handle"})

    class Msg:
        topic = f"hubs/{c.client_id}/v1/cmd/sensors/poll"
        payload = b"{}"

    c.on_message(None, None, Msg())
    assert called, "handlers.handle_message was not called"


def test_build_telemetry_wrapper_uses_monkeypatched_get_cpu(monkeypatch):
    mod = _load_client_module()
    # monkeypatch the module-level get_cpu_percent to return a known value
    monkeypatch.setattr(mod, "get_cpu_percent", lambda: 42)
    raw = mod.build_telemetry("cid-test")
    data = json.loads(raw)
    # telemetry should include cpu_percent and reflect patched value
    assert data.get("cpu_percent") == 42


def test_run_finally_calls_loop_stop_and_disconnect(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "unit-run"})

    flags = {"stopped": False, "disconnected": False}

    class ClientShim:
        def loop_stop(self):
            flags["stopped"] = True

        def disconnect(self):
            flags["disconnected"] = True

    c._client = ClientShim()

    # make connect a no-op and run_iteration raise to hit finally
    c.connect = lambda: True

    def bad_iteration():
        raise KeyboardInterrupt()

    c.run_iteration = bad_iteration

    try:
        c.run()
    except KeyboardInterrupt:
        # expected
        pass

    assert flags["stopped"] is True and flags["disconnected"] is True


def test_publish_telemetry_vault_transform_exception_fallback(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    options = {"client_id": "unit-vault", "vault_topic": "vault/unit"}
    c = CentralCoreClient(options)

    published = []

    class PubClient:
        def publish(self, topic, payload, qos=0):
            published.append((topic, payload, qos))

            class R:
                rc = 0

            return R()

    c._client = PubClient()

    # stub telemetry builder: telemetry returns 'raw'
    monkeypatch.setattr(mod, "build_telemetry", lambda cid, **kwargs: "raw-payload")

    # Case A: vault transform returns None -> fallback publish expected
    published.clear()
    monkeypatch.setattr(mod, "build_vault_payload", lambda raw: None)
    c.publish_telemetry()
    topics = [t for (t, p, q) in published]
    assert c.telemetry_topic in topics
    assert c.vault_topic in topics

    # Case B: vault transform raises -> no vault publish and error path exercised
    published.clear()
    monkeypatch.setattr(
        mod,
        "build_vault_payload",
        lambda raw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    c.publish_telemetry()
    topics = [t for (t, p, q) in published]
    # only telemetry should be published
    assert c.telemetry_topic in topics
    assert c.vault_topic not in topics


def test_build_telemetry_wrapper_cleans_up(monkeypatch):
    mod = _load_client_module()
    # ensure telemetry module is loaded from file path
    repo_root = Path(__file__).resolve().parents[3]
    tele_path = repo_root / "central-core-hub" / "telemetry.py"
    spec = importlib.util.spec_from_file_location("telemetry", tele_path)
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    tele = importlib.util.module_from_spec(spec)
    tloader = spec.loader
    assert tloader is not None
    tloader.exec_module(tele)
    # ensure no external override exists before call
    if hasattr(tele, "_external_get_cpu_percent"):
        delattr(cast(Any, tele), "_external_get_cpu_percent")

    # monkeypatch mqtt_client.get_cpu_percent so wrapper will attempt to set it
    cast(Any, mod).get_cpu_percent = lambda: 77
    # call build_telemetry (wrapper should set and then remove attribute)
    raw = mod.build_telemetry("wrap-test")
    assert isinstance(raw, str)
    # attribute should not remain on telemetry module
    assert not hasattr(tele, "_external_get_cpu_percent")


def test_init_prefers_local_mqtt_runtime_import(monkeypatch):
    # load mqtt_runtime into sys.modules under the name 'mqtt_runtime'
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_runtime.py"
    spec = importlib.util.spec_from_file_location("mqtt_runtime", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    rt = importlib.util.module_from_spec(spec)
    rloader = spec.loader
    assert rloader is not None
    rloader.exec_module(rt)
    sys.modules["mqtt_runtime"] = rt

    # Now instantiate CentralCoreClient; it should import mqtt_runtime directly
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "use-local-rt"})
    # the runtime module should have attached a _client attribute
    assert hasattr(c, "_client")


def test_wait_for_connected_timeout_and_on_disconnect():
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "wait-test"})
    # ensure not connected
    c._connected = False
    assert c.wait_for_connected(timeout=0.5) is False

    # on_disconnect should set connected False
    c._connected = True
    c.on_disconnect(None, None, 0)
    assert c._connected is False


def test_run_iteration_reconnects_and_calls_publish(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    c = CentralCoreClient({"client_id": "ri-test"})

    called = {"connect": 0, "telemetry": 0, "sensors": 0}

    def fake_connect():
        called["connect"] += 1
        c._connected = True

    def fake_telemetry():
        called["telemetry"] += 1

    def fake_sensors():
        called["sensors"] += 1

    c.connect = fake_connect
    c.publish_telemetry = fake_telemetry
    c.publish_sensors = fake_sensors
    c._connected = False
    c._last_sensors_sent = 0
    # should call connect then telemetry and sensors
    c.run_iteration()
    assert called["connect"] >= 1
    assert called["telemetry"] == 1
    assert called["sensors"] == 1


def test_on_message_handles_binary_payload_and_calls_handler():
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    called = []

    fake_mod = types.ModuleType("handlers")
    cast(Any, fake_mod).handle_message = lambda *a, **k: called.append(True)
    sys.modules["handlers"] = fake_mod

    c = CentralCoreClient({"client_id": "bin-test"})

    class BadPayload:
        def decode(self, enc="utf-8", errors="replace"):
            raise RuntimeError("bad")

    class Msg:
        topic = f"hubs/{c.client_id}/v1/cmd/sensors/poll"
        payload = BadPayload()

    c.on_message(None, None, Msg())
    assert called, "handler not invoked for binary payload"
