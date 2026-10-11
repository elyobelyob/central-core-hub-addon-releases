# Remote Add-on Upgrade via MQTT

Trigger add-on upgrades remotely via MQTT to the latest version or a specific version.

Every command needs a `command_id` (letters, digits, `_`, `.`, `-`, up to 64 characters, never reused)
and a `timestamp` (ISO 8601 with a UTC offset, or epoch seconds, no more than 10 minutes old). The hub
ignores a command without a `command_id` and answers one without a readable `timestamp` with a failed
ack (`bad_timestamp`). It also ignores retained messages.

## Usage

**Topic**: `hubs/{client_id}/v1/cmd/config/update`

**Latest version:**
```json
{"command_id": "cmd-123", "action": "config/update", "payload": {}, "timestamp": "2026-01-01T12:00:00Z"}
```

**Specific version:**
```json
{"command_id": "cmd-123", "action": "config/update", "payload": {"version": "1.1.74"}, "timestamp": "2026-01-01T12:00:00Z"}
```

## Response

**Ack topic**: `hubs/{client_id}/v1/ack/config.update/{command_id}`

**Success:**
```json
{
  "status": "completed",
  "result": {"success": true, "version": "1.1.74", ...},
  "timestamp": "2025-12-15T05:00:15Z"
}
```

**Failure:**
```json
{
  "status": "failed",
  "result": {"success": false, "reason": "addon_slug_missing"},
  "timestamp": "2025-12-15T05:00:15Z"
}
```

## Examples

**Python:**
```python
import paho.mqtt.client as mqtt, json, uuid
from datetime import datetime, timezone

client = mqtt.Client()
client.connect("mqtt.example.com", 1883, 60)
command = {"command_id": str(uuid.uuid4()), "action": "config/update", "payload": {"version": "1.1.74"},
           "timestamp": datetime.now(timezone.utc).isoformat()}
client.publish("hubs/my-hub-id/v1/cmd/config/update", json.dumps(command), qos=1)
```

**Node.js:**
```javascript
const mqtt = require('mqtt');
const client = mqtt.connect('mqtt://mqtt.example.com');
client.publish('hubs/my-hub-id/v1/cmd/config/update', 
  JSON.stringify({command_id: uuidv4(), action: 'config/update', payload: {version: '1.1.74'},
                  timestamp: new Date().toISOString()}), 
  {qos: 1});
```

## Security
- Use MQTT authentication & TLS
- Restrict command topic publish permissions
- Use unique command IDs

---
**Added in**: v1.1.75
