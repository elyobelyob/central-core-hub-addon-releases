"""Tests for central-core-hub/mqtt_runtime.py.

Covers setup_mqtt_client: the shim path, real paho client creation,
TLS configuration, and callback attachment.
"""

import importlib.util
import pathlib
import types
from unittest.mock import MagicMock


def _load_module():
    base = pathlib.Path(__file__).resolve().parents[2] / "central-core-hub"
    spec = importlib.util.spec_from_file_location("mqtt_runtime", str(base / "mqtt_runtime.py"))
    if spec is None or spec.loader is None:
        raise ImportError("could not load mqtt_runtime")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rt = _load_module()


def _make_ctx(**kwargs):
    """Build a minimal context object for setup_mqtt_client."""
    ctx = types.SimpleNamespace(
        client_id="test-hub",
        mqtt_username=None,
        mqtt_password=None,
        mqtt_tls=False,
        mqtt_ca=None,
        mqtt_cert=None,
        mqtt_key=None,
        on_connect=MagicMock(),
        on_disconnect=MagicMock(),
        on_message=MagicMock(),
        _client=None,
    )
    for k, v in kwargs.items():
        setattr(ctx, k, v)
    return ctx


# ---------------------------------------------------------------------------
# Shim path (mqtt_mod=None)
# ---------------------------------------------------------------------------

class TestShimPath:
    def test_returns_shim_client_when_no_mqtt_mod(self):
        ctx = _make_ctx()
        client = rt.setup_mqtt_client(ctx, None)
        assert client is ctx._client

    def test_shim_is_assigned_to_ctx(self):
        ctx = _make_ctx()
        rt.setup_mqtt_client(ctx, None)
        assert ctx._client is not None

    def test_shim_has_required_methods(self):
        ctx = _make_ctx()
        rt.setup_mqtt_client(ctx, None)
        for method in ("username_pw_set", "tls_set", "publish", "subscribe",
                       "connect", "loop_start", "loop_stop", "disconnect"):
            assert callable(getattr(ctx._client, method)), f"shim missing {method}"

    def test_shim_publish_returns_rc_zero(self):
        ctx = _make_ctx()
        rt.setup_mqtt_client(ctx, None)
        result = ctx._client.publish("topic", "payload")
        assert result.rc == 0

    def test_shim_subscribe_returns_tuple(self):
        ctx = _make_ctx()
        rt.setup_mqtt_client(ctx, None)
        result = ctx._client.subscribe("topic")
        assert isinstance(result, tuple)

    def test_shim_callbacks_attached(self):
        ctx = _make_ctx()
        rt.setup_mqtt_client(ctx, None)
        assert ctx._client.on_connect is ctx.on_connect
        assert ctx._client.on_disconnect is ctx.on_disconnect
        assert ctx._client.on_message is ctx.on_message


# ---------------------------------------------------------------------------
# Real paho client path
# ---------------------------------------------------------------------------

class TestRealClientPath:
    def _make_mqtt_mod(self, has_callback_api=True):
        """Create a fake paho mqtt module."""
        mock_client_instance = MagicMock()
        mqtt_mod = MagicMock()
        mqtt_mod.Client.return_value = mock_client_instance
        if has_callback_api:
            mqtt_mod.CallbackAPIVersion = MagicMock()
            mqtt_mod.CallbackAPIVersion.VERSION2 = "v2"
        else:
            del mqtt_mod.CallbackAPIVersion
        return mqtt_mod, mock_client_instance

    def test_real_client_is_created(self):
        ctx = _make_ctx()
        mqtt_mod, client_instance = self._make_mqtt_mod()
        rt.setup_mqtt_client(ctx, mqtt_mod)
        assert ctx._client is client_instance

    def test_client_created_with_client_id(self):
        ctx = _make_ctx(client_id="hub-xyz")
        mqtt_mod, _ = self._make_mqtt_mod()
        rt.setup_mqtt_client(ctx, mqtt_mod)
        call_kwargs = mqtt_mod.Client.call_args
        assert call_kwargs.kwargs.get("client_id") == "hub-xyz" or \
               (call_kwargs.args and "hub-xyz" in call_kwargs.args)

    def test_username_password_set_when_provided(self):
        ctx = _make_ctx(mqtt_username="user", mqtt_password="pass")
        mqtt_mod, client_instance = self._make_mqtt_mod()
        rt.setup_mqtt_client(ctx, mqtt_mod)
        client_instance.username_pw_set.assert_called_once_with("user", "pass")

    def test_username_password_not_set_when_absent(self):
        ctx = _make_ctx(mqtt_username=None)
        mqtt_mod, client_instance = self._make_mqtt_mod()
        rt.setup_mqtt_client(ctx, mqtt_mod)
        client_instance.username_pw_set.assert_not_called()

    def test_callbacks_attached_to_real_client(self):
        ctx = _make_ctx()
        mqtt_mod, client_instance = self._make_mqtt_mod()
        rt.setup_mqtt_client(ctx, mqtt_mod)
        assert client_instance.on_connect == ctx.on_connect
        assert client_instance.on_disconnect == ctx.on_disconnect
        assert client_instance.on_message == ctx.on_message

    def test_falls_back_when_callback_api_version_missing(self):
        ctx = _make_ctx()
        _, client_instance = self._make_mqtt_mod(has_callback_api=False)
        # Use a plain SimpleNamespace so hasattr returns False for missing attrs
        import types as _t
        real_mod = _t.SimpleNamespace()
        real_mod.Client = MagicMock(return_value=client_instance)
        rt.setup_mqtt_client(ctx, real_mod)
        assert ctx._client is client_instance


