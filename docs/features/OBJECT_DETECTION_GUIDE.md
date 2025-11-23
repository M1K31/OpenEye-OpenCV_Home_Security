# Object Detection User Guide (v3.10.0)

AI-powered object detection using YOLOv8 to identify vehicles, animals, packages, and more.

## 🎯 Overview

OpenEye's Object Detection feature uses state-of-the-art YOLO (You Only Look Once) AI to detect and classify objects in your camera feeds. This enables:
- **Automated monitoring** of vehicles entering/leaving your property
- **Package detection** for delivery notifications
- **Wildlife/pet tracking** in specific areas
- **Identified object tracking** for specific vehicles, pets, or belongings

Built on **YOLOv8** from Ultralytics, trained on the COCO dataset with 80+ object classes.

---

## ✨ Features

### Detection Capabilities
- ✅ **80+ Object Classes** - Cars, trucks, dogs, cats, birds, packages, and more
- ✅ **Real-time Detection** - Process video streams with configurable frame rates
- ✅ **High Accuracy** - YOLOv8 state-of-the-art object detection
- ✅ **GPU Acceleration** - CUDA support for fast inference (optional)
- ✅ **Smart Filtering** - Focus on specific object classes (vehicles, animals, packages)
- ✅ **Confidence Thresholds** - Configurable minimum confidence levels

### Object Identification
- 🏷️ **Named Objects** - Identify specific vehicles, pets, or items
- 📊 **Detection Grouping** - View all detections of identified objects
- 📈 **Detection Statistics** - Track frequency and patterns
- 🔍 **Search & Filter** - Find detections by class, name, camera, or date

### Smart Notifications
- 🔔 **Class-Based Alerts** - Notify on any vehicle, animal, or package
- 🏷️ **Entity-Based Alerts** - Notify for specific identified objects
- 📧 **Multi-Channel** - Email, SMS, push notifications, webhooks
- ⏰ **Quiet Hours** - Respect do-not-disturb times
- 🚫 **Alert Throttling** - Prevent notification spam

### User Interface
- 📱 **Unified Detections Page** - View all detection types in one place
- 🎨 **Visual Timeline** - See detections on interactive timeline
- 📊 **Dashboard Statistics** - Quick overview of recent detections
- 🔍 **Advanced Filtering** - Filter by class, camera, date range, identified objects

---

## 📋 Requirements

### Hardware Requirements

**Minimum (CPU Mode)**:
- CPU: 4+ cores (Intel i5/AMD Ryzen 5 or better)
- RAM: 8GB (16GB recommended)
- Storage: 500MB for models

**Recommended (GPU Mode)**:
- GPU: NVIDIA GPU with 4GB+ VRAM
- CUDA: 11.0+ installed
- RAM: 16GB+
- Storage: 500MB for models

**Performance Expectations**:
- **CPU Mode (yolov8n)**: 5-10 FPS on quad-core CPU
- **GPU Mode (yolov8n)**: 30-60+ FPS on mid-range GPU
- **Nano Model (yolov8n)**: Fastest, good accuracy
- **Small Model (yolov8s)**: Balanced speed/accuracy
- **Medium/Large (yolov8m/l/x)**: Best accuracy, slower

### Software Requirements

**Backend Dependencies**:
```bash
ultralytics>=8.0.0      # YOLOv8 implementation
torch>=2.0.0            # PyTorch deep learning framework
torchvision>=0.15.0     # Computer vision utilities
opencv-python>=4.8.0    # Image processing
numpy>=1.24.0           # Numerical computing
scipy>=1.10.0           # Scientific computing
```

**Installation**:
```bash
cd opencv_surveillance
source venv/bin/activate
pip install -r requirements.txt
```

The first time object detection runs, YOLO will automatically download the model weights (~6MB for yolov8n).

---

## 🚀 Quick Start

### Step 1: Enable Object Detection

**Via System Settings Page**:
1. Navigate to **System & Alerts** page
2. Find "Object Detection" section
3. Toggle **Enable Object Detection** to ON
4. Select model size (yolov8n recommended to start)
5. Choose device: **CPU** (compatible) or **CUDA** (requires NVIDIA GPU)
6. Set confidence threshold (0.5 = 50% confidence minimum)
7. Click **Save Settings**

