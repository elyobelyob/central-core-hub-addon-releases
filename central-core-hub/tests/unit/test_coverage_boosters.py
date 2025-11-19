import json
import types
import importlib.util
from pathlib import Path

def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_options_reads_file(tmp_path, monkeypatch):
    mod = _load_client_module()
    # write a temporary options file and point OPTIONS_PATH at it
    p = tmp_path / "options.json"
    p.write_text(json.dumps({"mqtt_host": "example"}))
    monkeypatch.setattr(mod, "OPTIONS_PATH", str(p))
    opts = mod.load_options()
    assert isinstance(opts, dict)
    assert opts.get("mqtt_host") == "example"


def test_load_options_invalid_json(tmp_path, monkeypatch):
    mod = _load_client_module()
    p = tmp_path / "options.json"
    p.write_text("{invalid")
    monkeypatch.setattr(mod, "OPTIONS_PATH", str(p))
    opts = mod.load_options()
    assert opts == {}


def test_read_proc_stat_and_cpu_percent(monkeypatch):
    mod = _load_client_module()

    # Create a side-effecting _read_proc_stat that returns two different values
    calls = {"n": 0}

    def fake_read():
        calls["n"] += 1
        if calls["n"] == 1:
            return 100, 400
        return 120, 500

    monkeypatch.setattr(mod, "_read_proc_stat", fake_read)
    val = mod.get_cpu_percent()
    assert val is None or isinstance(val, float)

    # also test when _read_proc_stat returns None
    def fake_none():
        return None, None

    monkeypatch.setattr(mod, "_read_proc_stat", fake_none)
    assert mod.get_cpu_percent() is None


def test_fetch_sensors_error_paths(monkeypatch):
    mod = _load_client_module()

    # requests unavailable
    monkeypatch.setattr(mod, "requests", None)
    assert mod.fetch_sensors("http://x", "tok") is None

    # requests.get raises
    class Bad:
        @staticmethod
        def get(url, headers=None, timeout=10):
            raise RuntimeError("fail")

    monkeypatch.setattr(mod, "requests", Bad)
    assert mod.fetch_sensors("http://x", "tok") is None


def test_mqtt_shim_and_tls_exception(monkeypatch):
    mod = _load_client_module()

    # Simulate no paho available -> shim should be used
    monkeypatch.setattr(mod, "mqtt", None)
    c = mod.CentralCoreClient({"client_id": "u1"})
    assert hasattr(c._client, "publish")
    r = c._client.publish("t", "p", qos=0)
    assert hasattr(r, "rc")

    # Now simulate a paho.Client whose tls_set raises
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def username_pw_set(self, u, p=None):
            return None

        def tls_set(self, **kw):
            raise RuntimeError("tls fail")

        def publish(self, topic, payload, qos=0):
            class R:
                rc = 0

            return R()

        def subscribe(self, topic, qos=0):
            return (0, 1)

        def connect(self, *a, **k):
            return 0

        def loop_start(self):
            return None

        def loop_stop(self):
            return None

        def disconnect(self):
            return None

    fake_mqtt = types.SimpleNamespace(Client=FakeClient)
    monkeypatch.setattr(mod, "mqtt", fake_mqtt)
    # enable tls to hit tls_set path
    c2 = mod.CentralCoreClient(
        {"client_id": "u2", "mqtt_tls": True, "mqtt_ca_cert": "x"}
    )
    # should have created _client even if tls_set failed
    assert hasattr(c2, "_client")
