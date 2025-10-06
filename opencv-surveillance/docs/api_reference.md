# Integration API Reference

Complete API documentation for all smart home integrations.

---

## Table of Contents

1. [Integration Manager API](#integration-manager-api)
2. [Home Assistant Integration](#home-assistant-integration)
3. [HomeKit Integration](#homekit-integration)
4. [Nest Integration](#nest-integration)
5. [MQTT Integration](#mqtt-integration)
6. [Webhook System](#webhook-system)
7. [Event Types](#event-types)
8. [Data Structures](#data-structures)

---

## Integration Manager API

### Class: `IntegrationManager`

Central manager for all smart home integrations.

#### Initialization

```python
from integration_manager import IntegrationManager

manager = IntegrationManager(config_file='config/integrations.yaml')
await manager.initialize()
```

#### Methods

##### `initialize()`
Initialize all enabled integrations.

```python
await manager.initialize()
```

**Returns:** None

---

##### `register_camera()`
Register a camera with all integrations.

```python
manager.register_camera(
    camera_id='camera_1',
    camera_name='Front Door',
    camera_source=get_frame_function,  # Callable that returns frame
    stream_url='http://localhost:8081/camera/1/stream',
    is_doorbell=False
)
```

**Parameters:**
- `camera_id` (str): Unique camera identifier
- `camera_name` (str): Display name
- `camera_source` (Callable, optional): Function returning camera frames
- `stream_url` (str, optional): Stream URL for RTSP/HTTP
- `is_doorbell` (bool): Whether camera is a doorbell

---

##### `publish_event()`
Publish event to all integrations.

```python
manager.publish_event(
    event_type='motion_detected',
    camera_id='camera_1',
    data={'confidence': 0.95, 'zones': ['zone_1']}
)
```

**Parameters:**
- `event_type` (str): Type of event (see [Event Types](#event-types))
- `camera_id` (str): Camera identifier
- `data` (dict, optional): Additional event data

---

##### `publish_system_metrics()`
Publish system performance metrics.

```python
manager.publish_system_metrics()
```

**Returns:** None

---

##### `get_statistics()`
Get integration statistics.

```python
stats = manager.get_statistics()
```

**Returns:** Dictionary with statistics:
```python
{
    'events_processed': 150,
    'events_failed': 2,
    'last_event_time': '2025-01-15T10:30:00',
    'integrations': {
        'home_assistant': True,
        'homekit': True,
        'mqtt': True,
        'webhooks': True
    },
    'webhook_count': 3
}
```

---

##### `shutdown()`
Gracefully shutdown all integrations.

```python
await manager.shutdown()
```

---

## Home Assistant Integration

### Class: `HomeAssistantIntegration`

MQTT-based Home Assistant integration with auto-discovery.

#### Initialization

```python
from homeassistant_integration import HomeAssistantIntegration

ha = HomeAssistantIntegration(
    mqtt_host='localhost',
    mqtt_port=1883,
    mqtt_username='homeassistant',
    mqtt_password='password',
    discovery_prefix='homeassistant',
    state_prefix='opencv_surveillance'
)

ha.connect()
```

#### Methods

##### `register_camera()`
Register camera with Home Assistant.

```python
ha.register_camera(
    camera_id='camera_1',
    camera_name='Front Door Camera',
    stream_url='http://localhost:8081/camera/1/stream'
)
```

---

##### `publish_motion_event()`
Publish motion detection state.

```python
ha.publish_motion_event(
    camera_id='camera_1',
    motion_detected=True
)
```

---

##### `publish_face_detected_event()`
Publish face detection event.

```python
ha.publish_face_detected_event(
    camera_id='camera_1',
    face_name='John Doe',
    confidence=0.95,
    timestamp=datetime.now()
)
```

---

##### `publish_camera_snapshot()`
Publish camera snapshot.

```python
ha.publish_camera_snapshot(
    camera_id='camera_1',
    image_bytes=jpeg_bytes
)
```

---

##### `set_camera_availability()`
Update camera availability.

```python
ha.set_camera_availability(
    camera_id='camera_1',
    available=True
)
```

---

## HomeKit Integration

### Class: `HomeKitIntegration`

HomeKit Accessory Protocol (HAP) integration.

#### Initialization

```python
from homekit_integration import HomeKitIntegration

homekit = HomeKitIntegration(
    bridge_name='OpenCV Surveillance',
    persist_file='homekit_state.json',
    port=51826,
    pincode='123-45-678'
)

homekit.start()
```

#### Methods

##### `add_camera()`
Add camera to HomeKit bridge.

```python
homekit.add_camera(
    camera_id='camera_1',
    camera_name='Front Door',
    camera_source=get_frame_function,
    is_doorbell=True
)
```

---

##### `update_motion()`
Update motion detection state.

```python
homekit.update_motion(
    camera_id='camera_1',
    detected=True
)
```

---

##### `trigger_doorbell()`
Trigger doorbell press event.

```python
homekit.trigger_doorbell(camera_id='camera_1')
```

---

##### `get_snapshot()`
Get camera snapshot.

```python
snapshot_bytes = homekit.get_snapshot(
    camera_id='camera_1',
    width=1920,
    height=1080
)
```

---

## Nest Integration

### Class: `NestIntegration`

Google Smart Device Management API integration.

#### Initialization

```python
from nest_integration import NestIntegration

nest = NestIntegration(
    project_id='your-project-id',
    client_id='your-client-id',
    client_secret='your-client-secret',
    credentials_file='nest_credentials.json'
)
```

#### Methods

##### `authorize()`
Start OAuth authorization flow.

```python
auth_url, flow = nest.authorize()
# User visits auth_url and authorizes
nest.complete_authorization(flow, callback_url)
```

---

##### `list_devices()`
List all Nest devices.

```python
devices = await nest.list_devices()
for device in devices:
    print(f"{device.name}: {device.type}")
```

---

##### `get_camera_stream_url()`
Get RTSP stream URL for camera.

```python
stream_url = await nest.get_camera_stream_url(device_id='device_id')
```

---

##### `get_camera_image()`
Get latest camera image.

```python
image_bytes = await nest.get_camera_image(device_id='device_id')
```

---

## MQTT Integration

### Class: `MQTTIntegration`

Generic MQTT client for publishing events.

#### Initialization

```python
from mqtt_integration import MQTTIntegration, MQTTConfig

config = MQTTConfig(
    host='localhost',
    port=1883,
    username='surveillance',
    password='password',
    base_topic='surveillance'
)

mqtt = MQTTIntegration(config)
mqtt.connect()
```

#### Methods

##### `publish()`
Publish message to topic.

```python
mqtt.publish(
    topic='surveillance/camera/1/status',
    payload={'status': 'online'},
    qos=QoS.AT_LEAST_ONCE,
    retain=True
)
```

---

##### `subscribe()`
Subscribe to topic with callback.

```python
def message_handler(topic, payload):
    print(f"Received on {topic}: {payload}")

mqtt.subscribe(
    topic='surveillance/command/+',
    callback=message_handler,
    qos=QoS.AT_LEAST_ONCE
)
```

---

##### `publish_motion_detected()`
Publish motion detection event.

```python
mqtt.publish_motion_detected(
    camera_id='camera_1',
    detected=True,
    confidence=0.95,
    zones=['zone_1', 'zone_2']
)
```

---

##### `publish_face_detected()`
Publish face detection event.

```python
mqtt.publish_face_detected(
    camera_id='camera_1',
    face_name='John Doe',
    confidence=0.92,
    location={'x': 100, 'y': 150, 'width': 200, 'height': 250}
)
```

---

##### `publish_system_metrics()`
Publish system metrics.

```python
mqtt.publish_system_metrics(
    cpu_percent=45.2,
    memory_percent=62.8,
    disk_usage_gb=125.5,
    active_cameras=3
)
```

---

## Webhook System

### Class: `WebhookManager`

HTTP webhook delivery system.

#### Initialization

```python
from webhook_system import WebhookManager

manager = WebhookManager(database_file='webhooks.json')
```

#### Methods

##### `register_webhook()`
Register a new webhook.

```python
webhook = manager.register_webhook(
    webhook_id='my_webhook',
    url='https://example.com/webhook',
    events=['motion_detected', 'face_detected'],
    secret='my_secret_key',
    camera_ids=['camera_1'],  # Optional filter
    max_retries=3,
    retry_delay=5,
    timeout=10
)
```

**Parameters:**
- `webhook_id` (str): Unique identifier
- `url` (str): Target URL
- `events` (List[str]): Event types to subscribe to
- `secret` (str, optional): HMAC secret for signature
- `headers` (Dict, optional): Additional HTTP headers
- `camera_ids` (List[str], optional): Filter by cameras
- `max_retries` (int): Maximum retry attempts
- `retry_delay` (int): Delay between retries (seconds)
- `timeout` (int): Request timeout (seconds)

---

##### `trigger_event()`
Trigger webhooks for an event.

```python
await manager.trigger_event(
    event_type='motion_detected',
    camera_id='camera_1',
    data={'confidence': 0.95}
)
```

---

##### `get_delivery_stats()`
Get delivery statistics for webhook.

```python
stats = manager.get_delivery_stats('webhook_id')
```

**Returns:**
```python
{
    'webhook_id': 'my_webhook',
    'total_deliveries': 150,
    'failed_deliveries': 3,
    'success_rate': 98.0,
    'avg_response_time_ms': 125.5,
    'last_triggered': '2025-01-15T10:30:00'
}
```

---

## Event Types

All supported event types:

| Event Type | Description | Data Fields |
|------------|-------------|-------------|
| `motion_detected` | Motion detected on camera | `detected` (bool), `confidence` (float), `zones` (list) |
| `motion_ended` | Motion detection ended | None |
| `face_detected` | Face recognized | `name` (str), `confidence` (float), `location` (dict) |
| `recording_started` | Recording started | `filename` (str) |
| `recording_stopped` | Recording stopped | `filename` (str) |
| `camera_online` | Camera came online | None |
| `camera_offline` | Camera went offline | None |
| `audio_detected` | Audio/sound detected | `level` (float) |
| `object_detected` | Object detected | `object_type` (str), `confidence` (float) |
| `zone_breach` | Zone boundary breached | `zone` (str) |
| `doorbell_pressed` | Doorbell button pressed | None |
| `system_alert` | System alert/error | `message` (str), `level` (str) |

---

## Data Structures

### CameraEvent

```python
@dataclass
class CameraEvent:
    camera_id: str
    event_type: str
    timestamp: str
    data: Dict[str, Any]
```

**Example:**
```python
{
    "camera_id": "camera_1",
    "event_type": "motion_detected",
    "timestamp": "2025-01-15T10:30:00",
    "data": {
        "detected": true,
        "confidence": 0.95,
        "zones": ["zone_1", "zone_2"]
    }
}
```

---

### WebhookPayload

```python
@dataclass
class WebhookPayload:
    event_type: str
    camera_id: str
    timestamp: str
    data: Dict[str, Any]
```

**Example:**
```python
{
    "event_type": "face_detected",
    "camera_id": "camera_1",
    "timestamp": "2025-01-15T10:30:00",
    "data": {
        "face_name": "John Doe",
        "confidence": 0.92,
        "location": {
            "x": 100,
            "y": 150,
            "width": 200,
            "height": 250
        }
    }
}
```

---

### MQTTConfig

```python
@dataclass
class MQTTConfig:
    host: str = "localhost"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "opencv_surveillance"
    keepalive: int = 60
    base_topic: str = "surveillance"
    status_topic: str = "surveillance/status"
    command_topic: str = "surveillance/command"
```

---

## MQTT Topic Structure

### Published Topics

```
surveillance/
├── status                          # System status
├── system/
│   ├── cpu_usage                   # CPU usage percentage
│   ├── memory_usage                # Memory usage percentage
│   └── disk_usage                  # Disk usage in GB
├── camera/
│   ├── {camera_id}/
│   │   ├── availability            # online/offline
│   │   ├── motion                  # ON/OFF
│   │   ├── image                   # JPEG snapshot
│   │   ├── snapshot/metadata       # Snapshot metadata
│   │   └── event                   # Camera events (JSON)
└── events/
    ├── motion_detected             # Motion events (JSON)
    ├── face_detected               # Face events (JSON)
    └── ...                         # Other event types
```

### Command Topics

```
surveillance/command/
├── {camera_id}                     # Camera-specific commands
└── system                          # System commands
```

**Command Format:**
```json
{
    "type": "start_recording",
    "duration": 300
}
```

**Supported Commands:**
- `start_recording` - Start recording
- `stop_recording` - Stop recording
- `snapshot` - Take snapshot
- `enable_motion_detection` - Enable motion detection
- `disable_motion_detection` - Disable motion detection
- `cleanup_old_recordings` - Cleanup old files

---

## Webhook Security

### Signature Verification

All webhooks include an HMAC signature in the `X-Webhook-Signature` header.

**Format:** `sha256={hex_digest}`

**Verification Example (Python):**
```python
import hmac
import hashlib

def verify_signature(payload: str, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature == f"sha256={expected}"
```

**Verification Example (Node.js):**
```javascript
const crypto = require('crypto');

function verifySignature(payload, signature, secret) {
    const hmac = crypto.createHmac('sha256', secret);
    hmac.update(payload);
    const expected = `sha256=${hmac.digest('hex')}`;
    
    return signature === expected;
}
```

---

## Error Handling

All integration methods should be wrapped in try-except blocks:

```python
try:
    manager.publish_event('motion_detected', 'camera_1', {'detected': True})
except Exception as e:
    logger.error(f"Failed to publish event: {e}")
```

Common exceptions:
- `ConnectionError` - MQTT/Network connection failed
- `TimeoutError` - Request timeout
- `ValueError` - Invalid parameter
- `KeyError` - Missing required field

---

## Rate Limiting

### Recommended Limits

| Integration | Recommended Rate | Notes |
|-------------|------------------|-------|
| MQTT Publish | 10/second | Per topic |
| Webhook Delivery | 5/second | Per webhook |
| HomeKit Updates | 1/second | Per accessory |
| Nest API | 100/hour | Per project |

---

## Best Practices

1. **Event Batching**: Batch multiple events when possible
2. **QoS Levels**: Use QoS 0 for high-frequency updates, QoS 1 for important events
3. **Retained Messages**: Only retain state topics
4. **Error Handling**: Always handle integration failures gracefully
5. **Resource Cleanup**: Call `shutdown()` on application exit
6. **Monitoring**: Regularly check integration statistics
7. **Security**: Use TLS/SSL for all external connections

---

## Support & Troubleshooting

For integration issues, check:
1. Integration logs (set level to DEBUG)
2. MQTT broker logs
3. Network connectivity
4. Firewall rules
5. Authentication credentials

Enable debug logging:
```python
import logging
logging.getLogger('homeassistant_integration').setLevel(logging.DEBUG)
logging.getLogger('homekit_integration').setLevel(logging.DEBUG)
logging.getLogger('mqtt_integration').setLevel(logging.DEBUG)
```

---

**Version:** 1.0.0  
**Last Updated:** January 2025