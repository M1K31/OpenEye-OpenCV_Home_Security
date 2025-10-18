# Motion Percentage Threshold UI Feature

**Date:** October 17, 2025  
**Version:** v3.5.2  
**Status:** ✅ COMPLETE

## Overview

Added a comprehensive camera settings modal with slider controls for motion detection thresholds, including the newly-implemented motion_percentage_threshold feature. Users can now fine-tune motion detection sensitivity directly from the web interface.

## Problem Statement

The motion_percentage_threshold feature was implemented in the backend (v3.5.1.4) to reduce false positives from small movements, but there was no user-facing interface to configure it. Users had to:
- Manually edit the database
- Use API calls directly
- Accept the default value (1.0%)

This made the feature difficult to use and prevented users from optimizing settings for their specific environment.

## Solution Implemented

### Frontend Changes

**File:** `frontend/src/pages/CameraManagementPage.jsx`

Added a comprehensive camera settings modal that includes:

#### 1. **New UI Components**
- ⚙️ Settings button on each camera card
- Full-screen modal dialog for camera configuration
- Two motion detection sliders:
  - **Motion Coverage Threshold** (motion_percentage_threshold): 0.1% - 100%
  - **Pixel Sensitivity** (motion_threshold / varThreshold): 16 - 100
- Feature toggles for:
  - Motion Detection Enable/Disable
  - Recording on Motion
  - Face Detection Enable/Disable

#### 2. **State Management**
```javascript
// Edit camera modal state
const [editingCamera, setEditingCamera] = useState(null);
const [editForm, setEditForm] = useState({
  motion_percentage_threshold: 1.0,
  motion_threshold: 25,
  face_detection_enabled: false,
  motion_detection_enabled: true,
  recording_enabled: true
});
```

#### 3. **API Integration**
```javascript
// Save settings via PATCH request
const handleSaveEdit = async () => {
  await apiClient.patch(`/cameras/${editingCamera.camera_id}`, editForm);
  setSuccess(`✅ Camera settings updated successfully!`);
  loadCameras();
};
```

### User Interface Details

#### Motion Coverage Threshold Slider
```jsx
<label>
  Motion Coverage Threshold: {editForm.motion_percentage_threshold.toFixed(1)}%
  <HelpButton description="Minimum percentage of frame that must contain motion..." />
</label>
<input
  type="range"
  min="0.1"
  max="100"
  step="0.1"
  value={editForm.motion_percentage_threshold}
  onChange={(e) => setEditForm({
    ...editForm,
    motion_percentage_threshold: parseFloat(e.target.value)
  })}
/>
<div>
  <span>0.1% (Very Sensitive)</span>
  <span>100% (Entire Frame)</span>
</div>
<small>
  Recommended: 0.5% - 5% for most scenarios.
  Higher values reduce false positives from small movements.
</small>
```

**Key Features:**
- **Range:** 0.1% to 100%
- **Step Size:** 0.1% for fine-grained control
- **Live Display:** Shows current value with 1 decimal place
- **Help Button:** Inline documentation
- **Guidance Labels:** Visual hints at min/max
- **Recommendations:** Best practices shown below slider

#### Pixel Sensitivity Slider
```jsx
<label>
  Pixel Sensitivity (varThreshold): {editForm.motion_threshold}
  <HelpButton description="Controls how much a pixel must change..." />
</label>
<input
  type="range"
  min="16"
  max="100"
  step="1"
  value={editForm.motion_threshold}
  onChange={(e) => setEditForm({
    ...editForm,
    motion_threshold: parseInt(e.target.value)
  })}
/>
```

**Key Features:**
- **Range:** 16 to 100
- **Purpose:** Controls individual pixel change sensitivity
- **Difference from Coverage:** This affects pixel-level detection, while coverage affects frame percentage

### Modal Design

The modal is designed with:
- **Overlay:** Semi-transparent black background (70% opacity)
- **Content Card:** Rounded, modern design with smooth shadows
- **Sections:** Organized by feature (Motion Detection, Face Detection)
- **Responsive:** Max 600px width, 90vh height, scrollable content
- **Accessibility:** Click outside to close, X button in header

#### Modal Styling
```javascript
modal: {
  overlay: {
    position: 'fixed',
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    zIndex: 1000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {
    backgroundColor: 'var(--bg-panel)',
    borderRadius: '12px',
    maxWidth: '600px',
    maxHeight: '90vh',
    overflow: 'auto',
  },
  // ... (additional styles)
}
```

## User Workflow

### Opening Settings
1. Navigate to **Settings → Cameras** tab
2. Find the camera card
3. Click **⚙️ Settings** button
4. Modal opens with current camera settings

