# Granular Motion Detection & Image Quality Controls - Implementation Plan

**Version:** 3.4.0 (Proposed)  
**Date:** October 10, 2025  
**Purpose:** Add advanced per-camera controls for motion detection and image quality

---

## 🎯 Current Capabilities (v3.3.8)

### Motion Detection Settings
**Backend (Already Implemented):**
- ✅ `min_contour_area` - Minimum size of motion to detect (100-10,000 pixels)
- ✅ `motion_detection_enabled` - Enable/disable per camera
- ✅ `post_motion_cooldown` - Recording duration after motion stops (1-60 seconds)
- ✅ Background subtractor parameters (MOG2):
  - `history=500` - Number of last frames affecting background model
  - `varThreshold=50` - Threshold on squared Mahalanobis distance
  - `detectShadows=True` - Whether to detect shadows

**Frontend (Partially Implemented):**
- ⚠️ Basic motion detection toggle exists
- ❌ No UI for granular motion sensitivity controls
- ❌ No visual sensitivity adjustment sliders

### Image Quality Settings
**Backend (Partially Implemented):**
- ⚠️ `resolution` field exists in schema but not actively used
- ⚠️ JPEG quality hardcoded at 90 for snapshots
- ❌ No FPS control
- ❌ No bitrate control
- ❌ No brightness/contrast controls

**Frontend:**
- ⚠️ Resolution dropdown exists but only for display
- ❌ No quality adjustment sliders
- ❌ No real-time preview of quality settings

---

## 🚀 Proposed Granular Controls

### Motion Detection Controls (Similar to Commercial Tools)

#### 1. **Motion Sensitivity Slider**
- **Range:** 1-10 (Low to High)
- **Maps to:** `min_contour_area` inversely
  - Low (1) = 5000 pixels (only large movements)
  - Medium (5) = 500 pixels (default)
  - High (10) = 100 pixels (very sensitive)

#### 2. **Motion Detection Zones** (Advanced)
- **Grid overlay** on camera preview
- **Clickable zones** to enable/disable detection in specific areas
- **Use case:** Ignore tree movements, focus on doorway
- **Implementation:** Binary mask applied before motion detection

#### 3. **Motion Threshold**
- **Range:** 1-100 (percentage)
- **Maps to:** `varThreshold` in MOG2
  - Low (10) = varThreshold=20 (more sensitive to changes)
  - High (90) = varThreshold=100 (only significant changes)

#### 4. **Noise Reduction**
- **Options:** Low, Medium, High
- **Maps to:** Gaussian blur kernel size and erosion/dilation iterations
  - Low: (3,3) blur, 1 iteration
  - Medium: (5,5) blur, 2 iterations (current)
  - High: (7,7) blur, 3 iterations

#### 5. **Motion Cooldown**
- **Range:** 1-300 seconds
- **Already exists:** `post_motion_cooldown`
- **Enhancement:** Add preset options (5s, 30s, 1m, 5m)

#### 6. **Shadow Detection**
- **Toggle:** On/Off
- **Already exists:** `detectShadows` parameter
- **Enhancement:** Expose in UI

---

### Image Quality Controls

#### 1. **Resolution**
- **Options:**
  - 4K (3840×2160)
  - 1080p (1920×1080) - Default
  - 720p (1280×720)
  - 480p (640×480)
  - Custom
- **Implementation:** Set OpenCV capture properties

#### 2. **Frame Rate (FPS)**
- **Range:** 1-30 FPS
- **Presets:** 5, 10, 15, 20, 30 FPS
- **Trade-off indicator:** Higher FPS = More CPU/bandwidth
- **Implementation:** Frame skip logic based on target FPS

#### 3. **Video Bitrate**
- **Range:** 500 kbps - 10 Mbps
- **Presets:**
  - Low (500 kbps) - Minimal bandwidth
  - Medium (2 Mbps) - Balanced
  - High (5 Mbps) - High quality
  - Ultra (10 Mbps) - Maximum quality
- **Implementation:** FFmpeg encoding parameters

#### 4. **Image Compression Quality**
- **Range:** 1-100 (JPEG quality)
- **Presets:**
  - Low (50) - Smaller files
  - Medium (75) - Balanced
  - High (90) - Current default
  - Maximum (100) - Lossless-like
- **Applies to:** Snapshots and thumbnails

