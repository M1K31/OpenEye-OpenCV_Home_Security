# UI Improvements Implementation Guide (v3.6.2)

## Overview

This guide documents the UI improvements requested and implemented for the OpenEye surveillance system.

## Completed Work

### 1. ✅ Comprehensive Camera Settings Modal

**Files Created:**
- `/frontend/src/components/CameraSettingsModal.jsx` (400+ lines)
- `/frontend/src/components/CameraSettingsModal.css` (380+ lines)

**Features:**
- 3 tabbed interface: Motion Detection, Recording, Detection Zones
- All camera settings in one place
- Per-tab save buttons
- Integrates MotionZoneEditor component directly

**Benefits:**
- Consolidates settings from multiple pages
- No need to navigate between System Settings, Alert Settings, and Camera Management
- Zones are now easily accessible as a tab

### 2. ✅ Motion Detection Zones

**Status:** Already integrated in v3.6.2
**Location:** Camera Management page → "📍 Zones" button on each camera card

**Files:**
- `/frontend/src/components/MotionZoneEditor.jsx`
- `/frontend/src/components/MotionZoneEditor.css`
- Backend API: `/api/cameras/{camera_id}/zones`

**Features:**
- Interactive canvas-based zone drawing
- Inclusion/exclusion zones
- Per-zone sensitivity multipliers
- Real-time statistics

---

## Integration Steps

### Step 1: Update Camera Management Page

**File:** `/frontend/src/pages/CameraManagementPage.jsx`

#### Import the new modal:
```javascript
import CameraSettingsModal from '../components/CameraSettingsModal';
```

#### Replace state (around line 31):
```javascript
// REMOVE:
const [editingCamera, setEditingCamera] = useState(null);
const [editForm, setEditForm] = useState({...});
const [zoneEditorCamera, setZoneEditorCamera] = useState(null);

// REPLACE WITH:
const [settingsCamera, setSettingsCamera] = useState(null);
```

#### Remove old handler functions (around lines 113-136):
```javascript
// REMOVE handleEditCamera and handleSaveEdit functions
```

#### Update button click handler (around line 278):
```javascript
// CHANGE FROM:
onClick={() => handleEditCamera(camera)}

// CHANGE TO:
onClick={() => setSettingsCamera(camera)}
```

#### Remove the "📍 Zones" button (around lines 293-299):
```javascript
// REMOVE this button - zones are now in the settings modal
```

#### Replace both modals at the end (around lines 483-618):
```javascript
// REMOVE both:
// - Edit Camera Modal (lines 483-607)
// - Motion Zone Editor Modal (lines 610-618)

// REPLACE WITH:
{settingsCamera && (
  <CameraSettingsModal
    camera={settingsCamera}
    onClose={() => setSettingsCamera(null)}
    onSave={loadCameras}
  />
)}
```

#### Update button styles (in styles object):
```javascript
// RENAME:
editButton → settingsButton
// REMOVE:
zonesButton
```

---

### Step 2: Fix Timeline Date Picker

**File:** `/frontend/src/pages/TimelineView.jsx`

**Issue:** Date picker not allowing date selection

**Solution:**
1. Verify date input has proper `onChange` handler
2. Ensure date format is compatible (YYYY-MM-DD)
3. Check for any disabled state on the input

**Code to add:**
```javascript
const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);

<input
  type="date"
  value={selectedDate}
  onChange={(e) => {
    setSelectedDate(e.target.value);
    loadEventsForDate(e.target.value);
  }}
  max={new Date().toISOString().split('T')[0]}
  style={styles.dateInput}
/>
```

---

### Step 3: Add Per-Section Save Buttons to Alert Settings

**File:** `/frontend/src/pages/AlertSettingsPage.jsx`

**Current Issue:** Single save button at bottom requires scrolling

**Solution:** Add individual save buttons for each notification section

**Example implementation:**
```javascript
// Email Notifications Section
const handleSaveEmailSettings = async () => {
  try {
    await apiClient.put('/settings/alert', {
      email_enabled: emailSettings.enabled,
      email_recipients: emailSettings.recipients,
      email_smtp_settings: emailSettings.smtp
    });
    setSuccess('Email settings saved!');
  } catch (err) {
    setError(`Failed to save: ${err.message}`);
  }
};

<div className="settings-section">
  <h3>Email Notifications</h3>
  {/* Email settings fields */}
  <button onClick={handleSaveEmailSettings} className="section-save-btn">
    Save Email Settings
  </button>
</div>

// Repeat for SMS, Push, Webhook sections
```

**CSS to add:**
```css
.section-save-btn {
  margin-top: 16px;
  padding: 10px 24px;
  background: var(--primary-color);
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}

.section-save-btn:hover {
  background: var(--primary-hover);
}
```

---

## Troubleshooting

### Issue: 401/403 Errors for Thumbnails and Videos