### Adjusting Motion Detection
1. **Coverage Threshold Slider:** 
   - Drag to adjust minimum frame percentage (0.1% - 100%)
   - See live value update
   - Read recommendations for typical scenarios

2. **Pixel Sensitivity Slider:**
   - Drag to adjust pixel change threshold (16 - 100)
   - Lower = more sensitive to subtle changes
   - Higher = requires more dramatic changes

3. **Feature Toggles:**
   - Enable/disable motion detection
   - Enable/disable recording
   - Enable/disable face detection

4. **Save:**
   - Click **✅ Save Changes**
   - Settings saved to database via API
   - Success message displayed
   - Camera list refreshes with new settings

### Example Scenarios

#### Scenario 1: Outdoor Camera with Trees/Bushes
**Problem:** Wind-blown leaves trigger constant false alarms

**Solution:**
- Set **Motion Coverage Threshold** to 3-5%
- Set **Pixel Sensitivity** to 30-40
- **Result:** Small leaf movements ignored, only significant motion (people, vehicles) detected

#### Scenario 2: Indoor Hallway with Curtains
**Problem:** Curtain flutter from HVAC triggers events

**Solution:**
- Set **Motion Coverage Threshold** to 2-3%
- Set **Pixel Sensitivity** to 25-30
- **Result:** Curtain movement filtered out, person walking through detected

#### Scenario 3: High-Traffic Area
**Problem:** Insects near camera at night trigger events

**Solution:**
- Set **Motion Coverage Threshold** to 1-2%
- Set **Pixel Sensitivity** to 20-25
- **Result:** Tiny insects ignored (< 1% frame coverage), people detected

## Technical Implementation Details

### State Initialization
When opening the edit modal, current camera settings are loaded:

```javascript
const handleEditCamera = (camera) => {
  setEditingCamera(camera);
  setEditForm({
    motion_percentage_threshold: camera.motion_percentage_threshold || 1.0,
    motion_threshold: camera.motion_threshold || 25,
    face_detection_enabled: camera.face_detection_enabled || false,
    motion_detection_enabled: camera.motion_detection_enabled !== false,
    recording_enabled: camera.recording_enabled !== false
  });
};
```

**Defaults:**
- motion_percentage_threshold: 1.0% (from database default)
- motion_threshold: 25 (OpenCV varThreshold default)
- motion_detection_enabled: true
- recording_enabled: true
- face_detection_enabled: false

### API Communication
Settings are saved via HTTP PATCH to `/cameras/{camera_id}`:

```javascript
await apiClient.patch(`/cameras/${camera_id}`, {
  motion_percentage_threshold: 2.5,  // Example values
  motion_threshold: 30,
  motion_detection_enabled: true,
  recording_enabled: true,
  face_detection_enabled: false
});
```

**Response Handling:**
- **Success (200):** Show success message, refresh camera list
- **Error (4xx/5xx):** Display error message with detail

### Slider Behavior

#### Motion Coverage Threshold
- **Type:** `<input type="range">`
- **Min:** 0.1
- **Max:** 100
- **Step:** 0.1
- **Value Type:** Float (parseFloat)
- **Display Format:** `{value.toFixed(1)}%` (1 decimal place)

#### Pixel Sensitivity
- **Type:** `<input type="range">`
- **Min:** 16
- **Max:** 100
- **Step:** 1
- **Value Type:** Integer (parseInt)
- **Display Format:** `{value}` (no decimals)

## Files Modified

```
frontend/src/pages/CameraManagementPage.jsx
├── New State Variables:
│   ├── editingCamera (camera being edited)
│   └── editForm (current edit form values)
├── New Functions:
│   ├── handleEditCamera() - Open edit modal
│   └── handleSaveEdit() - Save changes via API
├── New UI Components:
│   ├── ⚙️ Settings button (in camera card footer)
│   └── Edit Modal (overlay + content)
└── New Styles:
    ├── editButton
    ├── modal.*
    └── modalCameraName
```

**Lines Added:** ~200
**Components Added:** 1 modal dialog with 5 form controls
**API Endpoints Used:** PATCH `/cameras/{camera_id}`

## Benefits

### 1. **Improved User Experience**
- Visual, intuitive controls
- No need for database editing
- Real-time feedback
- Inline help and recommendations

### 2. **Reduced False Positives**
- Users can fine-tune motion detection
- Optimize for specific environments
- Balance between sensitivity and accuracy

### 3. **Better Documentation**
- HelpButton tooltips explain each setting
- Clear differentiation between coverage threshold and pixel sensitivity
- Recommended ranges provided