**Via Database** (Advanced):
```sql
-- Enable object detection globally
INSERT INTO system_settings (key, value, value_type)
VALUES ('object_detection_enabled', 'true', 'boolean')
ON CONFLICT(key) DO UPDATE SET value='true';

-- Configure model
INSERT INTO system_settings (key, value, value_type)
VALUES ('object_detection_model', 'yolov8n', 'string');
```

### Step 2: Configure Detection Classes

Choose which object classes to detect:

**Default Classes** (recommended):
- ✅ **Vehicles** - cars, trucks, motorcycles, buses
- ✅ **Animals** - dogs, cats, birds, horses
- ✅ **Packages** - backpacks, handbags, suitcases

**Person Detection** is handled by face recognition system (disabled in object detection by default to avoid duplicates).

**Configuration**:
1. Go to **System Settings**
2. Under "Object Detection Classes", select:
   - Vehicle Detection
   - Animal Detection
   - Package Detection
3. Click **Save**

### Step 3: View Detections

**Dashboard Overview**:
- Navigate to **Live Dashboard**
- See real-time object detection statistics banner
- View counts: 🚗 Vehicles, 🐾 Animals, 📦 Packages

**All Detections Page**:
1. Navigate to **All Detections** (🔍 in sidebar)
2. Use tabs to filter: All | People | Vehicles | Animals | Packages
3. View detection cards with:
   - Object class and subclass
   - Camera name
   - Timestamp
   - Confidence score
   - Thumbnail (if available)

**Timeline View**:
1. Navigate to **Timeline Playback** (📊 in sidebar)
2. See object detection events marked with 🔍 icon
3. Hover to see object class details
4. Click to jump to that moment in recording

---

## 🏷️ Identifying Specific Objects

Track specific vehicles, pets, or belongings by giving them names.

### Create Identified Object

**Via Detections Page**:
1. Go to **All Detections** page
2. Find a detection you want to identify
3. Click **Identify** button on detection card
4. Enter details:
   - **Name**: "John's Tesla", "My Dog Rex", "Delivery Van"
   - **Object Class**: vehicle, animal, or package
   - **Description**: Optional notes
5. Click **Save**

**Via API** (Advanced):
```bash
curl -X POST http://localhost:8000/api/objects/identified \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "object_id": "johns_tesla",
    "name": "John'\''s Tesla",
    "object_class": "vehicle",
    "description": "Blue Tesla Model 3"
  }'
```

### View Identified Objects

**All Detections Page**:
- Filter by identified object name
- See all historical detections of that object
- View detection frequency and patterns

**Statistics**:
- Total detections count
- First seen date
- Last seen date
- Detection timeline graph

### Link Detection to Identified Object

When a new detection matches an identified object:
1. System attempts automatic matching (future enhancement)
2. Manual linking available via detection card
3. Click **Link to Identified Object**
4. Select from dropdown of existing identified objects
5. Future detections may be auto-linked based on visual similarity

---

## 🔔 Configuring Notifications

Get alerted when objects are detected.

### Enable Object Detection Alerts

1. Navigate to **System & Alerts** → **Alert Settings**
2. Scroll to **Object Detection Alerts (v3.10.0)** section
3. Toggle **Enable Object Detection Alerts** (master toggle)
4. Enable specific alert types:

**Alert Types**:
- 🚗 **Vehicle Detection Alerts** - Any car, truck, motorcycle detected
- 🐾 **Animal Detection Alerts** - Any dog, cat, bird detected
- 📦 **Package Detection Alerts** - Any box, bag, suitcase detected
- 🏷️ **Identified Object Alerts** - Specific named objects detected

### Configure Notification Channels

**Email Notifications**:
1. Enable **Email Notifications**
2. Enter recipient email address
3. Configure SMTP settings (see Email section)
4. Click **Test** to verify

**SMS Notifications**:
1. Enable **SMS Notifications**
2. Enter phone number (E.164 format: +1234567890)
3. Configure Twilio credentials (see SMS section)
4. Click **Test** to verify

