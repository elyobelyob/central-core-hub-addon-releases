
import argparse
import time
import sys
import json
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to MQTT broker")
    else:
        print(f"Failed to connect, return code {rc}")

def on_publish(client, userdata, mid, reason_code=None, properties=None):
    print(f"Message published (mid={mid})")

def trigger_update(broker, port, username, password, client_id, version):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if username and password:
        client.username_pw_set(username, password)
    
    client.on_connect = on_connect
    client.on_publish = on_publish

    print(f"Connecting to {broker}:{port}...")
    try:
        client.connect(broker, port, 60)
        client.loop_start()
        time.sleep(1) # wait for connection

        topic = f"hubs/{client_id}/v1/cmd/config/update"
        payload = {"version": version} if version else {}
        
        print(f"Publishing update command to {topic} with payload {payload}")
        msg_info = client.publish(topic, json.dumps(payload), qos=1)
        msg_info.wait_for_publish()
        
        time.sleep(1) # ensure sent
        client.loop_stop()
        client.disconnect()
        print("Done.")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger remote add-on update via MQTT")
    parser.add_argument("--broker", required=True, help="MQTT Broker IP/Hostname")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker Port")
    parser.add_argument("--username", help="MQTT Username")
    parser.add_argument("--password", help="MQTT Password")
    parser.add_argument("--client-id", required=True, help="Target Client ID (e.g., test-hub-001)")
    parser.add_argument("--version", help="Target version (e.g., 2.0.1) or 'latest'")

    args = parser.parse_args()

    success = trigger_update(args.broker, args.port, args.username, args.password, args.client_id, args.version)
    sys.exit(0 if success else 1)