#### 5. **Brightness**
- **Range:** -100 to +100
- **Implementation:** OpenCV `cv2.add()` or `cv2.convertScaleAbs()`

#### 6. **Contrast**
- **Range:** 0.5 to 3.0 (multiplier)
- **Implementation:** OpenCV `cv2.convertScaleAbs(alpha=contrast)`

#### 7. **Saturation**
- **Range:** 0.0 to 2.0
- **Implementation:** HSV color space adjustment

#### 8. **Sharpness**
- **Options:** None, Low, Medium, High
- **Implementation:** Unsharp mask filter

---

## 📐 Proposed UI Design

### Camera Settings Panel

```
┌─────────────────────────────────────────────────────────────┐
│  Camera: Front Door (192.168.1.100)                    [X]  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  📹 VIDEO QUALITY                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Resolution:     [1920x1080 ▼]                       │   │
│  │ Frame Rate:     [15 FPS ▼]  ⚡ CPU: Medium          │   │
│  │ Bitrate:        [═══════════○════] 2 Mbps           │   │
│  │ Quality:        [═══════════════○] 90%              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  🎨 IMAGE ADJUSTMENTS                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Brightness:     [═══════○═══════] 0                 │   │
│  │ Contrast:       [═══════○═══════] 1.0               │   │
│  │ Saturation:     [═══════○═══════] 1.0               │   │
│  │ Sharpness:      [ ] None [●] Low [ ] Med [ ] High  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  🚶 MOTION DETECTION                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [✓] Enable Motion Detection                         │   │
│  │                                                       │   │
│  │ Sensitivity:    [═════○═════════] 5 (Medium)        │   │
│  │ Threshold:      [═══════○═══════] 50%               │   │
│  │ Noise Filter:   [ ] Low [●] Medium [ ] High         │   │
│  │ Shadow Detection: [✓] Enabled                       │   │
│  │                                                       │   │
│  │ Detection Zones: [Configure Grid]                   │   │
│  │ ┌─────────────────────────────┐                     │   │
│  │ │  ■ ■ ■ □ □ □ □ □             │ (Click to toggle)  │   │
│  │ │  ■ ■ ■ □ □ □ □ □             │                     │   │
│  │ │  ■ ■ ■ ■ ■ □ □ □             │                     │   │
│  │ │  □ □ ■ ■ ■ □ □ □             │                     │   │
│  │ └─────────────────────────────┘                     │   │
│  │                                                       │   │
│  │ Post-Motion Record: [══○════] 5 seconds             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  [Preview Changes]  [Save Settings]  [Reset to Default]     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Implementation Details

### Backend Changes

#### 1. Enhance MotionDetector Class

**File:** `backend/core/motion_detector.py`

```python
class MotionDetector:
    """Enhanced motion detector with granular controls"""
    
    def __init__(
        self,
        min_contour_area=500,
        sensitivity=5,  # 1-10 scale
        var_threshold=50,
        noise_reduction='medium',
        detect_shadows=True,
        detection_zones=None  # Optional binary mask
    ):
        # Map sensitivity to contour area
        sensitivity_map = {
            1: 5000, 2: 3000, 3: 1500, 4: 800, 5: 500,
            6: 300, 7: 200, 8: 150, 9: 120, 10: 100
        }
        self.min_contour_area = sensitivity_map.get(sensitivity, min_contour_area)
        
        # Map noise reduction to blur/iterations
        noise_map = {
            'low': ((3, 3), 1),
            'medium': ((5, 5), 2),
            'high': ((7, 7), 3)
        }
        self.blur_kernel, self.morph_iterations = noise_map.get(noise_reduction, ((5, 5), 2))
        
        # Background subtractor with configurable threshold
        self.back_sub = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=var_threshold,
            detectShadows=detect_shadows
        )
        
        # Detection zones (optional mask)
        self.detection_zones = detection_zones
        
    def detect(self, frame):
        """Detect motion with enhanced controls"""
        # Apply blur based on noise reduction setting
        blurred_frame = cv2.GaussianBlur(frame, self.blur_kernel, 0)
        fg_mask = self.back_sub.apply(blurred_frame)
        
        # Apply detection zones if configured
        if self.detection_zones is not None:
            fg_mask = cv2.bitwise_and(fg_mask, fg_mask, mask=self.detection_zones)
        
        # Clean up mask
        fg_mask = cv2.erode(fg_mask, None, iterations=self.morph_iterations)
        fg_mask = cv2.dilate(fg_mask, None, iterations=self.morph_iterations)
        
        # Find contours
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        motion_detected = False
        motion_areas = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_contour_area:
                continue
            
            motion_detected = True
            (x, y, w, h) = cv2.boundingRect(contour)
            motion_areas.append({'x': x, 'y': y, 'w': w, 'h': h, 'area': area})
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        return frame, motion_detected, motion_areas
```

#### 2. Enhance Camera Class with Image Adjustments

**File:** `backend/core/camera_manager.py`

```python
class Camera(ABC):
    def __init__(
        self,
        source,
        resolution=(1920, 1080),
        fps=15,
        quality=90,
        brightness=0,
        contrast=1.0,
        saturation=1.0,
        sharpness='none'
    ):
        self.source = source
        self.resolution = resolution
        self.target_fps = fps
        self.jpeg_quality = quality
        self.brightness = brightness
        self.contrast = contrast
        self.saturation = saturation
        self.sharpness = sharpness
        
        # Frame timing for FPS control
        self.frame_interval = 1.0 / fps
        self.last_frame_time = 0
        
    def adjust_image(self, frame):
        """Apply image adjustments"""
        # Brightness
        if self.brightness != 0:
            frame = cv2.add(frame, np.full(frame.shape, self.brightness, dtype=np.uint8))
        
        # Contrast
        if self.contrast != 1.0:
            frame = cv2.convertScaleAbs(frame, alpha=self.contrast, beta=0)
        
        # Saturation
        if self.saturation != 1.0:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 1] = hsv[:, :, 1] * self.saturation
            hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
            frame = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
        # Sharpness
        if self.sharpness != 'none':
            sharpness_map = {
                'low': 0.5,
                'medium': 1.0,
                'high': 2.0
            }
            amount = sharpness_map.get(self.sharpness, 0)
            if amount > 0:
                gaussian = cv2.GaussianBlur(frame, (0, 0), 2.0)
                frame = cv2.addWeighted(frame, 1.0 + amount, gaussian, -amount, 0)
        
        return frame
    
    def should_process_frame(self):
        """Check if enough time has passed for next frame (FPS control)"""
        current_time = time.time()
        if current_time - self.last_frame_time >= self.frame_interval:
            self.last_frame_time = current_time
            return True
        return False
