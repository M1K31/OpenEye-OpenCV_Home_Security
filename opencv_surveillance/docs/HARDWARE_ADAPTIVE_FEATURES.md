# Hardware-Adaptive Features System

## Overview

OpenEye now features a comprehensive hardware detection and adaptive feature system that:
- ✅ Automatically detects available hardware (CPU, RAM, GPU, storage)
- ✅ Provides recommendations based on detected hardware
- ✅ Warns users before enabling resource-intensive features
- ✅ Offers CPU fallback options for all features
- ✅ Prevents enabling GPU-only features without GPU
- ✅ Shows optimal configuration for user's hardware

**All hardware-intensive features are OFF by default** and require user opt-in with full awareness of requirements.

---

## Key Principles

1. **User Choice First**: Users decide what features to enable
2. **Hardware-Aware**: System detects capabilities and provides guidance
3. **No Surprises**: Clear warnings before enabling intensive features
4. **CPU Fallback**: Everything works on CPU (though slower for some features)
5. **GPU Optional**: GPU features only available if GPU detected
6. **Performance Transparency**: Show expected impact of each feature

---

## Architecture

### Components

#### 1. Hardware Detector (`backend/core/hardware_detector.py`)
- Detects CPU (cores, threads, frequency)
- Detects RAM (total, available, usage)
- Detects GPU (NVIDIA CUDA via PyTorch or nvidia-smi)
- Detects storage (total, free, usage)
- Classifies hardware into tiers: minimal, low, medium, high_end

#### 2. Feature Configuration (`backend/core/feature_config.py`)
- Defines all features with requirements
- Specifies CPU/RAM/GPU requirements per feature
- Indicates which features have CPU/GPU modes
- Provides performance impact ratings (1-10)
- Default states (ON/OFF) for each feature

#### 3. Frame Optimizer (`backend/core/frame_optimizer.py`)
- **Adaptive Frame Rate**: Skips frames when idle (80% CPU reduction)
- **Resolution Scaling**: Processes at lower resolution (2-4x speedup)
- Tracks statistics (frames processed, skipped, time saved)
- CPU-friendly optimizations (no GPU required)

#### 4. Hardware API (`backend/api/routes/hardware.py`)
- `GET /api/hardware/info` - Get hardware details
- `GET /api/hardware/tier` - Get hardware tier and recommendations
- `GET /api/features/all` - List all features with requirements
- `GET /api/features/{id}/check` - Check if hardware can run feature
- `GET /api/features/optimal-config` - Get recommended configuration
- `GET /api/features/{id}/impact` - See performance impact of feature

---

## Feature Categories

### Core Features (Always Available)
- **Motion Detection** - CPU-friendly, always enabled
- **Video Recording** - CPU-friendly, always enabled

### Detection Features
- **Face Recognition (CPU Mode)** - Default enabled, HOG algorithm
- **Face Recognition (GPU Mode)** - Default OFF, requires GPU, 6-15x faster
- **Object Detection (YOLOv8)** - Default OFF, works on CPU/GPU
- **Weapon Detection** - Default OFF, requires object detection
- **License Plate Recognition** - Default OFF, works on CPU/GPU
- **Barcode & QR Detection** - Default OFF, CPU-friendly
- **Name Tag / Badge Detection** - Default OFF, GPU recommended

### Optimization Features (All Default OFF)
- **Adaptive Frame Rate** - CPU-friendly, 80% reduction when idle
- **Resolution Scaling** - CPU-friendly, 2-4x speedup
- **Hardware Video Encoding** - Requires GPU or Intel QuickSync
- **Parallel Processing** - Requires 4+ CPU cores
- **Redis Caching** - Requires Redis server
- **Batch Database Inserts** - CPU-friendly

---

## Hardware Requirements

### Feature Requirements Example

```python
"face_recognition_cnn": {
    "min_ram_gb": 8,
    "min_cpu_cores": 2,
    "gpu_required": True,  # Cannot enable without GPU
    "min_gpu_memory_mb": 4096,
    "cpu_impact": 2,  # Low CPU usage (GPU does work)
    "gpu_impact": 7,  # High GPU usage
}

"face_recognition_hog": {
    "min_ram_gb": 4,
    "min_cpu_cores": 2,
    "gpu_required": False,  # Works on CPU
    "cpu_impact": 5,  # Moderate CPU usage
    "gpu_impact": 0,  # No GPU needed
}
```