**Push Notifications**:
- Enable **Push Notifications**
- Enter Firebase FCM server key
- Register device tokens

**Webhooks**:
- Enable **Webhook Notifications**
- Enter webhook URL
- Configure custom headers (optional)

### Alert Throttling

Prevent notification spam with throttling:

**Min Seconds Between Alerts**:
- Default: 300 seconds (5 minutes)
- Recommended: 180-600 seconds
- Per-class throttling: Vehicle alerts separate from animal alerts
- Per-object throttling: "John's Tesla" alerts separate from "Jane's Honda"

**Example**:
- If "John's Tesla" is detected at 2:00 PM
- And detected again at 2:03 PM
- Second alert is throttled (within 5-minute window)
- Alert sent again at 2:06 PM if still detecting

### Quiet Hours

Disable alerts during specific hours:

1. Enable **Quiet Hours**
2. Set **Start Time**: 22:00 (10:00 PM)
3. Set **End Time**: 07:00 (7:00 AM)
4. Alerts are suppressed during this window
5. Detections still recorded, just not notified

---

## 📊 Understanding Detection Results

### Detection Confidence

Each detection includes a confidence score (0-100%):

- **90-100%**: Very high confidence - object clearly identified
- **70-89%**: High confidence - object likely correct
- **50-69%**: Medium confidence - object probably correct
- **Below 50%**: Low confidence - filtered out by default

**Adjusting Confidence Threshold**:
- Lower threshold (e.g., 0.3): More detections, more false positives
- Higher threshold (e.g., 0.7): Fewer detections, higher accuracy
- Recommended: 0.5 (50%) for balanced results

### Object Classes

**YOLO COCO Dataset** includes 80 classes organized into categories:

**Vehicles** (15 classes):
- car, truck, bus, motorcycle, bicycle
- train, boat, airplane

**Animals** (20+ classes):
- dog, cat, bird, horse, sheep, cow
- elephant, bear, zebra, giraffe

**Packages/Items** (15+ classes):
- backpack, handbag, suitcase
- umbrella, bottle, cup

**Indoor Objects** (30+ classes):
- chair, couch, bed, dining table
- laptop, keyboard, mouse, cell phone
- book, clock, vase, scissors

**Full class list**: See `backend/core/object_detection.py` `CLASS_MAPPINGS` dictionary

### Detection Accuracy

**Factors Affecting Accuracy**:
- ✅ **Good Lighting** - Daylight or well-lit areas
- ✅ **Clear View** - Unobstructed camera angle
- ✅ **Object Size** - Larger objects easier to detect
- ✅ **Camera Resolution** - 720p+ recommended
- ❌ **Poor Lighting** - Night/darkness reduces accuracy
- ❌ **Partial Occlusion** - Objects partially hidden
- ❌ **Motion Blur** - Fast-moving objects
- ❌ **Distance** - Very small/distant objects

**Improving Accuracy**:
1. Use higher resolution cameras (1080p/4K)
2. Ensure good lighting (add external lights)
3. Position cameras for clear object views
4. Use larger YOLO model (yolov8s/m for better accuracy)
5. Enable GPU acceleration for faster processing
6. Increase confidence threshold to reduce false positives

---

## ⚙️ Advanced Configuration

### Model Selection

**YOLOv8 Model Variants**:

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| yolov8n | 6MB | Fastest | Good | CPU mode, multiple cameras |
| yolov8s | 22MB | Fast | Better | Balanced speed/accuracy |
| yolov8m | 52MB | Medium | High | GPU recommended |
| yolov8l | 87MB | Slow | Higher | GPU required, best accuracy |
| yolov8x | 131MB | Slowest | Highest | GPU required, research-grade |

**Changing Model**:
```python
# Via system settings
UPDATE system_settings
SET value = 'yolov8s'
WHERE key = 'object_detection_model';

# Restart detection to apply
```

### GPU Acceleration

**Enable CUDA** (NVIDIA GPUs only):

1. **Verify GPU**:
```bash
nvidia-smi  # Should show your GPU
```

2. **Install CUDA** (if not installed):
- Download from NVIDIA website
- Install CUDA Toolkit 11.0+
- Install cuDNN library

