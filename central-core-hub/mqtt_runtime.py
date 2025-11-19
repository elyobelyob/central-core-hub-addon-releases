#!/usr/bin/env python3
"""
Small helper module to create and configure an MQTT client for
`CentralCoreClient`. This isolates TLS/configuration and the
client shim so it can be unit-tested independently.
"""
import sys
import traceback
from datetime import datetime, timezone


def _log(msg, file=sys.stdout):
    """Log a message with UTC timestamp."""
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    print(f"[{ts}] {msg}", file=file)


def setup_mqtt_client(ctx, mqtt_mod):
    """Create and configure `ctx._client` based on attributes on `ctx`.

    Args:
        ctx: instance of CentralCoreClient (expects attributes like
             client_id, mqtt_username, mqtt_password, mqtt_tls, etc.)
        mqtt_mod: the `paho.mqtt.client` module or None. Passing the
                  module in avoids import-time failures in tests.
    Returns:
        The configured client object (or shim) assigned to `ctx._client`.
    """
    if mqtt_mod is None:

        class _ClientShim:
            def __init__(self, *a, **k):
                pass

            def username_pw_set(self, u, p=None):
                return None

            def tls_set(self, **kw):
                return None

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

        ctx._client = _ClientShim()  # pragma: no cover
    else:
        # Create the real paho client and apply username/password if present
        try:
            ctx._client = mqtt_mod.Client(client_id=ctx.client_id, clean_session=True)
        except TypeError:
            try:
                ctx._client = mqtt_mod.Client(client_id=ctx.client_id)
            except TypeError:
                ctx._client = mqtt_mod.Client()
        if getattr(ctx, "mqtt_username", None):
            ctx._client.username_pw_set(ctx.mqtt_username, ctx.mqtt_password)

    # TLS configuration (best-effort)
    if getattr(ctx, "mqtt_tls", False):
        tls_kwargs = {}
        if getattr(ctx, "mqtt_ca", None):
            tls_kwargs["ca_certs"] = ctx.mqtt_ca
        if getattr(ctx, "mqtt_cert", None) and getattr(ctx, "mqtt_key", None):
            tls_kwargs["certfile"] = ctx.mqtt_cert
            tls_kwargs["keyfile"] = ctx.mqtt_key
        try:  # pragma: no cover
            # Some clients (shim) may not implement tls_set; ignore failures
            ctx._client.tls_set(**tls_kwargs)
        except Exception:
            try:
                _log("Failed to configure TLS for MQTT", sys.stderr)
            except Exception:
                pass  # pragma: no cover

    # Attach callbacks if present on the context
    try:  # pragma: no cover
        ctx._client.on_connect = ctx.on_connect
        ctx._client.on_disconnect = ctx.on_disconnect
        ctx._client.on_message = ctx.on_message
    except Exception:
        traceback.print_exc()  # pragma: no cover

    return ctx._client