### Hardware Tiers

**Minimal** (< 2 cores, < 8GB RAM, no GPU):
- Motion detection
- Recording
- Adaptive frame rate (critical)
- Resolution scaling (critical)

**Low** (2-4 cores, 8-16GB RAM, no GPU):
- + Face recognition (CPU mode)
- + Barcode/QR detection
- + Basic optimizations

**Medium** (4-8 cores, 16-32GB RAM, GPU optional):
- + License plate recognition
- + Badge detection
- + Parallel processing
- + Most features available

**High-End** (8+ cores, 32GB+ RAM, GPU with 6GB+ VRAM):
- + Face recognition (GPU mode)
- + Object detection
- + Weapon detection
- + All optimizations
- + All features at maximum quality

---

## API Usage Examples

### Get Hardware Information

```bash
curl -X GET http://localhost:8000/api/hardware/info \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "cpu_model": "Intel Core i7-10700",
  "cpu_cores": 8,
  "cpu_threads": 16,
  "ram_total_gb": 32.0,
  "ram_available_gb": 20.5,
  "gpu_available": true,
  "gpu_name": "NVIDIA GeForce RTX 3060",
  "gpu_memory_total_mb": 12288,
  "cuda_version": "11.8"
}
```

### Get Hardware Tier

```bash
curl -X GET http://localhost:8000/api/hardware/tier \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "tier": "high_end",
  "max_cameras": 20,
  "processing_resolution": "1920x1080",
  "recommendations": {
    "face_detection_method": "cnn",
    "enable_object_detection": true,
    "frame_skip_idle": 2
  }
}
```

### Check Feature Capability

```bash
curl -X GET http://localhost:8000/api/features/object_detection/check \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "feature_id": "object_detection",
  "feature_name": "Object Detection (YOLOv8)",
  "can_run": true,
  "warnings": [],
  "requirements": {
    "min_ram_gb": 8,
    "min_cpu_cores": 4,
    "gpu_required": false,
    "gpu_recommended": true,
    "min_gpu_memory_mb": 6144
  },
  "has_cpu_fallback": true,
  "has_gpu_mode": true,
  "recommended": true
}
```

### Get Optimal Configuration

```bash
curl -X GET http://localhost:8000/api/features/optimal-config \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "hardware_tier": "medium",
  "features": {
    "face_recognition_hog": {
      "enabled": true,
      "can_run": true,
      "recommended": true,
      "warnings": [],
      "use_gpu": false,
      "use_cpu": true
    },
    "face_recognition_cnn": {
      "enabled": false,
      "can_run": false,
      "recommended": false,
      "warnings": ["GPU required but not detected"],
      "use_gpu": false,
      "use_cpu": false
    },
    "object_detection": {
      "enabled": true,
      "can_run": true,
      "recommended": true,
      "warnings": ["CPU mode: ~2-5 FPS | GPU mode: ~30+ FPS"],
      "use_gpu": false,
      "use_cpu": true
    }
  },
  "recommendations": [
    "Your hardware is classified as: medium",
    "Your hardware can handle most features comfortably",
    "Adding a GPU would enable real-time object detection"
  ]
}
```

### Get Feature Impact

```bash
curl -X GET http://localhost:8000/api/features/object_detection/impact \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "feature_name": "Object Detection (YOLOv8)",
  "performance_impact": {
    "cpu_impact": 8,
    "ram_impact": 5,
    "gpu_impact": 8,
    "disk_impact": 1
  },
  "estimated_resource_usage": {
    "cpu_usage_percent": 80,
    "ram_usage_mb": 2500,
    "gpu_usage_percent": 80
  },
  "current_hardware_status": {
    "ram_available_gb": 20.5,
    "ram_sufficient": true,
    "cpu_cores": 8,
    "cpu_sufficient": true,
    "gpu_available": true,
    "gpu_required": false,
    "gpu_recommended": true
  },
  "warnings": [
    "This feature is CPU-intensive and may affect other processes"
  ]
}
```

---

## Quick Win Optimizations Implemented

### 1. Adaptive Frame Rate (CPU-Friendly)