3. **Install PyTorch with CUDA**:
```bash
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

4. **Configure OpenEye**:
```sql
UPDATE system_settings
SET value = 'cuda'
WHERE key = 'object_detection_device';
```

5. **Verify**:
```python
import torch
print(torch.cuda.is_available())  # Should print True
```

### Processing Frequency

Control how often frames are analyzed:

**Detection Cooldown** (default: 3 seconds):
- Lower value (1-2s): More frequent detection, higher CPU/GPU usage
- Higher value (5-10s): Less frequent detection, lower resource usage

**Configuration**:
```python
# In backend/core/object_detector.py
self.detection_cooldown = 3.0  # Seconds between detections
```

**Recommendation**:
- **Multiple Cameras**: 5-10 seconds
- **Single Camera**: 2-3 seconds
- **GPU Available**: 1-2 seconds
- **CPU Only**: 5-10 seconds

### Memory Management

**Buffer Size** (default: 20 detections):
- Stores recent detections in memory for quick access
- Increase for longer history (uses more RAM)
- Decrease for memory-constrained systems

```python
# In backend/core/object_detector.py
self.max_buffer_size = 20
```

---

## 🐛 Troubleshooting

### Object Detection Not Working

**Symptoms**: No objects detected, feature appears disabled

**Solutions**:
1. **Check if enabled**:
   - Go to System Settings
   - Verify "Object Detection" toggle is ON

2. **Check model download**:
   ```bash
   ls ~/.cache/torch/hub/ultralytics_yolov8
   # Should contain yolov8n.pt or similar
   ```

3. **Check logs**:
   ```bash
   tail -f logs/app.log | grep -i "object"
   # Look for initialization errors
   ```

4. **Verify dependencies**:
   ```bash
   pip list | grep -E "ultralytics|torch"
   # Should show ultralytics>=8.0.0, torch>=2.0.0
   ```

### Poor Detection Accuracy

**Symptoms**: Many false positives or missed objects

**Solutions**:
1. **Increase confidence threshold**: 0.5 → 0.7
2. **Improve lighting**: Add external lights or enable IR
3. **Upgrade camera**: Use 1080p or 4K resolution
4. **Use better model**: yolov8n → yolov8s or yolov8m
5. **Enable GPU**: CPU mode is less accurate
6. **Reposition camera**: Ensure clear, unobstructed view

### Slow Performance / High CPU Usage

**Symptoms**: Lag, dropped frames, high CPU usage

**Solutions**:
1. **Increase detection cooldown**: 3s → 10s
2. **Use smaller model**: yolov8s → yolov8n
3. **Reduce camera count**: Disable detection on some cameras
4. **Enable GPU acceleration**: Offload processing to GPU
5. **Lower camera resolution**: 4K → 1080p or 720p
6. **Disable other features temporarily**: Turn off face detection

### CUDA / GPU Errors

**Symptoms**: "CUDA out of memory", "No CUDA device found"

**Solutions**:
1. **Verify CUDA installation**:
   ```bash
   nvidia-smi
   nvcc --version
   ```

2. **Reinstall PyTorch with CUDA**:
   ```bash
   pip uninstall torch torchvision
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ```

3. **Check GPU memory**:
   ```bash
   nvidia-smi
   # GPU Memory: < 4GB may struggle with YOLO
   ```

4. **Fallback to CPU**:
   ```sql
   UPDATE system_settings SET value = 'cpu' WHERE key = 'object_detection_device';
   ```

### Notifications Not Sending

**Symptoms**: Detections work but no alerts received

**Solutions**:
1. **Check master toggle**: Enable "Object Detection Alerts"
2. **Check class toggles**: Enable specific classes (vehicles, animals, packages)
3. **Check throttling**: Wait 5+ minutes between detections
4. **Check quiet hours**: Alerts disabled during quiet hours
5. **Test notification channels**: Use "Test" button in Alert Settings
6. **Check logs**:
   ```bash
   tail -f logs/app.log | grep -i "alert"
   # Look for throttling or error messages
   ```

---

## 📚 API Reference

### List Detections

**Endpoint**: `GET /api/objects/detections/history`

**Parameters**:
- `camera_id` (optional): Filter by camera
- `object_class` (optional): Filter by class (vehicle, animal, package)
- `identified_object_id` (optional): Filter by identified object
- `start_date` (optional): Start of date range (ISO 8601)
- `end_date` (optional): End of date range (ISO 8601)
- `page` (default: 1): Page number
- `page_size` (default: 20): Items per page

**Example**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/objects/detections/history?object_class=vehicle&page=1&page_size=20"
```

