import json
import json
from pathlib import Path
import importlib.util
import time


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / 'central-core-hub' / 'mqtt_client.py'
    spec = importlib.util.spec_from_file_location('mqtt_client', str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        # record a tuple; mimic paho return
        self.published.append({'topic': topic, 'payload': payload, 'qos': qos})
        class R:
            rc = 0
        return R()


class DummyMsg:
    def __init__(self, topic, payload_bytes):
        self.topic = topic
        self.payload = payload_bytes


def test_publish_sensors_calls_publish_and_updates_timestamp(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    # stub fetch_sensors to return sample sensors
    sample = [
        {'entity_id': 'sensor.temp', 'state': '21.5', 'attributes': {'friendly_name': 'Temp'}},
        {'entity_id': 'sensor.hum', 'state': '42', 'attributes': {'friendly_name': 'Humidity'}},
    ]
    monkeypatch.setattr(mod, 'fetch_sensors', lambda url, token: sample)

    options = {'client_id': 'unit-hub', 'ha_api_url': 'http://ha', 'ha_api_token': 'tok'}
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    assert c._last_sensors_sent == 0
    c.publish_sensors()
    # ensure preferred topic was published (legacy topics are not used in dev)
    topics = [p['topic'] for p in dummy.published]
    assert c.preferred_sensors_topic in topics
    # payloads are JSON; check structure: publish_sensors uses a 'sensors' list
    payload = json.loads(next(p['payload'] for p in dummy.published if p['topic'] == c.preferred_sensors_topic))
    assert 'sensors' in payload and 'timestamp' in payload
    # sensors list contains entries with entity_id
    ids = [s.get('entity_id') for s in payload['sensors']]
    assert 'sensor.temp' in ids
    assert c._last_sensors_sent > 0


def test_handle_sensors_poll_command_ack_and_completion(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    # stub fetch_sensors
    sample = [
        {'entity_id': 'sensor.temp', 'state': '21.5', 'attributes': {'friendly_name': 'Temp'}},
    ]
    monkeypatch.setattr(mod, 'fetch_sensors', lambda url, token: sample)

    options = {'client_id': 'unit-hub', 'ha_api_url': 'http://ha', 'ha_api_token': 'tok'}
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy

    command = {
        'command_id': 'abc123',
        'action': 'sensors/poll',
        'payload': {}
    }
    topic = f"hubs/{c.client_id}/cmd/sensors/poll"
    msg = DummyMsg(topic, json.dumps(command).encode('utf-8'))

    c.on_message(None, None, msg)

    # Verify ACK, telemetry (preferred), and completion were published
    topics = [p['topic'] for p in dummy.published]
    ack_topic = f"hubs/{c.client_id}/cmd/{command['command_id']}/response"
    assert ack_topic in topics
    assert c.preferred_sensors_topic in topics
    # completion should also be on ack_topic (another message with qos=1)
    completions = [p for p in dummy.published if p['topic'] == ack_topic]
    # there should be at least two publishes to ack_topic (ack + completion)
    assert len(completions) >= 2
    # check that telemetry payload contains reported sensor
    tele_payload = json.loads(next(p['payload'] for p in dummy.published if p['topic'] == c.preferred_sensors_topic))
    assert 'data' in tele_payload and 'sensor.temp' in tele_payload['data']


def test_handle_sensors_set_command_calls_ha_and_responds(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    # capture posts
    posts = []

    class FakeResp:
        def raise_for_status(self):
            return None

    def fake_post(url, headers=None, json=None, timeout=10):
        posts.append({'url': url, 'headers': headers, 'json': json})
        return FakeResp()

    monkeypatch.setattr(mod, 'requests', type('R', (), {'post': staticmethod(fake_post)}))

    options = {'client_id': 'unit-hub', 'ha_api_url': 'http://ha', 'ha_api_token': 'tok'}
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy

    command = {
        'command_id': 'set123',
        'action': 'sensors/set',
        'payload': {
            'sensors': [
                {'entity_id': 'sensor.temp', 'state': '22.0'},
                {'entity_id': 'sensor.hum', 'state': '43'}
            ]
        }
    }
    topic = f"hubs/{c.client_id}/cmd/sensors/set"
    msg = DummyMsg(topic, json.dumps(command).encode('utf-8'))

    c.on_message(None, None, msg)

    # requests.post should be called for each sensor
    assert len(posts) == 2
    assert posts[0]['url'].endswith('/api/states/sensor.temp')
    assert posts[1]['url'].endswith('/api/states/sensor.hum')

    # ACK and completion should be published to response topic
    ack_topic = f"hubs/{c.client_id}/cmd/{command['command_id']}/response"
    topics = [p['topic'] for p in dummy.published]
    assert ack_topic in topics
    completions = [p for p in dummy.published if p['topic'] == ack_topic]
    assert len(completions) >= 2
    # completion payload contains result.summary
    comp = json.loads(completions[-1]['payload'])
    assert 'result' in comp and 'set' in comp['result']