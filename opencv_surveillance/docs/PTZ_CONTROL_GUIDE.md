# PTZ Control Guide

Complete guide for using Pan-Tilt-Zoom camera controls in OpenEye.

## Table of Contents

1. [Overview](#overview)
2. [Supported Protocols](#supported-protocols)
3. [Setup & Configuration](#setup--configuration)
4. [Manual Control](#manual-control)
5. [Presets](#presets)
6. [Patrol Patterns](#patrol-patterns)
7. [API Reference](#api-reference)
8. [Troubleshooting](#troubleshooting)

## Overview

The PTZ Control system allows you to remotely control Pan-Tilt-Zoom cameras through the OpenEye interface. You can:

- **Manual Control**: Use joystick-style controls to pan, tilt, and zoom in real-time
- **Presets**: Save favorite camera positions for quick recall
- **Patrol Patterns**: Create automated movement sequences that patrol multiple positions

## Supported Protocols

### ONVIF (Primary)
- **Protocol**: ONVIF Profile S
- **Port**: Usually 80 or 8000
- **Features**: Full PTZ control, preset management, continuous movement
- **Compatible Cameras**: Most modern IP PTZ cameras with ONVIF support

### Future Support (Coming Soon)
- **Pelco-D**: RS-485 serial protocol
- **Pelco-P**: RS-485 serial protocol
- **VISCA**: Sony VISCA protocol over IP

## Setup & Configuration

### 1. Install Dependencies

The `onvif-zeep` package is required for PTZ functionality:

```bash
cd opencv_surveillance
source venv/bin/activate
pip install onvif-zeep>=0.2.12
```

This is automatically included in `requirements.txt` for new installations.

### 2. Camera Requirements

Your PTZ camera must support:
- ONVIF Profile S protocol
- Network connectivity (IP camera)
- PTZ service enabled

### 3. Connection Setup

1. Navigate to **Camera Management** page
2. Click **🎮 PTZ Control** on your PTZ camera
3. Click **Connect** in the PTZ Control panel
4. Enter connection details:
   - **Camera IP**: The camera's IP address (e.g., `192.168.1.100`)
   - **ONVIF Port**: Usually `80` or `8000`
   - **Username**: Camera admin username
   - **Password**: Camera admin password
5. Click **Connect**

The status indicator will turn green when connected.

## Manual Control

### Joystick Controls

The 9-button joystick provides directional control:

```
↖  ↑  ↗
←  ⬛  →
↙  ↓  ↘
```

- **8 Direction Buttons**: Hold to move camera in that direction
- **Center Button (⬛)**: Stop all movement
- **Release**: Movement automatically stops when you release the button

### Zoom Controls

- **+ Button**: Zoom in (telephoto)
- **- Button**: Zoom out (wide angle)
- Click and hold for continuous zoom

### Speed Control

Use the **Movement Speed** slider to adjust:
- **0%**: Slowest, most precise movements
- **50%**: Default balanced speed
- **100%**: Fastest movements

## Presets

Presets allow you to save and recall camera positions instantly.

### Creating a Preset

1. Navigate to the **Presets** tab
2. Use manual controls to position the camera
3. Click **+ Add Preset**
4. Enter a preset name (e.g., "Front Gate", "Parking Lot")
5. Enter a preset number (1-255)
6. Click **Create**

The preset is saved both in the database and on the camera hardware (if supported).

### Using Presets

1. Navigate to the **Presets** tab
2. Find your preset in the grid
3. Click **Go To** to move the camera to that position

Preset cards show:
- **Preset Name**: User-friendly identifier
- **Preset Number**: Slot number (#1-#255)
- **Position**: Pan, Tilt, Zoom coordinates

### Deleting Presets

Click **Delete** on any preset card. This removes it from both the database and camera.

## Patrol Patterns

Patrol patterns automate camera movement through a sequence of positions.

### Pattern Structure

A patrol pattern consists of:
- **Name**: Pattern identifier (e.g., "Perimeter Scan")
- **Description**: Optional details about the pattern
- **Steps**: 2 or more positions to visit
- **Interval**: Time to stay at each position (seconds)
- **Loop**: Whether to repeat continuously

### Creating a Pattern

#### Method 1: Using Presets (Recommended)

1. Create 2+ presets for the positions you want to patrol
2. Navigate to the **Patrol Patterns** tab
3. Click **+ Add Patrol Pattern**
4. Enter pattern details:
   - Name: "Standard Patrol"
   - Description: "Left → Center → Right"
   - Steps: Select presets in order
   - Interval: 10 seconds (time at each position)
   - Loop: Enabled
5. Click **Create**

#### Method 2: Direct Coordinates (API)

Use the API to create patterns with direct pan/tilt/zoom coordinates:

```bash
curl -X POST http://localhost:8000/api/cameras/{camera_id}/ptz/patrol-patterns \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "Custom Patrol",
    "description": "Left to right scan",
    "pattern_steps": [
      {"pan": -0.8, "tilt": 0.0, "zoom": 0.5, "dwell_time": 5},
      {"pan": 0.0, "tilt": 0.0, "zoom": 0.5, "dwell_time": 3},
      {"pan": 0.8, "tilt": 0.0, "zoom": 0.5, "dwell_time": 5}
    ],
    "loop_enabled": true,
    "interval_seconds": 10
  }'
```

### Starting a Patrol

1. Navigate to the **Patrol Patterns** tab
2. Find your pattern in the list
3. Click **Start**

The pattern status will change to **● Running** and the camera will begin moving through the sequence.

### Stopping a Patrol

Click **Stop** on any running pattern. The camera will complete its current movement and halt.

### Pattern Behavior

- **Loop Enabled**: Pattern repeats indefinitely until stopped
- **Loop Disabled**: Pattern runs once then stops automatically
- **Multiple Steps**: Camera moves to each position in order
- **Dwell Time**: Camera pauses at each position before moving to the next
- **Smooth Movement**: Transitions between positions are smooth (speed configurable)

### Example Patterns

**Perimeter Scan**
```json
{
  "name": "Perimeter Scan",
  "pattern_steps": [
    {"preset_id": 1, "dwell_time": 10},  // Front gate
    {"preset_id": 2, "dwell_time": 8},   // Left fence
    {"preset_id": 3, "dwell_time": 8},   // Back yard
    {"preset_id": 4, "dwell_time": 10}   // Right fence
  ],
  "interval_seconds": 10,
  "loop_enabled": true
}
```

**Quick Sweep**
```json
{
  "name": "Quick Sweep",
  "pattern_steps": [
    {"pan": -1.0, "tilt": 0.0, "zoom": 0.3, "dwell_time": 2},
    {"pan": 0.0, "tilt": 0.0, "zoom": 0.3, "dwell_time": 2},
    {"pan": 1.0, "tilt": 0.0, "zoom": 0.3, "dwell_time": 2}
  ],
  "interval_seconds": 5,
  "loop_enabled": true
}
```

## API Reference

### Connection

**Connect to PTZ Camera**
```http
POST /api/cameras/{camera_id}/ptz/connect
Content-Type: application/json

{
  "camera_ip": "192.168.1.100",
  "port": 80,
  "username": "admin",
  "password": "password",
  "ptz_type": "onvif"
}
```

**Disconnect PTZ Camera**
```http
POST /api/cameras/{camera_id}/ptz/disconnect
```

**Get PTZ Status**
```http
GET /api/cameras/{camera_id}/ptz/status

Response:
{
  "camera_id": "front_ptz",
  "connected": true,
  "status": {
    "pan": 0.5,
    "tilt": 0.2,
    "zoom": 0.7,
    "moving": false
  }
}
```

### Manual Control

**Absolute Move**
```http
POST /api/cameras/{camera_id}/ptz/move/absolute
Content-Type: application/json

{
  "pan": 0.5,    // -1.0 (left) to 1.0 (right)
  "tilt": 0.2,   // -1.0 (down) to 1.0 (up)
  "zoom": 0.7,   // 0.0 (wide) to 1.0 (tele)
  "speed": 0.5   // 0.0 (slow) to 1.0 (fast)
}
```

**Continuous Move**
```http
POST /api/cameras/{camera_id}/ptz/move/continuous
Content-Type: application/json

{
  "pan_velocity": 0.3,   // -1.0 to 1.0
  "tilt_velocity": 0.2,  // -1.0 to 1.0
  "zoom_velocity": 0.0   // -1.0 to 1.0
}
```

**Stop Movement**
```http
POST /api/cameras/{camera_id}/ptz/stop
```

### Presets

**List Presets**
```http
GET /api/cameras/{camera_id}/ptz/presets

Response:
{
  "camera_id": "front_ptz",
  "presets": [
    {
      "id": 1,
      "name": "Front Gate",
      "preset_number": 1,
      "pan": 0.5,
      "tilt": 0.0,
      "zoom": 0.8,
      "usage_count": 42
    }
  ],
  "total": 1
}
```

**Create Preset**
```http
POST /api/cameras/{camera_id}/ptz/presets
Content-Type: application/json

{
  "name": "Front Gate",
  "preset_number": 1,
  "pan": 0.5,
  "tilt": 0.0,
  "zoom": 0.8
}
```

**Go to Preset**
```http
POST /api/cameras/{camera_id}/ptz/presets/{preset_id}/goto?speed=0.5
```

**Delete Preset**
```http
DELETE /api/cameras/{camera_id}/ptz/presets/{preset_id}
```

### Patrol Patterns

**List Patterns**
```http
GET /api/cameras/{camera_id}/ptz/patrol-patterns
```

**Create Pattern**
```http
POST /api/cameras/{camera_id}/ptz/patrol-patterns
Content-Type: application/json

{
  "name": "Perimeter Scan",
  "description": "Patrols the perimeter",
  "pattern_steps": [
    {"preset_id": 1, "dwell_time": 5},
    {"preset_id": 2, "dwell_time": 5},
    {"preset_id": 3, "dwell_time": 5}
  ],
  "loop_enabled": true,
  "interval_seconds": 10
}
```

**Start Pattern**
```http
POST /api/cameras/{camera_id}/ptz/patrol-patterns/{pattern_id}/start
```

**Stop Pattern**
```http
POST /api/cameras/{camera_id}/ptz/patrol-patterns/{pattern_id}/stop
```

**Delete Pattern**
```http
DELETE /api/cameras/{camera_id}/ptz/patrol-patterns/{pattern_id}
```

## Troubleshooting

### Connection Issues

**Problem**: "Failed to connect to PTZ camera"

**Solutions**:
1. Verify camera IP address is correct
2. Check ONVIF port (try 80, 8000, 8080)
3. Confirm username/password are correct
4. Ensure ONVIF is enabled in camera settings
5. Check firewall isn't blocking ONVIF port
6. Verify camera is on the same network

**Test Command**:
```bash
# Ping camera
ping 192.168.1.100

# Check ONVIF port
telnet 192.168.1.100 80
```

### Movement Not Working

**Problem**: Connected but camera doesn't move

**Solutions**:
1. Verify PTZ service is enabled on camera
2. Check camera isn't in manual override mode
3. Ensure no other software is controlling the camera
4. Try rebooting the camera
5. Check camera PTZ permissions for the user

### Presets Not Saving

**Problem**: Presets saved in OpenEye but not on camera

**Solutions**:
1. Camera may not support preset storage
2. Preset slots may be full (255 limit)
3. Insufficient camera permissions
4. ONVIF firmware may need update

### Patrol Pattern Stops Unexpectedly

**Problem**: Pattern stops mid-execution

**Solutions**:
1. Check backend logs for errors
2. Verify all preset IDs exist
3. Ensure camera stays connected
4. Check for API timeouts in logs

### Getting Logs

View PTZ logs for debugging:

```bash
# Backend logs
cd opencv_surveillance
tail -f logs/app.log | grep PTZ

# System logs
journalctl -u openeye -f | grep PTZ
```

## Best Practices

### 1. Naming Conventions

Use descriptive names for presets and patterns:
- ✅ "Front Gate - Wide"
- ✅ "Parking Lot - Zoomed"
- ❌ "Preset 1"
- ❌ "Camera Position"

### 2. Preset Organization

Organize presets by zone:
- Presets 1-10: Front of building
- Presets 11-20: Sides
- Presets 21-30: Back area
- Presets 31-40: Parking

### 3. Pattern Timing

Consider lighting and activity:
- **Daytime**: Faster patrols (5s intervals)
- **Nighttime**: Slower patrols (10-15s intervals) for better IR capture

### 4. Performance

- Limit active patrol patterns to 1-2 per camera
- Use presets instead of direct coordinates when possible
- Keep pattern steps to 2-8 positions for smooth operation
- Avoid very fast speed settings to prevent camera wear

### 5. Security

- Use strong credentials for PTZ cameras
- Change default camera passwords
- Restrict PTZ API access to authorized users only
- Log PTZ movements for audit trail

## Integration Examples

### Trigger Pattern on Motion

Automatically start a patrol pattern when motion is detected:

```python
# In motion_detector.py
async def on_motion_detected(camera_id):
    # Start patrol pattern
    await apiClient.post(
        f'/api/cameras/{camera_id}/ptz/patrol-patterns/1/start'
    )
```

### Return to Home Position

Return camera to home position after inactivity:

```python
# Scheduled task
async def return_to_home():
    for camera in ptz_cameras:
        # Go to preset 1 (home position)
        await apiClient.post(
            f'/api/cameras/{camera.id}/ptz/presets/1/goto'
        )
```

### Face Detection Tracking

Move camera to track detected faces:

```python
# In face_recognition.py
async def track_face(camera_id, face_location):
    # Calculate pan/tilt to center face
    pan, tilt = calculate_ptz_from_face(face_location)

    # Move camera
    await apiClient.post(
        f'/api/cameras/{camera_id}/ptz/move/absolute',
        json={'pan': pan, 'tilt': tilt, 'zoom': 0.8, 'speed': 0.7}
    )
```

## Architecture Notes

### Database Schema

**PTZPreset Table**:
- `id`: Primary key
- `camera_id`: Foreign key to cameras
- `name`: Preset name
- `preset_number`: Slot (1-255)
- `pan`, `tilt`, `zoom`: Position coordinates
- `usage_count`, `last_used_at`: Usage tracking

**PTZPatrolPattern Table**:
- `id`: Primary key
- `camera_id`: Foreign key to cameras
- `name`: Pattern name
- `pattern_steps`: JSON array of steps
- `is_active`: Currently running flag
- `loop_enabled`: Continuous patrol flag
- `interval_seconds`: Default dwell time

### Controller Architecture

The PTZ system uses a singleton pattern:

```python
from backend.core.ptz_controller import get_ptz_controller

# Get controller for camera
controller = get_ptz_controller("front_ptz", ptz_type="onvif")

# Connect
await controller.connect("192.168.1.100", 80, "admin", "password")

# Control
await controller.move_absolute(0.5, 0.2, 0.7, speed=0.5)
await controller.stop()
```

### Background Pattern Execution

Patrol patterns run as FastAPI background tasks:

```python
@router.post("/patrol-patterns/{pattern_id}/start")
async def start_pattern(pattern_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(execute_patrol_pattern, camera_id, pattern_id)
    return {"message": "Pattern started"}
```

## Future Enhancements

Planned features for future releases:

- [ ] Visual preset thumbnails with camera snapshots
- [ ] Drag-and-drop pattern builder UI
- [ ] Auto-tracking for detected objects
- [ ] Tour scheduling (time-based patrols)
- [ ] Multi-camera coordinated patrols
- [ ] PTZ zones (restrict movement areas)
- [ ] Speed profiles (slow/medium/fast presets)
- [ ] Pattern templates (common patrol types)
- [ ] Mobile app PTZ controls
- [ ] Voice control integration

## Support

For issues or questions:
- GitHub Issues: [OpenEye Issues](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues)
- Documentation: Check `docs/API_DOCUMENTATION.md`
- Logs: Review `logs/app.log` for PTZ errors

---

**Version**: 3.7.0
**Last Updated**: January 2025
**Author**: OpenEye Development Team