**Response**:
```json
{
  "data": [
    {
      "id": 123,
      "camera_id": "front_door",
      "object_class": "vehicle",
      "object_subclass": "car",
      "confidence": 0.92,
      "detected_at": "2025-11-15T10:30:00Z",
      "bbox_x": 100,
      "bbox_y": 50,
      "bbox_width": 200,
      "bbox_height": 150,
      "identified_object_name": "John's Tesla"
    }
  ],
  "total": 1543,
  "page": 1,
  "page_size": 20,
  "total_pages": 78
}
```

### Detection Statistics

**Endpoint**: `GET /api/objects/detections/statistics`

**Parameters**:
- `camera_id` (optional): Filter by camera
- `days` (optional): Number of days to include (default: 7)

**Example**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/objects/detections/statistics?days=30"
```

**Response**:
```json
{
  "total_detections": 1543,
  "by_class": {
    "vehicle": 892,
    "animal": 421,
    "package": 230,
    "person": 0
  },
  "by_camera": {
    "front_door": 654,
    "driveway": 512,
    "backyard": 377
  },
  "recent_detections": [
    {
      "id": 123,
      "object_class": "vehicle",
      "detected_at": "2025-11-15T10:30:00Z"
    }
  ]
}
```

### Create Identified Object

**Endpoint**: `POST /api/objects/identified`

**Request Body**:
```json
{
  "object_id": "johns_tesla",
  "name": "John's Tesla",
  "object_class": "vehicle",
  "description": "Blue Tesla Model 3"
}
```

**Response**:
```json
{
  "id": 5,
  "object_id": "johns_tesla",
  "name": "John's Tesla",
  "object_class": "vehicle",
  "description": "Blue Tesla Model 3",
  "detection_count": 0,
  "first_seen_at": null,
  "last_seen_at": null,
  "created_at": "2025-11-15T10:35:00Z"
}
```

### List Identified Objects

**Endpoint**: `GET /api/objects/identified`

**Parameters**:
- `object_class` (optional): Filter by class

**Example**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/objects/identified?object_class=vehicle"
```

### Update Identified Object

**Endpoint**: `PUT /api/objects/identified/{object_id}`

**Request Body**:
```json
{
  "name": "John's New Tesla",
  "description": "Red Tesla Model Y"
}
```

### Delete Identified Object

**Endpoint**: `DELETE /api/objects/identified/{object_id}`

**Response**: 204 No Content

---

## 💡 Use Cases & Examples

### Use Case 1: Driveway Vehicle Monitoring

**Goal**: Get notified when any vehicle enters driveway

**Setup**:
1. Enable object detection with class filter: `["vehicle"]`
2. Position camera to view driveway entrance
3. Enable "Vehicle Detection Alerts" in Alert Settings
4. Configure email/SMS notifications
5. Set throttling to 5 minutes to avoid duplicate alerts

**Result**: Receive alert when car enters driveway, with snapshot and timestamp

### Use Case 2: Package Delivery Detection

**Goal**: Know immediately when packages are delivered

**Setup**:
1. Enable object detection with class filter: `["package"]`
2. Position camera to view front porch/doorstep
3. Enable "Package Detection Alerts"
4. Set throttling to 2 minutes (packages may be quickly grabbed)
5. Configure push notifications for instant alerts

**Result**: Get instant notification when delivery person leaves package

### Use Case 3: Pet Activity Monitoring

**Goal**: Track when your dog goes outside

**Setup**:
1. Enable object detection with class filter: `["animal"]`
2. Create identified object: "My Dog Rex" (object_class: animal)
3. Link initial detections to "My Dog Rex"
4. Enable "Identified Object Alerts" for "My Dog Rex"
5. Set throttling to 15 minutes

**Result**: Get notified each time Rex goes outside, with activity timeline

