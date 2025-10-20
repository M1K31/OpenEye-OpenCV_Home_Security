# Snapshot and Recording Fixes v3.5.6
**Date**: 2025-10-19
**Version**: v3.5.6
**Status**: ✅ FIXED

## Issues Identified

### Issue 1: Snapshot Path 404 Errors
**Error**:
```
GET http://localhost:8000/api/snapshots/data/snapshots/motion_usb_camera_0_20251019_113340_835721.jpg 404 (Not Found)
```

**Impact**:
- Snapshots not displaying in Live Dashboard modal
- User sees "Snapshot not available" message
- Console cluttered with 404 errors

**Root Cause**:
Database stores full path `data/snapshots/filename.jpg`, but API was returning this path as-is. Frontend then built URL as `/api/snapshots/data/snapshots/filename.jpg` (double prefix).

---

### Issue 2: Recording Download Undefined ID
**Error**:
```
GET http://localhost:8000/api/recordings/undefined/download 422 (Unprocessable Entity)
```

**Impact**:
- Recording download buttons not working
- Repeated 422 errors in console
- Poor user experience when trying to download recordings

**Root Cause**:
Motion events from `/api/motion-events/` endpoint include `recording_id` field, but frontend was not mapping this field into the event objects used for rendering.

---

## Solutions Implemented

### Fix 1: Normalize Snapshot Paths in API Response

**File**: `backend/api/schemas/motion.py`

**Implementation**:
Added Pydantic field validator to automatically strip directory prefix from snapshot paths in API responses.

```python
from pydantic import BaseModel, Field, field_validator
from pathlib import Path

class MotionEventResponse(MotionEventBase):
    """Schema for motion event response"""
    id: int
    detected_at: datetime
    recording_id: Optional[int] = None
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None
    face_detection_ids: Optional[str] = None

    @field_validator('snapshot_path', mode='before')
    @classmethod
    def normalize_snapshot_path(cls, v):
        """Strip directory prefix from snapshot path for API response"""
        if v is None:
            return None
        # Remove 'data/snapshots/' prefix if present
        path_str = str(v)
        if path_str.startswith('data/snapshots/'):
            return path_str.replace('data/snapshots/', '', 1)
        # Also handle absolute paths
        return Path(path_str).name

    class Config:
        from_attributes = True
```

**How It Works**:
1. Database stores: `data/snapshots/motion_usb_camera_0_20251019_114158_198849.jpg`
2. Validator strips prefix
3. API returns: `motion_usb_camera_0_20251019_114158_198849.jpg`
4. Frontend builds URL: `/api/snapshots/motion_usb_camera_0_20251019_114158_198849.jpg` ✅

**Verification**:
```bash
curl "http://localhost:8000/api/motion-events/?skip=0&limit=1" | python3 -m json.tool
```

**Result**:
```json
{
  "events": [
    {
      "id": 248,
      "camera_id": "usb_camera_0",
      "detected_at": "2025-10-19T15:41:58.198849",
      "snapshot_path": "motion_usb_camera_0_20251019_114158_198849.jpg",
      "recording_id": 94,
      ...
    }
  ]
}
```

✅ **Path now clean** - no directory prefix

---

### Fix 2: Map Recording ID from API Response

**File**: `frontend/src/sections/LiveDashboard.jsx`

**Before** (Lines 82-96):
```javascript
// Motion snapshots (may or may not have recording)
...motionEvents.map(m => ({
  id: m.id,
  snapshot_id: m.id,
  snapshot_path: m.snapshot_path,
  // recording_id was missing!
  type: 'motion',
  camera_id: m.camera_id,
  timestamp: m.detected_at,
  duration_seconds: 0,
  faces_detected: m.faces_detected || 0,
  known_faces_detected: 0,
  hasRecording: false,  // Always false!
  hasSnapshot: true,
})),
```

**After** (Lines 82-96):
```javascript
// Motion snapshots (may or may not have recording)
...motionEvents.map(m => ({
  id: m.id,
  snapshot_id: m.id,
  snapshot_path: m.snapshot_path,
  recording_id: m.recording_id,  // ✅ Added - May be null
  type: 'motion',
  camera_id: m.camera_id,
  timestamp: m.detected_at,
  duration_seconds: 0,
  faces_detected: m.faces_detected || 0,
  known_faces_detected: 0,
  hasRecording: !!m.recording_id,  // ✅ Changed - Conditional based on recording_id
  hasSnapshot: true,
})),
```

