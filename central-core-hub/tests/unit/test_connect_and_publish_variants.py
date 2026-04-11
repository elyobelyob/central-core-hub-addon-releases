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
    loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_connect_retries_then_succeeds(monkeypatch):
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({"client_id": "conn-test"})

    calls = {"n": 0}

    def fake_connect_once():
        calls["n"] += 1
        # first call fails, second succeeds
        return calls["n"] >= 2

    monkeypatch.setattr(c, "connect_once", fake_connect_once)
    # avoid sleeping delays from _stop_event.wait(timeout=5)
    monkeypatch.setattr(c._stop_event, "wait", lambda timeout=None: None)
    # once connect_once returns True, wait_for_connected should succeed
    monkeypatch.setattr(c, "wait_for_connected", lambda timeout=5: True)

    res = c.connect()
    assert res is True
    assert calls["n"] >= 2


def test__publish_returns_object_without_rc_attribute():
    mc = _load_module()
    CentralCoreClient = mc.CentralCoreClient
    c = CentralCoreClient({"client_id": "pub-obj"})

    class NoRc:
        pass

    nr = NoRc()

    class PubClient:
        def publish(self, topic, payload, qos=0):
            return nr

    c._client = PubClient()
    res = c._publish("topic", "payload", qos=0)
    assert res is nr