### Use Case 4: Specific Vehicle Arrival

**Goal**: Know when your spouse arrives home

**Setup**:
1. Enable object detection with class filter: `["vehicle"]`
2. Create identified object: "Jane's Honda" (object_class: vehicle)
3. Link Jane's car detections to identified object
4. Enable "Identified Object Alerts"
5. Disable generic "Vehicle Detection Alerts" (to only get Jane's car alerts)

**Result**: Only receive alerts for Jane's specific vehicle, not all vehicles

---

## 🔒 Security & Privacy

### Data Storage

**Local Storage**:
- All object detections stored in local SQLite database
- Detection images stored in `data/snapshots/` directory
- No cloud uploads unless cloud storage explicitly enabled

**Database Encryption**:
- Database file can be encrypted at rest (see Security Guide)
- Identified object names stored as plain text for search

### Privacy Considerations

**YOLO Model**:
- Runs 100% locally on your server
- No data sent to external services
- No internet connection required (after model download)

**Detection Data**:
- Bounding boxes (coordinates) stored, not full images
- Optional: Disable snapshot storage to save disk space
- Retention: Configure auto-delete after X days

**Identified Objects**:
- Names/descriptions visible to all users with dashboard access
- Consider generic names (e.g., "Vehicle 1" instead of "John's Tesla")

### Access Control

**Authentication**:
- All API endpoints require JWT authentication
- Tokens expire after 30 minutes (configurable)
- Refresh tokens for extended sessions

**Permissions** (future enhancement):
- Role-based access control (RBAC)
- Restrict identified object creation to admins
- View-only access for regular users

---

## 🎓 Best Practices

### Camera Placement

1. **Height**: Mount cameras 8-12 feet high for optimal object view
2. **Angle**: 15-30 degree downward angle works best
3. **Lighting**: Ensure good lighting or enable IR night vision
4. **Coverage**: Overlap camera views for better tracking
5. **Background**: Avoid busy/complex backgrounds

### Model Selection

1. **Start Small**: Begin with yolov8n to test performance
2. **Upgrade If Needed**: Move to yolov8s/m if accuracy insufficient
3. **GPU Recommended**: For yolov8m/l/x models
4. **Monitor Resources**: Check CPU/GPU usage and adjust

### Alert Configuration

1. **Class-Based First**: Start with broad class alerts (all vehicles)
2. **Refine Over Time**: Add identified objects as patterns emerge
3. **Throttling**: Set appropriate cooldowns (5-10 minutes typical)
4. **Quiet Hours**: Enable for bedroom cameras
5. **Test Channels**: Always test notification channels before relying on them

### Performance Optimization

1. **Detection Cooldown**: Increase if CPU usage too high
2. **Camera Selection**: Disable detection on less-important cameras
3. **Model Size**: Use smallest model that meets accuracy needs
4. **Resolution**: Lower camera resolution if processing struggles
5. **Batch Processing**: Process multiple cameras on same schedule

---

## 📖 Additional Resources

- **YOLOv8 Documentation**: https://docs.ultralytics.com/
- **COCO Dataset**: https://cocodataset.org/
- **PyTorch CUDA Guide**: https://pytorch.org/get-started/locally/
- **OpenEye API Reference**: `/docs/API_REFERENCE.md`
- **System Settings**: `/docs/features/HARDWARE_AWARE_FEATURES_v3.7.0.md`
- **Notification Setup**: `/docs/features/NOTIFICATION_SETTINGS_FEATURE.md`

---

## 🆘 Getting Help

**Documentation**:
- Main README: `/README.md`
- User Guide: `/docs/USER_GUIDE.md`
- Quick Reference: `/docs/QUICK_REFERENCE.md`

**Support**:
- GitHub Issues: https://github.com/anthropics/openeye/issues
- Discussions: https://github.com/anthropics/openeye/discussions
- Email: support@openeye.ai (if available)

**Logs**:
- Application logs: `logs/app.log`
- Object detection logs: `grep "object" logs/app.log`
- Alert logs: Check notification_logs table in database

---

**Version**: 3.10.0
**Last Updated**: 2025-11-15
**Author**: OpenEye Development Team
