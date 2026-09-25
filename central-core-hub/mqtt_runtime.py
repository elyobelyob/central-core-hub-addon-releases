#!/usr/bin/env python3
"""
Small helper module to create and configure an MQTT client for
`CentralCoreClient`. This isolates TLS/configuration and the
client shim so it can be unit-tested independently.
"""

import json
import sys
import time
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
            # declare callback attributes so assignment is allowed by type
            # checkers and editors (e.g., on_connect/on_disconnect/on_message)
            on_connect = None
            on_disconnect = None
            on_message = None

            def __init__(self, *a, **k):
                # initialize instance-level attributes
                self.on_connect = None
                self.on_disconnect = None
                self.on_message = None

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

        ctx._client = _ClientShim()
    else:
        # Create the real paho client and apply username/password if present
        try:
            if hasattr(mqtt_mod, "CallbackAPIVersion"):
                ctx._client = mqtt_mod.Client(
                    client_id=ctx.client_id,
                    clean_session=True,
                    callback_api_version=mqtt_mod.CallbackAPIVersion.VERSION2,
                )
            else:
                ctx._client = mqtt_mod.Client(client_id=ctx.client_id, clean_session=True)
        except TypeError:
            try:
                ctx._client = mqtt_mod.Client(client_id=ctx.client_id, clean_session=True)
            except TypeError:
                try:
                    ctx._client = mqtt_mod.Client(client_id=ctx.client_id)
                except TypeError:
                    ctx._client = mqtt_mod.Client()
        if getattr(ctx, "mqtt_username", None):
            ctx._client.username_pw_set(ctx.mqtt_username, ctx.mqtt_password)

    # TLS configuration. This fails closed: if TLS is enabled and cannot be
    # set up, ctx._tls_error is set and the client refuses to connect rather
    # than falling back to plaintext.
    ctx._tls_error = None
    if getattr(ctx, "mqtt_tls", False):
        tls_kwargs = {}
        if getattr(ctx, "mqtt_ca", None):
            tls_kwargs["ca_certs"] = ctx.mqtt_ca
        if getattr(ctx, "mqtt_cert", None) and getattr(ctx, "mqtt_key", None):
            tls_kwargs["certfile"] = ctx.mqtt_cert
            tls_kwargs["keyfile"] = ctx.mqtt_key
        try:
            ctx._client.tls_set(**tls_kwargs)
        except Exception as exc:
            ctx._tls_error = f"{type(exc).__name__}: {exc}"
            _log(f"Failed to configure TLS for MQTT ({ctx._tls_error}); not connecting without TLS", sys.stderr)

    # Last Will: the broker publishes this if the hub drops off without a
    # clean disconnect. Shape of the shared StatusOffline schema; the vault
    # subscribes to status/offline at QoS 1. Not retained, so a vault that
    # restarts does not see a stale "offline" for a hub that is back.
    will_topic = getattr(ctx, "status_offline_topic", None)
    will_set = getattr(ctx._client, "will_set", None)
    if will_topic and callable(will_set):
        try:
            will_set(
                will_topic,
                payload=json.dumps({"status": "offline", "timestamp": time.time()}),
                qos=1,
                retain=False,
            )
        except Exception as exc:
            _log(f"Could not set MQTT Last Will: {exc}", sys.stderr)
    # After the first connection paho's network loop reconnects by itself;
    # back off from 1 s up to 2 minutes instead of retrying at a fixed rate.
    delay_set = getattr(ctx._client, "reconnect_delay_set", None)
    if callable(delay_set):
        try:
            delay_set(min_delay=1, max_delay=120)
        except Exception:
            pass

    # Attach callbacks if present on the context
    try:
        ctx._client.on_connect = ctx.on_connect
        ctx._client.on_disconnect = ctx.on_disconnect
        ctx._client.on_message = ctx.on_message
    except Exception:  # pragma: no cover - assignment may fail on exotic clients
        traceback.print_exc()

    return ctx._client