**Likely Causes:**
1. Static file routes require authentication (they shouldn't)
2. URL paths are incorrect
3. Token is being sent but rejected

**Debugging Steps:**

1. Check browser network tab for exact failing URLs
2. Verify backend static file mounts in `main.py`:
```python
# These should NOT require authentication
app.mount("/recordings", StaticFiles(directory=str(paths.recordings_dir)), name="recordings")
app.mount("/data/thumbnails", StaticFiles(directory=str(paths.thumbnails_dir)), name="thumbnails")
app.mount("/api/snapshots", StaticFiles(directory=str(paths.snapshots_dir)), name="snapshots_api")
```

3. Check if middleware is intercepting static file requests:
```python
# In main.py, ensure static mounts are BEFORE middleware
# Static mounts should be at lines 167-206
# Middleware should be after line 300
```

4. **Quick Fix:** Add static paths to public endpoints in apiClient:
```javascript
// File: frontend/src/api/apiClient.js
const PUBLIC_ENDPOINTS = [
  '/token',
  '/setup/status',
  '/setup/initialize',
  '/recordings',     // ADD THIS
  '/data',           // ADD THIS
  '/snapshots',      // ADD THIS
];
```

5. **Alternative:** Remove Authorization header for static file requests:
```javascript
// In apiClient.js request interceptor
if (isPublicEndpoint(config.url) ||
    config.url.startsWith('/recordings') ||
    config.url.startsWith('/data') ||
    config.url.startsWith('/snapshots')) {
  return config;
}
```

### Issue: Zone Detection UI Not Visible

**Solution:** The UI is already there!

1. Go to **Camera Management** page
2. Find your camera in the list
3. Click the **"📍 Zones"** button
4. This opens the zone editor modal

**OR** (after integration):
1. Go to **Camera Management** page
2. Click **"⚙️ Settings"** on any camera
3. Click the **"Detection Zones"** tab
4. Draw zones interactively

### Issue: Zones Not Working

**Checklist:**
1. Verify zones are saved: `SELECT * FROM motion_zones WHERE camera_id='your_camera'`
2. Check zones are active: `is_active = 1`
3. Restart camera to load zones: Camera Management → Disable → Enable
4. Check backend logs for zone loading messages:
```
Loaded 2 polygon zones for camera front_door
```
5. Test with high motion in zone area
6. Verify motion threshold isn't too high

---

## Testing Checklist

### Camera Settings Modal
- [ ] Modal opens when clicking "⚙️ Settings"
- [ ] All 3 tabs switch correctly
- [ ] Motion settings save successfully
- [ ] Recording settings save successfully
- [ ] Zones tab shows zone editor
- [ ] Modal closes properly
- [ ] Settings reload after save

### Motion Zones
- [ ] Can draw polygon with 3+ points
- [ ] Zone appears on canvas with color
- [ ] Zone saves to database
- [ ] Zone statistics update on motion
- [ ] Exclusion zones filter motion
- [ ] Inclusion zones focus detection
- [ ] Sensitivity multipliers work

### Timeline Date Picker
- [ ] Can select past dates
- [ ] Events load for selected date
- [ ] Can navigate forward/backward
- [ ] Current date is default
- [ ] Future dates are disabled

### Alert Settings
- [ ] Each section has save button
- [ ] Save buttons work independently
- [ ] Success/error messages show
- [ ] Settings persist after save
- [ ] No need to scroll to save

---

## File Structure Summary

```
opencv_surveillance/
├── backend/
│   ├── core/
│   │   └── motion_detector.py          # ✅ Zone filtering logic
│   ├── database/
│   │   └── models.py                   # ✅ MotionZone model
│   └── api/routes/
│       └── motion_zones.py             # ✅ Zone CRUD API
├── frontend/src/
│   ├── components/
│   │   ├── CameraSettingsModal.jsx     # ✅ NEW - Comprehensive settings
│   │   ├── CameraSettingsModal.css     # ✅ NEW - Modal styling
│   │   ├── MotionZoneEditor.jsx        # ✅ Zone drawing UI
│   │   └── MotionZoneEditor.css        # ✅ Zone editor styling
│   ├── pages/
│   │   ├── CameraManagementPage.jsx    # ⚠️  NEEDS UPDATE
│   │   ├── TimelineView.jsx            # ⚠️  NEEDS FIX
│   │   └── AlertSettingsPage.jsx       # ⚠️  NEEDS ENHANCEMENT
│   └── services/
│       └── motionZonesService.js       # ✅ Zone API client
└── docs/
    ├── MOTION_ZONES_GUIDE.md           # ✅ User documentation
    └── UI_IMPROVEMENTS_GUIDE.md        # ✅ This file
```

---

## Quick Start

### To see zones immediately:
1. Navigate to **Camera Management**
2. Look for the **"📍 Zones"** button on each camera card
3. Click it to open the zone editor
4. Draw a zone and test motion detection

### After full integration:
1. Apply the changes in Step 1 above
2. Restart frontend: `npm run build` or `npm run dev`
3. Click "⚙️ Settings" → "Detection Zones" tab
4. All settings now in one place

---

## Support

For additional help:
- See `docs/MOTION_ZONES_GUIDE.md` for complete zone documentation
- Run test suite: `./venv/bin/python3 test_motion_zones.py`
- Check backend logs: `logs/backend.log`
- GitHub Issues: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues

---

**Version:** 3.6.2
**Last Updated:** October 26, 2025
**Author:** OpenEye Development Team