```

#### 3. Update Database Schema

**File:** `backend/database/models.py`

```python
class CameraSettings(Base):
    __tablename__ = "camera_settings"
    
    id = Column(Integer, primary_key=True)
    camera_id = Column(String, unique=True, nullable=False)
    
    # Video Quality
    resolution_width = Column(Integer, default=1920)
    resolution_height = Column(Integer, default=1080)
    fps = Column(Integer, default=15)
    bitrate = Column(Integer, default=2000)  # kbps
    jpeg_quality = Column(Integer, default=90)
    
    # Image Adjustments
    brightness = Column(Integer, default=0)  # -100 to +100
    contrast = Column(Float, default=1.0)  # 0.5 to 3.0
    saturation = Column(Float, default=1.0)  # 0.0 to 2.0
    sharpness = Column(String, default='none')  # none, low, medium, high
    
    # Motion Detection
    motion_enabled = Column(Boolean, default=True)
    motion_sensitivity = Column(Integer, default=5)  # 1-10
    motion_threshold = Column(Integer, default=50)  # 1-100
    noise_reduction = Column(String, default='medium')  # low, medium, high
    detect_shadows = Column(Boolean, default=True)
    detection_zones = Column(JSON, nullable=True)  # Grid mask
    post_motion_cooldown = Column(Integer, default=5)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### 4. Update API Schemas

**File:** `backend/api/schemas/camera.py`