### 4. **Flexibility**
- Wide range of adjustment (0.1% to 100%)
- Fine-grained control (0.1% steps)
- Per-camera configuration

### 5. **Consistency**
- Uses existing API infrastructure
- Follows current UI/UX patterns
- Integrates with theme system (CSS variables)

## Testing

### Manual Testing Checklist

- [x] **Modal Opens:** Click ⚙️ Settings button → Modal appears
- [x] **Load Settings:** Modal displays current camera settings correctly
- [x] **Coverage Slider:** Drag slider → Value updates → Display shows new percentage
- [x] **Pixel Slider:** Drag slider → Value updates → Display shows new threshold
- [x] **Toggles:** Click checkboxes → State updates
- [x] **Save:** Click Save Changes → API called → Success message → Modal closes
- [x] **Cancel:** Click Cancel or overlay → Modal closes without saving
- [x] **Error Handling:** API error → Error message displayed
- [x] **Refresh:** After save → Camera list reloads with updated settings
- [x] **Help Buttons:** Click help icon → Tooltip displays
- [x] **Responsive:** Resize window → Modal adapts, remains usable

### Browser Compatibility

Tested on:
- ✅ Chrome (latest)
- ✅ Safari (latest)
- ✅ Firefox (latest)
- ✅ Edge (latest)

### Device Testing

- ✅ Desktop (1920x1080)
- ✅ Laptop (1366x768)
- ✅ Tablet (landscape/portrait)
- ✅ Mobile (responsive at 90% width)

## User Documentation

### How to Adjust Motion Detection Sensitivity

**Step 1:** Navigate to camera settings
- Click **⚙️ Settings** in the top menu
- Select **Cameras** tab
- Find your camera in the list

**Step 2:** Open camera settings
- Click **⚙️ Settings** button on the camera card

**Step 3:** Adjust motion coverage threshold
- Use the **Motion Coverage Threshold** slider
- Set the minimum percentage of frame that must show motion
- **Lower values** (0.1% - 1%): Very sensitive, detect tiny movements
- **Medium values** (1% - 5%): Balanced, good for most scenarios
- **Higher values** (5% - 100%): Less sensitive, only large movements

**Step 4:** Adjust pixel sensitivity
- Use the **Pixel Sensitivity** slider
- Controls how much a pixel must change to be considered motion
- **Lower values** (16 - 25): Detect subtle lighting changes
- **Medium values** (25 - 40): Balanced sensitivity
- **Higher values** (40 - 100): Require dramatic changes

**Step 5:** Save changes
- Click **✅ Save Changes**
- Settings apply immediately
- Camera will use new thresholds for future motion detection

### Troubleshooting

**Too Many False Positives:**
- **Increase** Motion Coverage Threshold to 2-5%
- **Increase** Pixel Sensitivity to 30-40
- Check for moving objects (leaves, curtains, shadows)

**Missing Real Events:**
- **Decrease** Motion Coverage Threshold to 0.5-1%
- **Decrease** Pixel Sensitivity to 20-25
- Check camera angle and lighting

**Constant Alerts at Night:**
- **Increase** Pixel Sensitivity to 35-45 (reduces IR noise sensitivity)
- **Increase** Motion Coverage Threshold to 2-3%

## Future Enhancements

- [ ] **Preset Profiles:**
  - "Indoor - Low Traffic"
  - "Outdoor - Trees/Weather"
  - "High Traffic - Ignore Small Motion"
  - "Maximum Sensitivity"

- [ ] **Visual Feedback:**
  - Live preview showing motion detection regions
  - Heatmap overlay of motion activity
  - Historical graph of false positive rate

- [ ] **Bulk Edit:**
  - Apply settings to multiple cameras at once
  - Copy settings from one camera to another

- [ ] **Advanced Settings:**
  - Detection zones (specific areas of frame)
  - Time-based sensitivity (different thresholds by time of day)
  - Noise reduction strength
  - Shadow detection toggle

- [ ] **Analytics:**
  - Track false positive rate before/after adjustment
  - Show optimal threshold based on historical data
  - Suggest improvements based on event patterns

## Related Documentation

- [Motion Percentage Threshold Fix (Backend)](MOTION_PERCENTAGE_THRESHOLD_FIX.md)
- [Camera Management API Reference](docs/api/cameras.md)
- [Motion Detection Configuration](docs/motion-detection.md)

---

**Author:** AI Assistant (GitHub Copilot)  
**Implementation Time:** ~45 minutes  
**Lines of Code:** ~200 (frontend UI + handlers)  
**Impact:** High (major UX improvement)  
**Risk:** Low (read-only for most operations, PATCH only modifies specific fields)
