import importlib.util
import pathlib
import json
import builtins


def _load_ha_client():
    base = pathlib.Path(__file__).parents[2]
    src = base / "ha_client.py"
    spec = importlib.util.spec_from_file_location("ha_client", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load ha_client spec")
    spec.loader.exec_module(mod)
    return mod


ha_client = _load_ha_client()


def test_ws_url_variants():
    listener_empty = ha_client.HAWebSocketListener("", "tok", None)
    assert listener_empty._ws_url() is None
    listener_http = ha_client.HAWebSocketListener("http://host.local", "tok", None)
    assert listener_http._ws_url().startswith("ws://host.local")
    listener_https = ha_client.HAWebSocketListener("https://host.local/", "tok", None)
    assert listener_https._ws_url().startswith("wss://host.local")


def test_send_json_swallows_exceptions(monkeypatch):
    class BadSock:
        def send(self, _):
            raise Exception("boom")

    listener = ha_client.HAWebSocketListener("http://ha", "tok", None)
    # ensure no exception raised
    listener._send_json(BadSock(), {"x": 1})


def test_persist_ha_version_write_failure(monkeypatch, tmp_path):
    # create a file with non-dict JSON so code treats opts as {}
    opts = tmp_path / "opts.json"
    opts.write_text(json.dumps([]))

    # patch OPTIONS_PATH to point to our file
    monkeypatch.setattr(ha_client, "OPTIONS_PATH", str(opts))

    original_open = builtins.open

    def open_no_write(path, mode="r", *a, **k):
        if "w" in mode:
            raise Exception("no write")
        return original_open(path, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", open_no_write)

    listener = ha_client.HAWebSocketListener("http://ha", "tok", None)
    # when write fails, _persist_ha_version should return False
    assert not listener._persist_ha_version("1.2.3")