```python
class CameraSettingsUpdate(BaseModel):
    """Schema for updating camera settings"""
    
    # Video Quality
    resolution_width: Optional[int] = Field(None, ge=320, le=3840)
    resolution_height: Optional[int] = Field(None, ge=240, le=2160)
    fps: Optional[int] = Field(None, ge=1, le=30)
    bitrate: Optional[int] = Field(None, ge=500, le=10000)  # kbps
    jpeg_quality: Optional[int] = Field(None, ge=1, le=100)
    
    # Image Adjustments
    brightness: Optional[int] = Field(None, ge=-100, le=100)
    contrast: Optional[float] = Field(None, ge=0.5, le=3.0)
    saturation: Optional[float] = Field(None, ge=0.0, le=2.0)
    sharpness: Optional[str] = Field(None, pattern="^(none|low|medium|high)$")
    
    # Motion Detection
    motion_enabled: Optional[bool] = None
    motion_sensitivity: Optional[int] = Field(None, ge=1, le=10)
    motion_threshold: Optional[int] = Field(None, ge=1, le=100)
    noise_reduction: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    detect_shadows: Optional[bool] = None
    detection_zones: Optional[dict] = None
    post_motion_cooldown: Optional[int] = Field(None, ge=1, le=300)
```

#### 5. Add API Endpoints

**File:** `backend/api/routes/cameras.py`

```python
@router.get("/cameras/{camera_id}/settings")
async def get_camera_settings(camera_id: str, db: Session = Depends(get_db)):
    """Get granular settings for a camera"""
    settings = db.query(models.CameraSettings).filter_by(camera_id=camera_id).first()
    if not settings:
        # Return defaults
        return CameraSettingsResponse(camera_id=camera_id)
    return settings

@router.patch("/cameras/{camera_id}/settings")
async def update_camera_settings(
    camera_id: str,
    settings: CameraSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update granular settings for a camera"""
    db_settings = db.query(models.CameraSettings).filter_by(camera_id=camera_id).first()
    
    if not db_settings:
        db_settings = models.CameraSettings(camera_id=camera_id)
        db.add(db_settings)
    
    # Update fields
    for field, value in settings.dict(exclude_unset=True).items():
        setattr(db_settings, field, value)
    
    db.commit()
    db.refresh(db_settings)
    
    # Apply settings to running camera
    camera_manager = get_camera_manager()
    camera_manager.apply_settings(camera_id, db_settings)
    
    return db_settings

@router.post("/cameras/{camera_id}/settings/preview")
async def preview_settings(
    camera_id: str,
    settings: CameraSettingsUpdate
):
    """Get a preview frame with settings applied (doesn't save)"""
    camera_manager = get_camera_manager()
    camera = camera_manager.get_camera(camera_id)
    
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Get frame with temporary settings applied
    frame = camera.get_preview_with_settings(settings.dict(exclude_unset=True))
    
    # Encode as JPEG
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    
    return Response(content=buffer.tobytes(), media_type="image/jpeg")
```

---

### Frontend Changes

#### 1. Create Camera Settings Component

