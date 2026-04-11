import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_connect_loop_reports_connect_failed(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({"client_id": "loop-fail"})

    # connect_once returns False to trigger 'MQTT connect failed' branch
    call_count = [0]

    def once():
        call_count[0] += 1
        if call_count[0] >= 2:
            c._stop_event.set()
        return False

    monkeypatch.setattr(c, "connect_once", once)
    # make wait return immediately
    monkeypatch.setattr(c._stop_event, "wait", lambda timeout=None: None)

    c.connect()
    assert call_count[0] >= 1


def test_connect_loop_reports_timed_out(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({"client_id": "loop-timeout"})

    # connect_once returns True, but wait_for_connected returns False to hit timeout branch
    monkeypatch.setattr(c, "connect_once", lambda: True)
    monkeypatch.setattr(c, "wait_for_connected", lambda timeout=5: False)

    # ensure loop_stop exists
    class ClientShim:
        def loop_stop(self):
            return None

    c._client = ClientShim()
    # Set stop event so loop exits after first iteration
    c._stop_event.set()

    c.connect()


def test_publish_sensors_handles_publish_exception(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({"client_id": "pub-ex", "ha_api_url": "http://ha", "ha_api_token": "t"})

    # fetch_sensors returns a list
    monkeypatch.setattr(
        mc,
        "fetch_sensors",
        lambda u, t, s=None: [{"entity_id": "sensor.z", "state": "1", "name": "z", "attributes": {}}],
    )

    # make _publish raise to hit exception path in publish_sensors
    def bad_pub(topic, payload, qos=0):
        raise RuntimeError("boom")

    monkeypatch.setattr(c, "_publish", bad_pub)

    # should not raise
    c.publish_sensors()