**Changes Made**:
1. Added `recording_id: m.recording_id` to preserve the field from API
2. Changed `hasRecording: false` to `hasRecording: !!m.recording_id` (conditional)

**Result**:
- Events with recordings now include the recording_id
- Download buttons work correctly
- No more 422 errors

---

## API Response Format

### Motion Events Endpoint Response Structure

**Endpoint**: `GET /api/motion-events/?skip=0&limit=15`

**Response Format**:
```json
{
  "events": [
    {
      "id": 248,
      "camera_id": "usb_camera_0",
      "detected_at": "2025-10-19T15:41:58.198849",
      "snapshot_path": "motion_usb_camera_0_20251019_114158_198849.jpg",
      "recording_path": "recordings/motion_20251019_114152.mp4",
      "recording_id": 94,
      "faces_detected": 0,
      "motion_area": 0,
      "motion_percentage": 0.0,
      "contour_count": 0,
      "frame_width": null,
      "frame_height": null,
      "face_detection_ids": null,
      "triggered_zones": null
    }
  ],
  "total": 248,
  "limit": 15,
  "offset": 0,
  "has_more": true
}
```

**Key Fields**:
- `snapshot_path`: Now normalized (just filename) ✅
- `recording_id`: Links to recordings table (may be null)
- `recording_path`: Full path to video file (may be null)

---

## Frontend Integration

### LiveDashboard Event Click Handler

**File**: `frontend/src/sections/LiveDashboard.jsx:126-135`

```javascript
const handleEventClick = (event) => {
  if (event.recording_id) {
    // Has video recording - navigate to events page (recordings)
    window.location.href = `/events#${event.recording_id}`;
  } else if (event.snapshot_path || event.hasSnapshot) {
    // Has snapshot only - show in modal
    setSelectedSnapshot(event);
    setShowSnapshotModal(true);
  }
};
```

**Behavior**:
1. **Event with recording**: Navigates to `/events` page with hash navigation to specific recording
2. **Event with snapshot only**: Opens modal with snapshot viewer

### Snapshot Modal

**File**: `frontend/src/sections/LiveDashboard.jsx:286-333`

**Snapshot URL Construction**:
```javascript
<img
  src={`/api/snapshots/${selectedSnapshot.snapshot_path}`}
  alt="Event snapshot"
  className="snapshot-modal-image"
  onError={(e) => {
    e.target.src = 'data:image/svg+xml,<svg>...</svg>';
  }}
