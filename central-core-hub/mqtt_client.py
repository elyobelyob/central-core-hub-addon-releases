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
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except Exception:
    print("paho-mqtt not installed", file=sys.stderr)
    raise

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
        'client_id': client_id,
        'status': 'online',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
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

    def on_connect(self, client, userdata, flags, rc):
        print(f"{datetime.utcnow().isoformat()}Z Connected to MQTT broker with rc={rc}")
        try:
            client.subscribe(self.commands_topic)
            print(f"Subscribed to {self.commands_topic}")
        except Exception:
            print('Subscription failed', file=sys.stderr)
        self._connected = True

    def on_disconnect(self, client, userdata, rc):
        print(f"{datetime.utcnow().isoformat()}Z Disconnected from MQTT broker rc={rc}")
        self._connected = False

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8', errors='replace')
        except Exception:
            payload = '<binary>'
        print(f"Received command on {msg.topic}: {payload}")

    def connect(self):
        while True:
            try:
                print(f"{datetime.utcnow().isoformat()}Z Connecting to {self.mqtt_host}:{self.mqtt_port} as {self.client_id}")
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
                self._client.publish(self.vault_topic, payload)
                print(f"Also published telemetry to vault topic {self.vault_topic}")
            except Exception:
                print(f'Failed to publish telemetry to vault topic {self.vault_topic}', file=sys.stderr)

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