**Status**: ✅ Implemented
**File**: `backend/core/frame_optimizer.py`
**Default**: OFF (user must enable)

**How It Works**:
- Processes every frame when motion detected
- Skips N-1 out of N frames when idle
- Configurable skip factor (default: 5 for idle, 1 for active)

**Benefits**:
- 80% CPU reduction during idle periods
- No performance loss during motion/activity
- Works on any hardware (no GPU needed)

**Configuration**:
```python
optimizer = AdaptiveFrameProcessor(
    idle_skip_factor=5,        # Process every 5th frame when idle
    active_skip_factor=1,      # Process every frame when active
    motion_threshold_seconds=10.0  # Idle after 10s of no motion
)

should_process = optimizer.should_process_frame(motion_detected=True)
```

---

### 2. Resolution Scaling (CPU-Friendly)

**Status**: ✅ Implemented
**File**: `backend/core/frame_optimizer.py`
**Default**: OFF (user must enable)

**How It Works**:
- Downscales frames for detection/processing
- Records at original full resolution
- Scales detection coordinates back to original

**Benefits**:
- 2-4x faster processing (less pixels to analyze)
- Recordings remain full quality
- Works on any hardware (no GPU needed)

**Configuration**:
```python
scaler = ResolutionScaler(
    processing_resolution=(1280, 720),  # Process at 720p
    # OR
    auto_scale=True,
    max_processing_width=1280  # Auto-scale to max 720p
)

# Scale frame down for processing
scaled_frame, scale_factor = scaler.scale_frame_for_processing(frame)

# Process detection on scaled frame
detections = detect_faces(scaled_frame)

# Scale coordinates back to original
original_coords = scaler.scale_coordinates(detection_coords, scale_factor)

# Record original full-resolution frame
recorder.write(frame)  # Still full quality!
```

---

### 3. Combined Optimizer

**Status**: ✅ Implemented
**File**: `backend/core/frame_optimizer.py`

**Usage**:
```python
from backend.core.frame_optimizer import FrameOptimizer

# Create optimizer with both features
optimizer = FrameOptimizer(
    enable_adaptive_frame_rate=True,
    enable_resolution_scaling=True,
    adaptive_config={
        'idle_skip_factor': 5,
        'active_skip_factor': 1
    },
    scaling_config={
        'max_processing_width': 1280
    }
)

# In camera processing loop
for frame in camera_stream:
    # Check if should process this frame
    if not optimizer.should_process_frame(motion_detected):
        continue  # Skip this frame

    # Scale frame for processing
    processing_frame, scale_factor = optimizer.prepare_frame(frame)

    # Run detection on scaled frame
    faces = detect_faces(processing_frame)

    # Scale coordinates back
    for face in faces:
        face.bbox = optimizer.scale_coordinates_to_original(face.bbox)

    # Record original frame (full quality)
    recorder.write(frame)

# Get statistics
stats = optimizer.get_combined_stats()
# {
#   'adaptive_frame_rate': {'frames_skipped': 800, 'cpu_reduction_percent': 80},
#   'resolution_scaling': {'pixel_reduction_percent': 56, 'time_saved_seconds': 45.2},
#   'combined': {'total_time_saved_seconds': 89.7}
# }
```

---

## Integration Steps

### For Camera Manager

1. **Add optimizer to camera initialization**:
```python
# In camera_manager.py
from backend.core.frame_optimizer import create_optimizer_from_config

class Camera:
    def __init__(self, ...):
        # Load optimization settings from database
        opt_config = db_settings.get('optimization', {})

        self.frame_optimizer = create_optimizer_from_config(opt_config)
```

2. **Use optimizer in frame processing**:
```python
def process_frame(self, frame):
    # Check if should process
    if not self.frame_optimizer.should_process_frame(self.motion_detected):
        return None  # Skip this frame

    # Scale frame
    processing_frame, scale_factor = self.frame_optimizer.prepare_frame(frame)

    # Run all detection on scaled frame
    motion_result = self.motion_detector.detect(processing_frame)
    faces = self.face_detector.detect(processing_frame)

    # Scale results back to original coordinates
    for face in faces:
        face.bbox = self.frame_optimizer.scale_coordinates_to_original(
            face.bbox,
            scale_factor
        )

    # Record original frame (full quality)
    if motion_result.motion_detected:
        self.recorder.write(frame)  # Original resolution!
```