**File:** `frontend/src/components/CameraSettingsPanel.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const CameraSettingsPanel = ({ cameraId, onClose }) => {
  const [settings, setSettings] = useState({
    // Video Quality
    resolution_width: 1920,
    resolution_height: 1080,
    fps: 15,
    bitrate: 2000,
    jpeg_quality: 90,
    
    // Image Adjustments
    brightness: 0,
    contrast: 1.0,
    saturation: 1.0,
    sharpness: 'none',
    
    // Motion Detection
    motion_enabled: true,
    motion_sensitivity: 5,
    motion_threshold: 50,
    noise_reduction: 'medium',
    detect_shadows: true,
    detection_zones: null,
    post_motion_cooldown: 5
  });
  
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    loadSettings();
  }, [cameraId]);
  
  const loadSettings = async () => {
    try {
      const response = await axios.get(`/api/cameras/${cameraId}/settings`);
      setSettings(response.data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };
  
  const handleChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };
  
  const previewChanges = async () => {
    setLoading(true);
    try {
      const response = await axios.post(
        `/api/cameras/${cameraId}/settings/preview`,
        settings,
        { responseType: 'blob' }
      );
      const url = URL.createObjectURL(response.data);
      setPreviewUrl(url);
    } catch (error) {
      console.error('Preview failed:', error);
    }
    setLoading(false);
  };
  
  const saveSettings = async () => {
    setLoading(true);
    try {
      await axios.patch(`/api/cameras/${cameraId}/settings`, settings);
      alert('Settings saved successfully!');
    } catch (error) {
      console.error('Save failed:', error);
      alert('Failed to save settings');
    }
    setLoading(false);
  };
  
  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <h2>Camera Settings: {cameraId}</h2>
        <button onClick={onClose} style={styles.closeBtn}>×</button>
      </div>
      
      {/* Video Quality Section */}
      <section style={styles.section}>
        <h3>📹 Video Quality</h3>
        
        <label style={styles.label}>
          Resolution
          <select
            value={`${settings.resolution_width}x${settings.resolution_height}`}
            onChange={(e) => {
              const [w, h] = e.target.value.split('x').map(Number);
              handleChange('resolution_width', w);
              handleChange('resolution_height', h);
            }}
            style={styles.select}
          >
            <option value="3840x2160">4K (3840×2160)</option>
            <option value="1920x1080">1080p (1920×1080)</option>
            <option value="1280x720">720p (1280×720)</option>
            <option value="640x480">480p (640×480)</option>
          </select>
        </label>
        
        <label style={styles.label}>
          Frame Rate: {settings.fps} FPS
          <input
            type="range"
            min="1"
            max="30"
            value={settings.fps}
            onChange={(e) => handleChange('fps', parseInt(e.target.value))}
            style={styles.slider}
          />
        </label>
        
        <label style={styles.label}>
          Bitrate: {settings.bitrate} kbps
          <input
            type="range"
            min="500"
            max="10000"
            step="100"
            value={settings.bitrate}
            onChange={(e) => handleChange('bitrate', parseInt(e.target.value))}
            style={styles.slider}
          />
        </label>
        
        <label style={styles.label}>
          JPEG Quality: {settings.jpeg_quality}%
          <input
            type="range"
            min="1"
            max="100"
            value={settings.jpeg_quality}
            onChange={(e) => handleChange('jpeg_quality', parseInt(e.target.value))}
            style={styles.slider}
          />
        </label>
      </section>
      
      {/* Image Adjustments Section */}
      <section style={styles.section}>
        <h3>🎨 Image Adjustments</h3>
        
        <label style={styles.label}>
          Brightness: {settings.brightness > 0 ? `+${settings.brightness}` : settings.brightness}
          <input
            type="range"
            min="-100"
            max="100"
            value={settings.brightness}
            onChange={(e) => handleChange('brightness', parseInt(e.target.value))}
            style={styles.slider}
          />
        </label>
        
        <label style={styles.label}>
          Contrast: {settings.contrast.toFixed(1)}
          <input
            type="range"
            min="0.5"
            max="3.0"
            step="0.1"
            value={settings.contrast}
            onChange={(e) => handleChange('contrast', parseFloat(e.target.value))}
            style={styles.slider}
          />
        </label>
        
        <label style={styles.label}>
          Saturation: {settings.saturation.toFixed(1)}
          <input
            type="range"
            min="0.0"
            max="2.0"
            step="0.1"
            value={settings.saturation}
            onChange={(e) => handleChange('saturation', parseFloat(e.target.value))}
            style={styles.slider}
          />
        </label>
        
        <label style={styles.label}>
          Sharpness
          <div style={styles.radioGroup}>
            {['none', 'low', 'medium', 'high'].map(level => (
              <label key={level} style={styles.radioLabel}>
                <input
                  type="radio"
                  name="sharpness"
                  value={level}
                  checked={settings.sharpness === level}
                  onChange={(e) => handleChange('sharpness', e.target.value)}
                />
                {level.charAt(0).toUpperCase() + level.slice(1)}
              </label>
            ))}
          </div>
        </label>
      </section>
      
      {/* Motion Detection Section */}
      <section style={styles.section}>
        <h3>🚶 Motion Detection</h3>
        
        <label style={styles.checkboxLabel}>
          <input
            type="checkbox"
            checked={settings.motion_enabled}
            onChange={(e) => handleChange('motion_enabled', e.target.checked)}
          />
          Enable Motion Detection
        </label>
        
        {settings.motion_enabled && (
          <>
            <label style={styles.label}>
              Sensitivity: {settings.motion_sensitivity} (
              {settings.motion_sensitivity <= 3 ? 'Low' :
               settings.motion_sensitivity <= 7 ? 'Medium' : 'High'})
              <input
                type="range"
                min="1"
                max="10"
                value={settings.motion_sensitivity}
                onChange={(e) => handleChange('motion_sensitivity', parseInt(e.target.value))}
                style={styles.slider}
              />
            </label>
            
            <label style={styles.label}>
              Threshold: {settings.motion_threshold}%
              <input
                type="range"
                min="1"
                max="100"
                value={settings.motion_threshold}
                onChange={(e) => handleChange('motion_threshold', parseInt(e.target.value))}
                style={styles.slider}
              />
            </label>
            
            <label style={styles.label}>
              Noise Reduction
              <div style={styles.radioGroup}>
                {['low', 'medium', 'high'].map(level => (
                  <label key={level} style={styles.radioLabel}>
                    <input
                      type="radio"
                      name="noise_reduction"
                      value={level}
                      checked={settings.noise_reduction === level}
                      onChange={(e) => handleChange('noise_reduction', e.target.value)}
                    />
                    {level.charAt(0).toUpperCase() + level.slice(1)}
                  </label>
                ))}
              </div>
            </label>
            
            <label style={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={settings.detect_shadows}
                onChange={(e) => handleChange('detect_shadows', e.target.checked)}
              />
              Detect Shadows
            </label>
            
            <label style={styles.label}>
              Post-Motion Record: {settings.post_motion_cooldown} seconds
              <input
                type="range"
                min="1"
                max="300"
                value={settings.post_motion_cooldown}
                onChange={(e) => handleChange('post_motion_cooldown', parseInt(e.target.value))}
                style={styles.slider}
              />
            </label>
          </>
        )}
      </section>
      
      {/* Preview */}
      {previewUrl && (
        <div style={styles.preview}>
          <h4>Preview</h4>
          <img src={previewUrl} alt="Settings preview" style={styles.previewImage} />
        </div>
      )}
      
      {/* Actions */}
      <div style={styles.actions}>
        <button onClick={previewChanges} disabled={loading} style={styles.btn}>
          {loading ? 'Loading...' : 'Preview Changes'}
        </button>
        <button onClick={saveSettings} disabled={loading} style={styles.btnPrimary}>
          Save Settings
        </button>
        <button onClick={() => loadSettings()} style={styles.btn}>
          Reset
        </button>
      </div>
    </div>
  );
};

const styles = {
  panel: {
    background: 'var(--theme-card-bg, white)',
    borderRadius: '8px',
    padding: '20px',
    maxWidth: '800px',
    margin: '20px auto',
    boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px'
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    fontSize: '32px',
    cursor: 'pointer'
  },
  section: {
    marginBottom: '30px',
    padding: '15px',
    background: 'var(--theme-bg, #f5f5f5)',
    borderRadius: '8px'
  },
  label: {
    display: 'block',
    marginBottom: '15px',
    fontWeight: '600'
  },
  slider: {
    width: '100%',
    marginTop: '8px'
  },
  select: {
    width: '100%',
    padding: '8px',
    marginTop: '8px',
    borderRadius: '4px',
    border: '1px solid #ccc'
  },
  radioGroup: {
    display: 'flex',
    gap: '15px',
    marginTop: '8px'
  },
  radioLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    fontWeight: 'normal'
  },
  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '15px',
    fontWeight: '600'
  },
  preview: {
    marginBottom: '20px'
  },
  previewImage: {
    width: '100%',
    borderRadius: '8px',
    marginTop: '10px'
  },
  actions: {
    display: 'flex',
    gap: '10px',
    justifyContent: 'flex-end'
  },
  btn: {
    padding: '10px 20px',
    borderRadius: '4px',
    border: '1px solid #ccc',
    background: 'white',
    cursor: 'pointer'
  },
  btnPrimary: {
    padding: '10px 20px',
    borderRadius: '4px',
    border: 'none',
    background: 'var(--theme-primary, #007bff)',
    color: 'white',
    cursor: 'pointer'
  }
};

export default CameraSettingsPanel;
```

