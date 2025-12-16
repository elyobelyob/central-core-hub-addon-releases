import importlib.util
from pathlib import Path


def _load_client_module():
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


def test_trigger_addon_update_calls_ha_services(monkeypatch):
    mod = _load_client_module()
    c = mod.CentralCoreClient({"client_id": "unit-hub"})

    calls = []

    class FakeListener:
        def call_service(self, domain, service, service_data=None, timeout=15.0):
            calls.append((domain, service, service_data))
            return {"domain": domain, "service": service}

    c._ha_ws_listener = FakeListener()
    monkeypatch.setattr(c, "_resolve_addon_slug", lambda: "central-core-hub")

    result = c.trigger_addon_update()
    assert result["success"] is True
    assert len(calls) >= 2
    assert calls[0][1].endswith("check_addon_updates")
    assert calls[1][1].endswith("addon_update")
    # Verify no version was passed (defaults to latest)
    assert "version" not in calls[1][2] or calls[1][2].get("version") is None


def test_trigger_addon_update_with_specific_version(monkeypatch):
    """Test upgrading addon (version parameter removed - vault handles versioning)."""
    mod = _load_client_module()
    c = mod.CentralCoreClient({"client_id": "unit-hub"})

    calls = []

    class FakeListener:
        def call_service(self, domain, service, service_data=None, timeout=15.0):
            calls.append((domain, service, service_data))
            return {"domain": domain, "service": service}

    c._ha_ws_listener = FakeListener()
    monkeypatch.setattr(c, "_resolve_addon_slug", lambda: "central-core-hub")

    result = c.trigger_addon_update()
    assert result["success"] is True
    assert len(calls) >= 2
    assert calls[0][1].endswith("check_addon_updates")
    assert calls[1][1].endswith("addon_update")


def test_trigger_addon_update_with_latest_keyword(monkeypatch):
    """Test upgrading addon to latest (version parameter removed)."""
    mod = _load_client_module()
    c = mod.CentralCoreClient({"client_id": "unit-hub"})

    calls = []

    class FakeListener:
        def call_service(self, domain, service, service_data=None, timeout=15.0):
            calls.append((domain, service, service_data))
            return {"domain": domain, "service": service}

    c._ha_ws_listener = FakeListener()
    monkeypatch.setattr(c, "_resolve_addon_slug", lambda: "central-core-hub")

    result = c.trigger_addon_update()
    assert result["success"] is True
    # Addon update always goes to latest
    assert "version" not in calls[1][2] or calls[1][2].get("version") is None
