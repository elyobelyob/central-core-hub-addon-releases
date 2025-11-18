#!/usr/bin/env python3
"""
Simple resilient MQTT client using paho-mqtt for the Central Core Hub add-on.

Responsibilities:
- Read options from `/data/options.json` (Home Assistant add-on options)
- Maintain a single persistent MQTT connection
- Publish telemetry every 30s to `telemetry/{client_id}`
- Subscribe to `hubs/{client_id}/commands` and print received commands
- Reconnect automatically and log connection lifecycle to stdout
"""
import json
import os
import socket
import sys
import time
import traceback
import platform
try:
    import requests
except Exception:
    requests = None
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
except Exception:
    # Do not raise during import so unit tests can import this module
    # in environments where `paho-mqtt` isn't installed. The runtime
    # CentralCoreClient will require a working `paho-mqtt` installation
    # if it is instantiated.
    print("paho-mqtt not installed; MQTT functionality disabled for import-time", file=sys.stderr)
    mqtt = None

OPTIONS_PATH = '/data/options.json'

def load_options():
    if not os.path.exists(OPTIONS_PATH):
        return {}
    with open(OPTIONS_PATH, 'r') as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def uptime_seconds():
    try:
        with open('/proc/uptime', 'r') as f:
            return int(float(f.readline().split()[0]))
    except Exception:
        return None

def loadavg():
    try:
        with open('/proc/loadavg', 'r') as f:
            parts = f.readline().split()
            return parts[0:3]
    except Exception:
        return []

def mem_info_kb():
    try:
        m = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    m[parts[0].rstrip(':')] = int(parts[1])
        return m.get('MemTotal'), m.get('MemFree')
    except Exception:
        return None, None

def disk_info_kb(path='/'):
    try:
        st = os.statvfs(path)
        total = (st.f_blocks * st.f_frsize) // 1024
        free = (st.f_bavail * st.f_frsize) // 1024
        return total, free
    except Exception:
        return None, None

def build_telemetry(client_id):
    hostname = socket.gethostname()
    ip = 'unknown'
    try:
        # try to get primary IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    up = uptime_seconds()
    la = loadavg()
    mem_total, mem_free = mem_info_kb()
    disk_total, disk_free = disk_info_kb('/')
    # CPU info
    cpu_count = os.cpu_count() or 1
    cpu_percent = get_cpu_percent()
    py_version = sys.version.split('\n')[0]
    platform_info = platform.platform()
    payload = {
        'schema_version': 1,
        'client_id': client_id,
        'status': 'online',
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'hostname': hostname,
        'ip': ip,
        'uptime': up,
        'load_avg': la,
        'mem_total_kb': mem_total,
        'mem_free_kb': mem_free,
        'disk_total_kb': disk_total,
        'disk_free_kb': disk_free,
        'cpu_count': cpu_count,
        'cpu_percent': cpu_percent,
        'platform': platform_info,
        'python_version': py_version,
    }
    return json.dumps(payload)


def build_vault_payload(raw_payload_json):
    """Transform the standard telemetry payload into a compact Vault-friendly payload.

    This produces a simplified structure with a `schema_version` so Vault can
    evolve independently. We keep the original telemetry payload intact and
    publish a transformed version to `vault_topic` when configured.
    """
    try:
        data = json.loads(raw_payload_json)
    except Exception:
        return None

    # Build a compact metrics object with key metrics consumers usually want
    metrics = {}
    for k in ('cpu_count', 'cpu_percent', 'uptime', 'mem_total_kb', 'mem_free_kb', 'disk_total_kb', 'disk_free_kb'):
        if k in data:
            metrics[k] = data.get(k)

    vault = {
        'schema_version': 2,
        'id': data.get('client_id'),
        'ts': data.get('timestamp'),
        'host': data.get('hostname'),
        'ip': data.get('ip'),
        'metrics': metrics,
    }
    return json.dumps(vault)