/>
```

**Now Correctly Builds**:
- Before: `/api/snapshots/data/snapshots/filename.jpg` ❌
- After: `/api/snapshots/filename.jpg` ✅

---

## Testing Results

### Test 1: Snapshot Display
**Before**: 404 errors, "Snapshot not available" ❌
**After**: Snapshots load and display correctly ✅

**Test Steps**:
1. Start application
2. Trigger motion detection (or use existing events)
3. Click on motion event in Live Dashboard timeline
4. Verify snapshot displays in modal

### Test 2: Recording Download
**Before**: 422 errors, download button not working ❌
**After**: Downloads work correctly ✅

**Test Steps**:
1. Navigate to `/events` page
2. Find recording with motion events
3. Click download button
4. Verify video file downloads

### Test 3: Console Errors
**Before**: Repeated 404 and 422 errors ❌
**After**: Clean console, no errors ✅

### Test 4: Event Navigation
**Before**: Navigation to `/events` page with undefined hash ❌
**After**: Navigation works with correct recording ID ✅

---

## Build Process

### Frontend Rebuild

```bash
cd frontend
npm run build
```

**Output**:
```
vite v5.4.11 building for production...
✓ 1774 modules transformed.
dist/index.html                   0.48 kB │ gzip:  0.32 kB
dist/assets/index-fce4a363.js   405.14 kB │ gzip: 96.84 kB
✓ built in 17.42s
```

**New Build Hash**: `index-fce4a363.js` (405.14 kB)

---

## Related Fixes

### Previous API Fix (Same Session)
**Issue**: Motion events API endpoint was wrong
**Fix**: Changed `/history/motion` to `/motion-events/`
**Documentation**: See `LIVE_DASHBOARD_API_FIXES_v3.5.6.md`

### Navigation Fix (Earlier Session)
**Issue**: Wrong route `/recordings` instead of `/events`
**Fix**: Updated navigation to use correct route
**Documentation**: See `LIVE_DASHBOARD_API_FIXES_v3.5.6.md`

---

## Files Modified

### Backend:
1. **`backend/api/schemas/motion.py`**
   - Added imports: `field_validator`, `Path`
   - Added `normalize_snapshot_path()` validator to `MotionEventResponse`
   - Lines modified: 8, 12, 40-51

### Frontend:
1. **`frontend/src/sections/LiveDashboard.jsx`**
   - Line 87: Added `recording_id: m.recording_id`
   - Line 94: Changed `hasRecording: !!m.recording_id`
   - Build: New hash `index-fce4a363.js`

---

## Technical Details

### Pydantic Field Validators

**Why Used**:
- Clean separation of storage format vs API format
- Automatic normalization at serialization time
- No need to modify database or CRUD operations
- Works with existing data

**Validator Mode**:
- `mode='before'`: Runs before Pydantic's type validation
- Allows raw value transformation before type checking

**Alternative Considered**:
Could have modified CRUD operations to store only filename, but:
- ❌ Requires database migration
- ❌ Breaks existing data
- ❌ More complex (affect recording_path too)
✅ Validator approach is cleaner and backward compatible

### Frontend Mapping

**Why Changed**:
- API provides `recording_id`, but frontend wasn't using it
- Event objects need `recording_id` for download buttons
- `hasRecording` should reflect actual data, not hardcoded false

**Data Flow**:
1. Backend API returns motion event with `recording_id: 94`
2. Frontend maps: `recording_id: m.recording_id` → `recording_id: 94`
3. Component uses: `hasRecording: !!94` → `true`
4. Download button enabled with correct ID

---

## Prevention Strategies

### For Future Development:

1. **API Response Validation**
   - Always verify API response format matches frontend expectations
   - Use TypeScript or PropTypes for type checking

2. **Path Consistency**
   - Decide on path format early (relative vs absolute, with/without prefix)
   - Document path format in API specification
   - Use validators for normalization

3. **Field Mapping**
   - When consuming API responses, map ALL relevant fields
   - Don't assume fields don't exist - check API response first
   - Use browser DevTools Network tab to inspect actual responses

4. **Console Monitoring**
   - Check browser console during development
   - 404 errors indicate path issues
   - 422 errors indicate validation failures (often missing fields)

---

## Recommended Testing

### Manual Testing Checklist:

- [x] Motion events display in Live Dashboard timeline
- [x] Clicking motion event opens modal (if snapshot only)
- [x] Snapshot displays correctly in modal
- [x] Clicking motion event navigates to recordings (if has recording)
- [x] Download button works on recordings page
- [x] No 404 errors in console
- [x] No 422 errors in console

### Automated Testing (Future):

```python
# Backend test for path normalization
def test_motion_event_response_snapshot_path_normalization():
    event = MotionEvent(
        id=1,
        camera_id="test",
        detected_at=datetime.now(),
        snapshot_path="data/snapshots/test.jpg",
        recording_id=1
    )
    response = MotionEventResponse.from_orm(event)
    assert response.snapshot_path == "test.jpg"
```

```javascript
// Frontend test for event mapping
test('motion events include recording_id', () => {
  const apiResponse = {
    events: [{
      id: 1,
      recording_id: 94,
      snapshot_path: "test.jpg"
    }]
  };
  const mappedEvents = mapMotionEvents(apiResponse.events);
  expect(mappedEvents[0].recording_id).toBe(94);
  expect(mappedEvents[0].hasRecording).toBe(true);
});
```

---

## Conclusion

Both snapshot and recording issues have been resolved:

✅ **Snapshot paths**: Normalized using Pydantic validator (strips directory prefix)
✅ **Recording IDs**: Properly mapped from API response to frontend events
✅ **Console errors**: Eliminated (no more 404s or 422s)
✅ **User workflow**: Fully functional (view snapshots, download recordings)
✅ **Backward compatible**: Works with existing database data

**Impact**:
- Clean console for better debugging
- Functional snapshot viewer modal
- Working recording downloads
- Improved user experience
- No database migration required

**Performance**: No impact (validator runs only during serialization)

**Next Steps**: Consider enhanced shadow mitigation for motion detection (user's next request).
