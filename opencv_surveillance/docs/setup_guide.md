# Phase 5: Smart Home Integrations - Setup Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Home Assistant Setup](#home-assistant-setup)
3. [HomeKit Setup](#homekit-setup)
4. [Nest/Google Setup](#nestgoogle-setup)
5. [MQTT Setup](#mqtt-setup)
6. [Webhook Setup](#webhook-setup)
7. [Testing Integrations](#testing-integrations)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- Python 3.9 or higher
- Docker (optional, for MQTT broker)
- Network access to smart home devices
- Valid SSL certificates (recommended for production)

### Python Dependencies

Install all required packages:

```bash
pip install -r requirements_integrations.txt
```

**requirements_integrations.txt:**
```
paho-mqtt>=1.6.1
pyyaml>=6.0
HAP-python>=4.9.0
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
google-auth-httplib2>=0.1.1
google-api-python-client>=2.100.0
google-cloud-pubsub>=2.18.0
aiohttp>=3.8.0
psutil>=5.9.0
```

---

## Home Assistant Setup

### Step 1: Install MQTT Broker

**Option A: Using Docker**
```bash
docker run -d \
  --name mosquitto \
  -p 1883:1883 \
  -p 9001:9001 \
  -v $(pwd)/mosquitto/config:/mosquitto/config \
  -v $(pwd)/mosquitto/data:/mosquitto/data \
  -v $(pwd)/mosquitto/log:/mosquitto/log \
  eclipse-mosquitto
```

**Option B: Native Installation (Linux)**
```bash
sudo apt-get update
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### Step 2: Configure Mosquitto

Create `mosquitto.conf`:
```conf
# mosquitto.conf
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd

# Persistence
persistence true
persistence_location /mosquitto/data/

# Logging
log_dest file /mosquitto/log/mosquitto.log
log_type all
```

Create user credentials:
```bash
mosquitto_passwd -c /path/to/mosquitto/passwd homeassistant
# Enter password when prompted
```

### Step 3: Configure Home Assistant

In Home Assistant, go to **Configuration** → **Integrations** → **MQTT**

Add MQTT broker:
- Broker: `localhost` (or your server IP)
- Port: `1883`
- Username: `homeassistant`
- Password: (your password)

### Step 4: Configure OpenCV Surveillance

Edit `config/integrations.yaml`:
```yaml
home_assistant:
  enabled: true
  mqtt:
    host: localhost
    port: 1883
    username: homeassistant
    password: your_password
    discovery_prefix: homeassistant
    state_prefix: opencv_surveillance
```

### Step 5: Start Integration

```python
from integration_manager import IntegrationManager
import asyncio

async def main():
    manager = IntegrationManager('config/integrations.yaml')
    await manager.initialize()
    
    # Cameras will automatically appear in Home Assistant
    
asyncio.run(main())
```

### Step 6: Verify in Home Assistant

1. Go to **Settings** → **Devices & Services**
2. Look for **MQTT** integration
3. You should see your cameras listed as devices
4. Each camera will have:
   - Camera entity
   - Motion sensor entity
   - Availability sensor

---

## HomeKit Setup

### Step 1: Install HAP-python

```bash
pip install HAP-python[QRCode]
```

### Step 2: Configure HomeKit

Edit `config/integrations.yaml`:
```yaml
homekit:
  enabled: true
  bridge_name: OpenCV Surveillance
  pincode: "123-45-678"  # Change this!
  port: 51826
  persist_file: ./config/homekit_state.json
```

### Step 3: Start HomeKit Bridge

The integration manager will automatically start the HomeKit bridge. You'll see output like:

```
HomeKit Bridge: OpenCV Surveillance
Pairing Code: 123-45-678
QR Code: [ASCII QR code will be displayed]
```

### Step 4: Pair with iOS Device

1. Open **Home** app on iPhone/iPad
2. Tap **+** → **Add Accessory**
3. Choose **More Options**
4. Select **OpenCV Surveillance**
5. Enter PIN code: `123-45-678`
6. Choose room and finish setup

### Step 5: Configure Cameras

Cameras will appear as:
- **Camera Accessories** (for streaming)
- **Motion Sensors** (for motion detection)
- **Doorbell** (if configured)

### Security Notes

⚠️ **Important:**
- Change the default PIN code
- Use strong network security
- Keep `homekit_state.json` secure (contains pairing data)
- Never expose HomeKit port (51826) to the internet

---

## Nest/Google Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project: `opencv-surveillance`
3. Enable the **Smart Device Management API**
4. Enable **Cloud Pub/Sub API**

### Step 2: Create OAuth Credentials

1. Navigate to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Authorized redirect URIs: `http://localhost:8080/oauth/callback`
5. Save the **Client ID** and **Client Secret**

### Step 3: Register for Device Access

1. Go to [Device Access Console](https://console.nest.google.com/device-access)
2. Pay the one-time $5 registration fee
3. Create a project
4. Note your **Project ID**

### Step 4: Configure OpenCV Surveillance

Edit `config/integrations.yaml`:
```yaml
nest:
  enabled: true
  project_id: your-project-id
  client_id: your-client-id.apps.googleusercontent.com
  client_secret: your-client-secret
  redirect_uri: http://localhost:8080/oauth/callback
  credentials_file: ./config/nest_credentials.json
```

### Step 5: Authorize Application

Run the authorization script:
```python
from nest_integration import NestIntegration
import asyncio

async def authorize():
    nest = NestIntegration(
        project_id="your-project-id",
        client_id="your-client-id",
        client_secret="your-client-secret"
    )
    
    auth_url, flow = nest.authorize()
    print(f"Visit this URL to authorize: {auth_url}")
    
    # Paste the callback URL here
    callback_url = input("Paste the full callback URL: ")
    nest.complete_authorization(flow, callback_url)
    
    print("Authorization complete!")

asyncio.run(authorize())
```

### Step 6: Test Connection

```python
devices = await nest.list_devices()
for device in devices:
    print(f"Found: {device.name} ({device.type})")
```

---

## MQTT Setup

### Step 1: Install MQTT Broker

See [Home Assistant Setup](#home-assistant-setup) Step 1

### Step 2: Configure MQTT Integration

Edit `config/integrations.yaml`:
```yaml
mqtt:
  enabled: true
  broker:
    host: localhost
    port: 1883
    username: surveillance
    password: your_password
  topics:
    base_topic: surveillance
    status_topic: surveillance/status
    command_topic: surveillance/command
```

### Step 3: Subscribe to Topics

Using `mosquitto_sub` to monitor:

```bash
# Monitor all surveillance topics
mosquitto_sub -h localhost -u surveillance -P password -t "surveillance/#" -v

# Monitor specific camera
mosquitto_sub -h localhost -u surveillance -P password -t "surveillance/camera/camera_1/#" -v

# Monitor motion events
mosquitto_sub -h localhost -u surveillance -P password -t "surveillance/camera/+/motion" -v
```

### Step 4: Send Commands

Using `mosquitto_pub`:

```bash
# Start recording
mosquitto_pub -h localhost -u surveillance -P password \
  -t "surveillance/command/camera_1" \
  -m '{"type":"start_recording"}'

# Take snapshot
mosquitto_pub -h localhost -u surveillance -P password \
  -t "surveillance/command/camera_1" \
  -m '{"type":"snapshot"}'

# Enable motion detection
mosquitto_pub -h localhost -u surveillance -P password \
  -t "surveillance/command/camera_1" \
  -m '{"type":"enable_motion_detection"}'
```

---

## Webhook Setup

### Step 1: Configure Webhooks

Edit `config/integrations.yaml`:
```yaml
webhooks:
  enabled: true
  database_file: ./config/webhooks.json
  registered:
    - id: my_webhook
      url: https://your-server.com/webhook
      events:
        - motion_detected
        - face_detected
      active: true
      secret: your_secret_key
```

### Step 2: Register Webhooks Programmatically

```python
from webhook_system import WebhookManager

manager = WebhookManager()

# Register webhook
manager.register_webhook(
    webhook_id="custom_webhook",
    url="https://example.com/webhook",
    events=["motion_detected", "face_detected"],
    secret="my_secret_123",
    camera_ids=["camera_1"]  # Optional filter
)
```

### Step 3: Verify Webhook Signature

In your webhook receiver:

```python
import hmac
import hashlib
from flask import Flask, request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Get signature from header
    signature = request.headers.get('X-Webhook-Signature', '')
    
    # Get payload
    payload = request.get_data(as_text=True)
    
    # Verify signature
    expected_sig = hmac.new(
        b'my_secret_123',
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if signature != f"sha256={expected_sig}":
        return "Invalid signature", 401
    
    # Process webhook
    data = request.get_json()
    print(f"Event: {data['event_type']}")
    print(f"Camera: {data['camera_id']}")
    
    return "OK", 200
```

### Step 4: Test Webhooks

```python
import asyncio
from webhook_system import WebhookManager

async def test():
    manager = WebhookManager()
    
    # Trigger test event
    await manager.trigger_motion_detected(
        camera_id="camera_1",
        confidence=0.95,
        zones=["zone_1"]
    )
    
    # Check stats
    stats = manager.get_delivery_stats("my_webhook")
    print(stats)

asyncio.run(test())
```

---

## Testing Integrations

### Integration Test Script

Create `test_integrations.py`:

```python
import asyncio
import logging
from integration_manager import IntegrationManager
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def test_all_integrations():
    """Test all integrations"""
    
    # Initialize manager
    manager = IntegrationManager('config/integrations.yaml')
    await manager.initialize()
    
    print("\n" + "="*60)
    print("INTEGRATION TEST SUITE")
    print("="*60 + "\n")
    
    # Test 1: Camera Registration
    print("Test 1: Registering test camera...")
    manager.register_camera(
        camera_id="test_camera",
        camera_name="Test Camera",
        stream_url="http://localhost:8081/test",
        is_doorbell=False
    )
    print("✓ Camera registered\n")
    
    # Test 2: Motion Detection Event
    print("Test 2: Publishing motion detection event...")
    manager.publish_event('motion_detected', 'test_camera', {
        'detected': True,
        'confidence': 0.95,
        'zones': ['zone_1', 'zone_2']
    })
    await asyncio.sleep(2)
    print("✓ Motion event published\n")
    
    # Test 3: Face Detection Event
    print("Test 3: Publishing face detection event...")
    manager.publish_event('face_detected', 'test_camera', {
        'name': 'John Doe',
        'confidence': 0.92,
        'location': {'x': 100, 'y': 150, 'width': 200, 'height': 250}
    })
    await asyncio.sleep(2)
    print("✓ Face event published\n")
    
    # Test 4: Recording Events
    print("Test 4: Publishing recording events...")
    manager.publish_event('recording_started', 'test_camera', {
        'filename': 'test_recording.mp4'
    })
    await asyncio.sleep(1)
    manager.publish_event('recording_stopped', 'test_camera', {
        'filename': 'test_recording.mp4'
    })
    print("✓ Recording events published\n")
    
    # Test 5: System Metrics
    print("Test 5: Publishing system metrics...")
    manager.publish_system_metrics()
    print("✓ System metrics published\n")
    
    # Test 6: Statistics
    print("Test 6: Checking statistics...")
    stats = manager.get_statistics()
    print(f"Events processed: {stats['events_processed']}")
    print(f"Events failed: {stats['events_failed']}")
    print(f"Active integrations: {sum(stats['integrations'].values())}")
    print("✓ Statistics retrieved\n")
    
    print("="*60)
    print("ALL TESTS COMPLETED")
    print("="*60 + "\n")
    
    # Cleanup
    await asyncio.sleep(2)
    await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(test_all_integrations())
```

Run tests:
```bash
python test_integrations.py
```

### Expected Output

```
============================================================
INTEGRATION TEST SUITE
============================================================

Test 1: Registering test camera...
✓ Camera registered

Test 2: Publishing motion detection event...
✓ Motion event published

Test 3: Publishing face detection event...
✓ Face event published

Test 4: Publishing recording events...
✓ Recording events published

Test 5: Publishing system metrics...
✓ System metrics published

Test 6: Checking statistics...
Events processed: 5
Events failed: 0
Active integrations: 3
✓ Statistics retrieved

============================================================
ALL TESTS COMPLETED
============================================================
```

---

## Troubleshooting

### Home Assistant Issues

**Problem: Cameras not appearing in Home Assistant**

1. Check MQTT connection:
```bash
mosquitto_sub -h localhost -u homeassistant -P password -t "homeassistant/#" -v
```

2. Verify discovery messages are published:
```bash
# Should show camera discovery configs
mosquitto_sub -h localhost -u homeassistant -P password -t "homeassistant/camera/+/config" -v
```

3. Check logs:
```python
logging.getLogger('homeassistant_integration').setLevel(logging.DEBUG)
```

**Problem: Motion sensor not updating**

- Verify motion events are published:
```bash
mosquitto_sub -h localhost -u homeassistant -P password -t "opencv_surveillance/+/motion" -v
```

- Check availability topic:
```bash
mosquitto_sub -h localhost -u homeassistant -P password -t "opencv_surveillance/+/availability" -v
```

### HomeKit Issues

**Problem: Can't pair with iOS device**

1. Check firewall allows port 51826
2. Ensure iOS device and server on same network
3. Delete `homekit_state.json` and restart
4. Try a different PIN code

**Problem: Camera stream not working**

- Verify camera source function returns valid frames
- Check frame format (must be numpy array, BGR format)
- Enable debug logging:
```python
logging.getLogger('pyhap').setLevel(logging.DEBUG)
```

### Nest Issues

**Problem: Authorization fails**

1. Verify redirect URI matches exactly in Google Console
2. Check OAuth client ID and secret
3. Ensure SDM API is enabled in Google Cloud project
4. Verify $5 Device Access fee was paid

**Problem: No devices found**

- Make sure Nest devices are shared with the Google account
- Check project ID matches Device Access project
- Verify permissions in Nest app

### MQTT Issues

**Problem: Connection refused**

1. Check mosquitto is running:
```bash
systemctl status mosquitto
```

2. Test credentials:
```bash
mosquitto_pub -h localhost -u surveillance -P password -t "test" -m "hello"
```

3. Check firewall:
```bash
sudo ufw allow 1883/tcp
```

**Problem: Messages not received**

- Verify subscription patterns match topic structure
- Check QoS levels (use QoS 1 for important messages)
- Enable verbose logging in mosquitto

### Webhook Issues

**Problem: Webhooks not triggering**

1. Check webhook is active:
```python
webhook = manager.get_webhook("webhook_id")
print(webhook.active)
```

2. Verify URL is accessible:
```bash
curl -X POST https://your-webhook-url.com/webhook
```

3. Check delivery stats:
```python
stats = manager.get_delivery_stats("webhook_id")
print(stats)
```

**Problem: Signature verification fails**

- Ensure same secret on both sides
- Check payload encoding (UTF-8)
- Verify signature format: `sha256={hex_digest}`

---

## Performance Optimization

### MQTT Optimization

```yaml
mqtt:
  broker:
    keepalive: 60
    clean_session: true  # Set to false for persistent sessions
  publish:
    qos: 0  # Use 0 for high-frequency updates, 1 for important events
    retain: false  # Only retain state topics
```

### Event Queue Tuning

```yaml
integration_manager:
  event_queue:
    max_size: 1000
    batch_size: 10  # Process multiple events at once
    batch_interval: 1
  performance:
    max_concurrent_webhooks: 10
    worker_threads: 4  # Increase for high event volume
```

### Webhook Optimization

```yaml
webhooks:
  defaults:
    max_retries: 2  # Reduce for faster failure
    retry_delay: 2  # Shorter delay
    timeout: 5  # Shorter timeout
```

---

## Security Best Practices

1. **Use TLS/SSL for all connections**
2. **Change default passwords and PIN codes**
3. **Use strong webhook secrets (32+ characters)**
4. **Implement rate limiting on webhook endpoints**
5. **Store credentials in environment variables**
6. **Regular security audits of integration logs**
7. **Network segmentation for IoT devices**
8. **Enable authentication on MQTT broker**

---

## Next Steps

After completing Phase 5 setup:

1. ✅ Test all integrations thoroughly
2. ✅ Set up automation rules in Home Assistant
3. ✅ Configure HomeKit scenes
4. ✅ Create custom webhook integrations
5. ✅ Monitor integration performance
6. ✅ Document your custom configurations
7. ✅ Set up backup for configuration files

For production deployment, refer to the deployment guide in Phase 6.