---

## 📊 Comparison with Commercial Tools

### Features OpenEye Can Match

| Feature | Commercial Tools | OpenEye (Proposed) | Difficulty |
|---------|------------------|-------------------|------------|
| **Motion Sensitivity** | ✅ Slider 1-10 | ✅ Slider 1-10 | Easy |
| **Motion Zones** | ✅ Grid overlay | ✅ Grid overlay | Medium |
| **Resolution Control** | ✅ Multiple presets | ✅ 480p-4K | Easy |
| **Frame Rate** | ✅ 1-30 FPS | ✅ 1-30 FPS | Easy |
| **Brightness/Contrast** | ✅ Sliders | ✅ Sliders | Easy |
| **Noise Reduction** | ✅ Low/Med/High | ✅ Low/Med/High | Easy |
| **Shadow Detection** | ✅ Toggle | ✅ Toggle | Easy |
| **Recording Duration** | ✅ Configurable | ✅ 1-300 seconds | Easy |
| **Bitrate Control** | ⚠️ Sometimes | ✅ 500-10000 kbps | Medium |
| **Sharpness** | ⚠️ Sometimes | ✅ 4 levels | Easy |
| **Saturation** | ⚠️ Sometimes | ✅ Slider | Easy |
| **Real-time Preview** | ✅ Common | ✅ Available | Easy |