# ---------------------------------------------------------------------------
# TLS configuration
# ---------------------------------------------------------------------------

class TestTlsConfiguration:
    def test_tls_set_called_when_tls_enabled(self):
        ctx = _make_ctx(mqtt_tls=True)
        mqtt_mod, client_instance = MagicMock(), MagicMock()
        mqtt_mod.Client.return_value = client_instance
        mqtt_mod.CallbackAPIVersion = MagicMock()
        mqtt_mod.CallbackAPIVersion.VERSION2 = "v2"
        rt.setup_mqtt_client(ctx, mqtt_mod)
        client_instance.tls_set.assert_called_once()

    def test_tls_set_not_called_when_tls_disabled(self):
        ctx = _make_ctx(mqtt_tls=False)
        mqtt_mod, client_instance = MagicMock(), MagicMock()
        mqtt_mod.Client.return_value = client_instance
        mqtt_mod.CallbackAPIVersion = MagicMock()
        mqtt_mod.CallbackAPIVersion.VERSION2 = "v2"
        rt.setup_mqtt_client(ctx, mqtt_mod)
        client_instance.tls_set.assert_not_called()

    def test_tls_set_with_ca_cert(self):
        ctx = _make_ctx(mqtt_tls=True, mqtt_ca="/path/to/ca.crt")
        mqtt_mod, client_instance = MagicMock(), MagicMock()
        mqtt_mod.Client.return_value = client_instance
        mqtt_mod.CallbackAPIVersion = MagicMock()
        mqtt_mod.CallbackAPIVersion.VERSION2 = "v2"
        rt.setup_mqtt_client(ctx, mqtt_mod)
        call_kwargs = client_instance.tls_set.call_args.kwargs
        assert call_kwargs.get("ca_certs") == "/path/to/ca.crt"

    def test_tls_set_with_cert_and_key(self):
        ctx = _make_ctx(mqtt_tls=True, mqtt_cert="/c.pem", mqtt_key="/k.pem")
        mqtt_mod, client_instance = MagicMock(), MagicMock()
        mqtt_mod.Client.return_value = client_instance
        mqtt_mod.CallbackAPIVersion = MagicMock()
        mqtt_mod.CallbackAPIVersion.VERSION2 = "v2"
        rt.setup_mqtt_client(ctx, mqtt_mod)
        call_kwargs = client_instance.tls_set.call_args.kwargs
        assert call_kwargs.get("certfile") == "/c.pem"
        assert call_kwargs.get("keyfile") == "/k.pem"

    def test_tls_with_no_ca_no_cert_calls_tls_set_empty(self):
        ctx = _make_ctx(mqtt_tls=True, mqtt_ca=None, mqtt_cert=None, mqtt_key=None)
        mqtt_mod, client_instance = MagicMock(), MagicMock()
        mqtt_mod.Client.return_value = client_instance
        mqtt_mod.CallbackAPIVersion = MagicMock()
        mqtt_mod.CallbackAPIVersion.VERSION2 = "v2"
        rt.setup_mqtt_client(ctx, mqtt_mod)
        client_instance.tls_set.assert_called_once_with()

    def test_tls_enabled_on_shim_does_not_raise(self):
        ctx = _make_ctx(mqtt_tls=True, mqtt_ca="/ca.crt")
        # shim's tls_set is a no-op; should not raise
        client = rt.setup_mqtt_client(ctx, None)
        assert client is not None


# ---------------------------------------------------------------------------
# _log helper
# ---------------------------------------------------------------------------

class TestLog:
    def test_log_outputs_timestamp_and_message(self):
        import io
        buf = io.StringIO()
        rt._log("hello world", file=buf)
        assert "hello world" in buf.getvalue()

    def test_log_output_contains_timestamp(self):
        import io
        buf = io.StringIO()
        rt._log("test message", file=buf)
        out = buf.getvalue()
        assert "[" in out and "T" in out
