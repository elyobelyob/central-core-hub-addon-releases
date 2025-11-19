import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / 'central-core-hub' / 'mqtt_client.py'
    spec = importlib.util.spec_from_file_location('mqtt_client', str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_connect_handles_timeout_and_retries(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({'client_id': 'timeout-test'})

    calls = {'connect_once': 0, 'wait_for_connected': 0, 'loop_stop': 0}

    def fake_connect_once():
        calls['connect_once'] += 1
        return True

    # first wait_for_connected returns False (timeout), then True
    def fake_wait_for_connected(timeout=5):
        calls['wait_for_connected'] += 1
        return calls['wait_for_connected'] >= 2

    class ClientShim:
        def loop_stop(self):
            calls['loop_stop'] += 1

    c._client = ClientShim()
    monkeypatch.setattr(c, 'connect_once', fake_connect_once)
    monkeypatch.setattr(c, 'wait_for_connected', fake_wait_for_connected)
    # avoid sleeping
    monkeypatch.setattr(mc.time, 'sleep', lambda s: None)

    # connect should eventually return True after retry
    assert c.connect() is True
    assert calls['connect_once'] >= 1
    assert calls['wait_for_connected'] >= 2
    assert calls['loop_stop'] >= 1


def test_connect_reports_failed_then_succeeds(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({'client_id': 'conn-fail'})

    seq = {'n': 0}

    def fake_connect_once():
        seq['n'] += 1
        # first call fails, second succeeds
        return seq['n'] >= 2

    monkeypatch.setattr(c, 'connect_once', fake_connect_once)
    monkeypatch.setattr(c, 'wait_for_connected', lambda timeout=5: True)
    monkeypatch.setattr(mc.time, 'sleep', lambda s: None)

    assert c.connect() is True
    assert seq['n'] >= 2


def test_on_disconnect_sets_connected_false():
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({'client_id': 'disc1'})
    c._connected = True
    c.on_disconnect(None, None, 123)
    assert c._connected is False


def test_run_iteration_attempts_reconnect_and_handles_exceptions(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({'client_id': 'runit'})

    called = {'connect': 0, 'publish_telemetry': 0}

    def fake_connect():
        called['connect'] += 1
        c._connected = True

    def bad_telemetry():
        called['publish_telemetry'] += 1
        raise RuntimeError('telemetry boom')

    monkeypatch.setattr(c, 'connect', fake_connect)
    monkeypatch.setattr(c, 'publish_telemetry', bad_telemetry)

    # ensure sensors path does not raise (last_sensors_sent recent)
    c._last_sensors_sent = int(mc.time.time())
    c._connected = False

    # should not raise despite publish_telemetry raising
    c.run_iteration()
    assert called['connect'] >= 1
    assert called['publish_telemetry'] >= 1


def test_publish_telemetry_handles_publish_exception(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({'client_id': 'pub-ex'})

    def bad_publish(topic, payload, qos=0):
        raise RuntimeError('boom')

    # monkeypatch _publish to raise and ensure publish_telemetry handles it
    monkeypatch.setattr(c, '_publish', bad_publish)
    # also ensure build_telemetry exists
    monkeypatch.setattr(mc, 'build_telemetry', lambda cid: 'x')

    # should not raise
    c.publish_telemetry()
