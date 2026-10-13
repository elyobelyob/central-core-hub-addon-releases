"""The subscription id is known before the request leaves.

Home Assistant answers a subscribe_entities request with its snapshot at once.
The reader thread keeps only events whose id equals the live subscription id,
so if the id was stored after the send, a fast snapshot was dropped and
ha_streaming stayed false until the next reconnect.
"""

import json

import ha_client


def _listener(selectors):
    listener = ha_client.HAWebSocketListener(
        "http://localhost:8123", "tok", on_event=lambda *a: None, selectors=selectors
    )
    listener._authed = True
    return listener


class WS:
    """Records the subscription id the listener holds at the moment each request is sent."""

    def __init__(self, listener):
        self.listener = listener
        self.seen = []

    def send(self, data):
        msg = json.loads(data)
        self.seen.append((msg["type"], msg["id"], self.listener._sub_id))


def test_the_subscription_id_is_stored_before_subscribe_entities_is_sent():
    listener = _listener(["binary_sensor.demo_door"])
    listener._ws = ws = WS(listener)
    listener._subscribe()
    kind, sent_id, held_id = ws.seen[-1]
    assert kind == "subscribe_entities"
    assert held_id == sent_id == listener._sub_id


def test_changing_the_selection_while_connected_resubscribes_with_the_new_id():
    listener = _listener(["binary_sensor.demo_door"])
    listener._ws = ws = WS(listener)
    listener._subscribe()
    first = listener._sub_id
    listener.update_selectors(["binary_sensor.demo_door", "binary_sensor.demo_hall"])
    kinds = [k for k, _, _ in ws.seen]
    assert kinds == ["subscribe_entities", "unsubscribe_events", "subscribe_entities"]
    kind, sent_id, held_id = ws.seen[-1]
    assert held_id == sent_id == listener._sub_id != first


def test_a_snapshot_arriving_during_the_send_marks_the_listener_streaming():
    listener = _listener(["binary_sensor.demo_door"])

    class FastWS(WS):
        def send(self, data):
            super().send(data)
            msg = json.loads(data)
            if msg["type"] == "subscribe_entities" and msg["id"] == listener._sub_id:
                listener._handle_entities_event({"a": {"binary_sensor.demo_door": {"s": "off"}}})

    listener._ws = FastWS(listener)
    listener._subscribe()
    assert listener.is_streaming()


def test_a_failed_send_leaves_no_subscription_id():
    listener = _listener(["binary_sensor.demo_door"])

    class Broken:
        def send(self, data):
            raise ConnectionError("down")

    listener._ws = Broken()
    listener._subscribe()
    assert listener._sub_id is None and not listener._streaming.is_set()