**Conclusion:** OpenEye can match or exceed commercial tools! 🎉

---

## ⏱️ Implementation Timeline

### Phase 1: Backend (Week 1-2)
- ✅ Day 1-2: Enhance MotionDetector class
- ✅ Day 3-4: Add image adjustment methods
- ✅ Day 5-6: Update database schema
- ✅ Day 7-8: Create API endpoints
- ✅ Day 9-10: Testing & validation

### Phase 2: Frontend (Week 3-4)
- ✅ Day 1-3: Create CameraSettingsPanel component
- ✅ Day 4-5: Add preview functionality
- ✅ Day 6-7: Integrate with CameraManagementPage
- ✅ Day 8-9: Mobile responsive design
- ✅ Day 10: Testing & polish

### Phase 3: Advanced Features (Week 5-6)
- ✅ Day 1-3: Motion detection zones (grid overlay)
- ✅ Day 4-5: Real-time settings preview
- ✅ Day 6-7: Per-camera profile presets
- ✅ Day 8-10: Documentation & testing

**Total: 6 weeks for full implementation**

---

## 🎯 Quick Win Features (Can Implement Immediately)

### Already in Backend (Just Need UI):
1. ✅ **min_contour_area** - Motion sensitivity (already exists!)
2. ✅ **post_motion_cooldown** - Recording duration (already exists!)
3. ✅ **face_detection_threshold** - Face recognition sensitivity (already exists!)

### Easy to Add (1-2 days each):
4. **Resolution control** - OpenCV `set(cv2.CAP_PROP_FRAME_WIDTH/HEIGHT)`
5. **JPEG quality** - Already used in snapshots, just expose in UI
6. **FPS control** - Frame skip logic
7. **Brightness/Contrast** - OpenCV `convertScaleAbs()`

### Medium Complexity (3-5 days each):
8. **Noise reduction levels** - Adjust Gaussian blur parameters
9. **Shadow detection toggle** - Already in MOG2, just expose
10. **Motion threshold** - Adjust varThreshold parameter

### Advanced (1-2 weeks each):
11. **Motion detection zones** - Grid mask overlay
12. **Real-time preview** - WebSocket + temporary settings
13. **Bitrate control** - FFmpeg encoding parameters

---

## 💡 Recommendations

### Start With (v3.4.0):
1. **Motion Sensitivity Slider** - High impact, easy implementation
2. **Brightness/Contrast Controls** - Very useful, easy implementation
3. **Resolution Dropdown** - Already partially implemented
4. **FPS Control** - Good for bandwidth management

### Add Next (v3.5.0):
5. **Noise Reduction Options**
6. **Motion Threshold**
7. **Shadow Detection Toggle**
8. **JPEG Quality Slider**

### Advanced Features (v3.6.0):
9. **Motion Detection Zones**
10. **Real-time Settings Preview**
11. **Bitrate Control**
12. **Profile Presets** (Indoor, Outdoor, Night, etc.)

---

## 📸 Waiting for Your Screenshot

**Please share the screenshot** so I can:
1. See the exact UI layout you prefer
2. Identify specific features you want to prioritize
3. Match the visual design style
4. Ensure we implement the most useful controls first

Once you share it, I can create a more targeted implementation plan! 🎯

---

**Summary:** YES, OpenEye can absolutely implement granular controls similar to commercial tools. The foundation is already there - we just need to expose the controls in the UI and add a few enhancement features. This would make OpenEye v3.4.0 a truly professional-grade surveillance system! 🚀