def _read_proc_stat():
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
            if not line.startswith('cpu '):
                return None, None
            parts = line.split()[1:]
            vals = [int(x) for x in parts]
            idle = vals[3]
            total = sum(vals)
            return idle, total
    except Exception:
        return None, None


def get_cpu_percent():
    # Simple /proc/stat based CPU percentage over short interval
    idle1, total1 = _read_proc_stat()
    if idle1 is None:
        return None
    time.sleep(0.1)
    idle2, total2 = _read_proc_stat()
    if idle2 is None or total2 is None or total2 == total1:
        return None
    idle_delta = idle2 - idle1
    total_delta = total2 - total1
    try:
        usage = (1.0 - (idle_delta / total_delta)) * 100.0
        return round(usage, 1)
    except Exception:
        return None


def fetch_sensors(ha_api_url, ha_api_token):
    if not ha_api_url or not ha_api_token or requests is None:
        return None
    try:
        url = ha_api_url.rstrip('/') + '/api/states'
        headers = {
            'Authorization': f'Bearer {ha_api_token}',
            'Content-Type': 'application/json'
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        sensors = []
        for ent in data:
            ent_id = ent.get('entity_id')
            if ent_id and ent_id.startswith('sensor.'):
                sensors.append({
                    'entity_id': ent_id,
                    'state': ent.get('state'),
                    'name': ent.get('attributes', {}).get('friendly_name') or ent_id
                })
        return sensors
    except Exception:
        return None


class CentralCoreClient:
    def __init__(self, options):
        self.options = options
        self.mqtt_host = options.get('mqtt_host') or os.environ.get('MQTT_HOST', '')
        self.mqtt_port = int(options.get('mqtt_port') or os.environ.get('MQTT_PORT', 1883))
        self.mqtt_username = options.get('mqtt_username') or ''
        self.mqtt_password = options.get('mqtt_password') or ''
        self.mqtt_tls = bool(options.get('mqtt_tls'))
        self.mqtt_ca = options.get('mqtt_ca_cert') or ''
        self.mqtt_cert = options.get('mqtt_client_cert') or ''
        self.mqtt_key = options.get('mqtt_client_key') or ''
        self.client_id = options.get('client_id') or socket.gethostname().lower().replace(' ', '-')
        self.ha_api_url = options.get('ha_api_url') or ''
        self.ha_api_token = options.get('ha_api_token') or ''
        # Optional vault-compatible topic to publish telemetry to in addition
        # to the default `telemetry/{client_id}` topic. If set, telemetry
        # payloads will be published to both topics.
        self.vault_topic = options.get('vault_topic') or ''
        self.telemetry_topic = f"telemetry/{self.client_id}"
        self.commands_topic = f"hubs/{self.client_id}/commands"
        # Preferred sensors telemetry topic for Vault
        self.preferred_sensors_topic = f"hubs/{self.client_id}/telemetry/sensors"
        # Legacy sensors topic (kept for backward compatibility)
        self.sensors_topic = f"telemetry/{self.client_id}/sensors"
        # Subscribe pattern for Vault commands (e.g. hubs/<hub_id>/cmd/sensors/poll)
        self.cmd_sub_topic = f"hubs/{self.client_id}/cmd/+"
        self._client = mqtt.Client(client_id=self.client_id, clean_session=True)
        if self.mqtt_username:
            self._client.username_pw_set(self.mqtt_username, self.mqtt_password)
        if self.mqtt_tls:
            tls_kwargs = {}
            if self.mqtt_ca:
                tls_kwargs['ca_certs'] = self.mqtt_ca
            if self.mqtt_cert and self.mqtt_key:
                tls_kwargs['certfile'] = self.mqtt_cert
                tls_kwargs['keyfile'] = self.mqtt_key
            # paho expects tls_set mostly; we rely on defaults for cert requirements
            try:
                self._client.tls_set(**tls_kwargs)
            except Exception:
                print('Failed to configure TLS for MQTT', file=sys.stderr)

        self._client.on_connect = self.on_connect
        self._client.on_disconnect = self.on_disconnect
        self._client.on_message = self.on_message

        self._connected = False
        # track last sensors publish time (epoch seconds)
        self._last_sensors_sent = 0

    def on_connect(self, client, userdata, flags, rc):
        print(f"{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} Connected to MQTT broker with rc={rc}")
        try:
            # Legacy subscription kept for older integrations
            client.subscribe(self.commands_topic)
            print(f"Subscribed to {self.commands_topic}")
            # Subscribe to Vault command pattern with QoS=1
            client.subscribe(self.cmd_sub_topic, qos=1)
            print(f"Subscribed to {self.cmd_sub_topic} (Vault command pattern)")
        except Exception:
            print('Subscription failed', file=sys.stderr)
        self._connected = True
        # Publish sensors list immediately on startup/connection
        try:
            self.publish_sensors()
        except Exception:
            # do not let sensor publish failures prevent client
            print('Failed to publish sensors on connect', file=sys.stderr)

    def on_disconnect(self, client, userdata, rc):
        print(f"{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} Disconnected from MQTT broker rc={rc}")
        self._connected = False

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8', errors='replace')
        except Exception:
            payload = '<binary>'
        print(f"Received message on {msg.topic}: {payload}")

        # Handle Vault-style sensors/poll commands
        try:
            topic = msg.topic
            # sensors poll command path: hubs/<hub_id>/cmd/sensors/poll
            expected_cmd_topic = f"hubs/{self.client_id}/cmd/sensors/poll"
            if topic == expected_cmd_topic:
                # Parse JSON payload
                try:
                    cmd = json.loads(payload) if payload and payload != '<binary>' else {}
                except Exception:
                    cmd = {}

                command_id = cmd.get('command_id')
                # Acknowledge immediately if we have a command_id
                if command_id:
                    ack_topic = f"hubs/{self.client_id}/cmd/{command_id}/response"
                    ack_payload = {
                        'status': 'acknowledged',
                        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                    }
                    try:
                        self._client.publish(ack_topic, json.dumps(ack_payload), qos=1)
                        print(f"Published ACK to {ack_topic}")
                    except Exception:
                        print(f"Failed to publish ACK to {ack_topic}", file=sys.stderr)

                # Determine sensors to fetch (empty -> full report)
                sensors_requested = None
                try:
                    if isinstance(cmd.get('payload'), dict):
                        srv = cmd.get('payload').get('sensors')
                        if isinstance(srv, list):
                            sensors_requested = srv
                except Exception:
                    sensors_requested = None

                # Fetch sensors from Home Assistant (if configured)
                sensors = fetch_sensors(self.ha_api_url, self.ha_api_token) or []
                # Filter if specific sensors requested
                if sensors_requested:
                    sensors = [s for s in sensors if s.get('entity_id') in sensors_requested]

                # Build telemetry payload (wrapper style recommended)
                data_map = {}
                for s in sensors:
                    ent = s.get('entity_id')
                    st = s.get('state')
                    # Try to coerce numeric/bool values
                    val = st
                    try:
                        if isinstance(st, str):
                            low = st.lower()
                            if low in ('on', 'true'):
                                val = True
                            elif low in ('off', 'false'):
                                val = False
                            else:
                                if '.' in st:
                                    val = float(st)
                                else:
                                    val = int(st)
                    except Exception:
                        val = st
                    data_map[ent] = val

                now_iso = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                telemetry_payload = {
                    'data': data_map,
                    'timestamp': now_iso
                }

                # Publish to preferred Vault topic (QoS 0) and also to legacy topic
                try:
                    self._client.publish(self.preferred_sensors_topic, json.dumps(telemetry_payload), qos=0)
                    print(f"Published sensors telemetry to {self.preferred_sensors_topic} (count={len(data_map)})")
                except Exception:
                    print(f"Failed to publish sensors to {self.preferred_sensors_topic}", file=sys.stderr)
                try:
                    self._client.publish(self.sensors_topic, json.dumps(telemetry_payload), qos=0)
                    print(f"Published sensors telemetry to legacy {self.sensors_topic} (count={len(data_map)})")
                except Exception:
                    print(f"Failed to publish sensors to legacy {self.sensors_topic}", file=sys.stderr)

                # Optionally send completion response with summary
                if command_id:
                    comp_topic = f"hubs/{self.client_id}/cmd/{command_id}/response"
                    comp_payload = {
                        'status': 'completed',
                        'result': {'sensors_reported': list(data_map.keys()), 'count': len(data_map)},
                        'timestamp': now_iso
                    }
                    try:
                        self._client.publish(comp_topic, json.dumps(comp_payload), qos=1)
                        print(f"Published completion to {comp_topic}")
                    except Exception:
                        print(f"Failed to publish completion to {comp_topic}", file=sys.stderr)
                return
        except Exception:
            # fall through to generic message logging
            traceback.print_exc()

    def connect(self):
        while True:
            try:
                print(f"{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} Connecting to {self.mqtt_host}:{self.mqtt_port} as {self.client_id}")
                self._client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
                self._client.loop_start()
                # wait for connection or timeout
                for _ in range(10):
                    if self._connected:
                        return True
                    time.sleep(0.5)
                # if not connected after timeout, treat as failure and retry
                print('Connection timed out, retrying in 5s')
                self._client.loop_stop()
            except Exception:
                print('MQTT connect failed, retrying in 5s')
                traceback.print_exc()
            time.sleep(5)

    def publish_telemetry(self):
        payload = build_telemetry(self.client_id)
        try:
            result = self._client.publish(self.telemetry_topic, payload)
            # result: (rc, mid)
            print(f"Published telemetry to {self.telemetry_topic}")
        except Exception:
            print('Failed to publish telemetry')
        # Also publish to an optional vault-specific topic if configured.
        if self.vault_topic:
            try:
                vault_payload = build_vault_payload(payload)
                if vault_payload:
                    self._client.publish(self.vault_topic, vault_payload)
                    print(f"Also published vault-formatted telemetry to {self.vault_topic}")
                else:
                    # Fallback: publish the full payload if transformation failed
                    self._client.publish(self.vault_topic, payload)
                    print(f"Also published (fallback) telemetry to vault topic {self.vault_topic}")
            except Exception:
                print(f'Failed to publish telemetry to vault topic {self.vault_topic}', file=sys.stderr)

    def publish_sensors(self):
        """Fetch sensors from Home Assistant (if configured) and publish to MQTT.

        Publishes to `telemetry/<client_id>/sensors` as a JSON object:
        { schema_version: 1, client_id, timestamp, sensors: [...] }
        """
        if not self.ha_api_url or not self.ha_api_token:
            # HA integration not configured
            return
        sensors = fetch_sensors(self.ha_api_url, self.ha_api_token)
        payload = {
            'schema_version': 1,
            'client_id': self.client_id,
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'sensors': sensors or []
        }
        try:
            self._client.publish(self.sensors_topic, json.dumps(payload))
            print(f"Published sensors list to {self.sensors_topic} (count={len(payload['sensors'])})")
            self._last_sensors_sent = int(time.time())
        except Exception:
            print(f'Failed to publish sensors to {self.sensors_topic}', file=sys.stderr)

    def run(self):
        # connect first
        self.connect()
        try:
            while True:
                if not self._connected:
                    print('Not connected, attempting reconnect')
                    self.connect()
                try:
                    self.publish_telemetry()
                except Exception:
                    print('Telemetry publish exception', file=sys.stderr)
                # send telemetry every 30s; send sensors every hour
                now = int(time.time())
                try:
                    if now - self._last_sensors_sent >= 3600:
                        self.publish_sensors()
                except Exception:
                    print('Sensors publish exception', file=sys.stderr)
                time.sleep(30)
        finally:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass


def main():
    options = load_options()
    c = CentralCoreClient(options)
    c.run()


if __name__ == '__main__':
    main()