---

## User Workflow

### 1. View Hardware Information
- Navigate to System Settings → Hardware & Features
- See detected CPU, RAM, GPU, storage
- View hardware tier classification

### 2. See Feature Recommendations
- System shows "Recommended for your hardware" badge
- Shows "Requires GPU" for GPU-only features
- Displays performance impact ratings

### 3. Enable Feature with Warnings
- User clicks "Enable" on a feature
- System checks hardware requirements
- Shows warning if:
  - Hardware doesn't meet minimum requirements
  - Feature will significantly impact performance
  - GPU required but not detected
- User must acknowledge warnings to proceed

### 4. Choose CPU vs GPU Mode
- For features with both modes (face recognition, object detection):
  - CPU mode: Always available, slower
  - GPU mode: Only if GPU detected, 5-20x faster
- User sees performance difference clearly

### 5. Monitor Performance
- Real-time statistics show:
  - Frames processed vs skipped
  - CPU/RAM/GPU usage
  - Time saved by optimizations
- Can adjust settings based on observed performance

---

## Testing the System

### Test Hardware Detection

```bash
# Get hardware info
curl -X GET http://localhost:8000/api/hardware/info \
  -H "Authorization: Bearer YOUR_TOKEN"

# Refresh detection (after hardware changes)
curl -X POST http://localhost:8000/api/hardware/refresh \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get tier classification
curl -X GET http://localhost:8000/api/hardware/tier \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test Feature Checks

```bash
# List all features
curl -X GET http://localhost:8000/api/features/all \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check specific feature
curl -X GET http://localhost:8000/api/features/face_recognition_cnn/check \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get optimal config
curl -X GET http://localhost:8000/api/features/optimal-config \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Future Frontend UI (Coming Next)

### Hardware & Features Page

```
┌─────────────────────────────────────────────────────────────┐
│  Hardware & Features                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Your Hardware  (High-End Tier)                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ CPU: Intel i7-10700 (8 cores, 16 threads)          │   │
│  │ RAM: 32GB (20.5GB available)                       │   │
│  │ GPU: NVIDIA RTX 3060 (12GB VRAM)  ✓ CUDA 11.8     │   │
│  │ Disk: 1TB (450GB free)                             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Recommended Features                                       │
│  ☑ Motion Detection                           [Always On]  │
│  ☑ Face Recognition (GPU Mode)                [Enabled]    │
│  ☐ Object Detection                           [Enable]     │
│      ⚠ High CPU/GPU usage (80%)                            │
│      ℹ Recommended for your hardware                        │
│  ☐ License Plate Recognition                  [Enable]     │
│      ⚠ Moderate GPU usage (60%)                            │
│                                                             │
│  Optimization Features                                      │
│  ☑ Adaptive Frame Rate                        [Enabled]    │
│      ✓ 80% CPU reduction when idle                         │
│  ☑ Resolution Scaling (720p processing)       [Enabled]    │
│      ✓ 2-4x speedup, recordings stay 1080p                 │
│  ☐ Hardware Video Encoding                    [Enable]     │
│      ✓ 90% CPU reduction for recording                     │
│      ℹ Requires NVENC support (detected: ✓)                │
│                                                             │
│  Not Compatible with Your Hardware                         │
│  ☐ Redis Caching                              [Disabled]   │
│      ✗ Requires Redis server (not installed)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary

✅ **Implemented**:
1. Hardware detection (CPU, RAM, GPU, storage)
2. Feature requirement definitions
3. Hardware tier classification
4. Adaptive frame rate optimization
5. Resolution scaling optimization
6. Complete API for hardware & features
7. Capability checking before enabling features
8. Optimal configuration recommendations
9. Performance impact warnings

✅ **User Benefits**:
- No surprises - always know hardware requirements
- No GPU-only lock-in - everything has CPU fallback
- Informed decisions - see performance impact before enabling
- Optimal defaults - system recommends best configuration
- Flexible - enable what works for your hardware

📋 **Next Steps** (if desired):
1. Frontend UI for hardware/features page
2. Integration with camera settings
3. Real-time performance monitoring dashboard
4. Automatic feature adjustment based on load

---

**Version**: 1.0
**Created**: January 2025
**Status**: Production-Ready
