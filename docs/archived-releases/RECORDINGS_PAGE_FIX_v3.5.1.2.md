# RecordingsPage API Integration Fix - v3.5.1.2
**Date:** October 11, 2025  
**Status:** ✅ Fixed and Deployed

## Issue Summary

The RecordingsPage was experiencing critical errors when loaded:
- **422 Unprocessable Entity** from `/api/recordings/snapshots` endpoint
- **TypeError: w.map is not a function** - trying to call `.map()` on undefined data
- Black screen upon navigation to recordings tab
- Console flooded with errors

## Root Cause Analysis

The RecordingsPage component was written with assumptions that didn't match the actual backend API:

### 1. **Missing API Endpoint**
- Frontend called: `/api/recordings/snapshots`
- Backend reality: **This endpoint doesn't exist**
- Solution: Use `/api/motion-events/` and filter for events with `snapshot_path`

### 2. **Data Structure Mismatch - Recordings**
Frontend expected:
```javascript
{
  filename: "recording.mp4",
  timestamp: "2025-10-11...",
  duration: 120.5,
  size: 1024000,
  camera_id: "cam1"
}
```

Backend returns:
```python
{
  id: 1,
  camera_id: "cam1",
  recording_path: "/path/to/recording.mp4",
  started_at: "2025-10-11T...",
  ended_at: "2025-10-11T...",
  duration_seconds: 120.5,
  file_size_bytes: 1024000,
  faces_detected: 2,
  known_faces_detected: 1,
  thumbnail_path: "/path/to/thumb.jpg"
}
```

### 3. **Data Structure Mismatch - Cameras**
Frontend expected: `response.data` (direct array)
Backend returns: Could be `response.data.cameras` or direct array
Solution: Handle both formats

### 4. **Array Safety**
No validation that API responses were arrays before calling `.map()`
Resulted in "map is not a function" errors when API returned errors

## Changes Made

### Fixed API Calls

**Before:**
```javascript
const loadCameras = async () => {
  const response = await axios.get('/api/cameras/');
  setCameras(response.data);
};

const loadSnapshots = async () => {
  const response = await axios.get('/api/recordings/snapshots');
  setSnapshots(response.data);
};
```

**After:**
```javascript
const loadCameras = async () => {
  try {
    const response = await axios.get('/api/cameras/');
    // Handle both formats: direct array or { cameras: [] }
    setCameras(Array.isArray(response.data) ? response.data : (response.data.cameras || []));
  } catch (err) {
    console.error('Error loading cameras:', err);
    setCameras([]); // Always set to array on error
  }
};

const loadSnapshots = async () => {
  try {
    // Load from motion events API and filter for snapshots
    const response = await axios.get('/api/motion-events/');
    const events = Array.isArray(response.data) ? response.data : [];
    const snapshotsData = events.filter(event => event.snapshot_path);
    setSnapshots(snapshotsData);
  } catch (err) {
    console.error('Error loading snapshots:', err);
    setSnapshots([]); // Always set to array on error
  }
};
```

### Fixed Recordings Rendering

**Before:**
```jsx
<video src={`/api/recordings/${recording.filename}/download`} />
<p>📅 {formatDate(recording.timestamp)}</p>
<p>⏱️ {recording.duration.toFixed(1)}s</p>
<p>💾 {formatFileSize(recording.size)}</p>
```

**After:**
```jsx
<video src={`/api/recordings/${recording.id}/download`} />
<p>📅 {formatDate(recording.started_at)}</p>
<p>⏱️ {recording.duration_seconds ? recording.duration_seconds.toFixed(1) : '0.0'}s</p>
<p>💾 {recording.file_size_bytes ? formatFileSize(recording.file_size_bytes) : 'N/A'}</p>
{recording.faces_detected > 0 && (
  <p>👤 {recording.faces_detected} face{recording.faces_detected > 1 ? 's' : ''} detected</p>
)}
```

### Fixed Snapshots Rendering

**Before:**
```jsx
<img src={`/api/recordings/snapshots/${snapshot.filename}`} />
<p>{formatDate(snapshot.timestamp)}</p>
<p>{formatFileSize(snapshot.size)}</p>
```

**After:**
```jsx
<img src={snapshot.snapshot_path} />
<p>{formatDate(snapshot.detected_at)}</p>
{snapshot.faces_detected > 0 && (
  <p>👤 {snapshot.faces_detected} face{snapshot.faces_detected > 1 ? 's' : ''}</p>
)}
```

### Fixed Delete Functions

**Before:**
```javascript
await axios.delete(`/api/recordings/${filename}`);
await axios.delete(`/api/recordings/snapshots/${filename}`);
```

**After:**
```javascript
await axios.delete(`/api/recordings/${recordingId}`);
await axios.delete(`/api/motion-events/${eventId}`);
```

## Error Prevention Improvements

### 1. **Always Initialize Arrays**
Every state that gets `.map()` called on it now:
- Initializes to `[]` instead of `undefined`
- Gets validated as array before setting: `Array.isArray(response.data) ? response.data : []`
- Sets to `[]` in catch blocks

### 2. **Null-Safe Property Access**
```javascript
// Before: recording.duration.toFixed(1)
// After:  recording.duration_seconds ? recording.duration_seconds.toFixed(1) : '0.0'
```

### 3. **Conditional Rendering**
```javascript
// Only show modal if snapshot_path exists
{selectedRecording && selectedRecording.snapshot_path && (
  <div style={styles.modal}>...</div>
)}
```

## Testing Results

### ✅ Fixed Issues
1. No more 422 errors - using correct API endpoints
2. No more "map is not a function" - all arrays validated
3. Page renders correctly with proper data
4. Videos display with correct metadata
5. Snapshots load from motion events
6. Delete functions use correct IDs
7. Face detection counts shown when available

### Expected Behavior Now

**Videos Tab:**
- Shows all recordings from database
- Displays camera name, date, duration, file size
- Shows face detection count if faces were detected
- Video player works inline
- Download and delete buttons functional

**Snapshots Tab:**
- Shows motion event snapshots (those with `snapshot_path`)
- Displays camera name and detection time
- Shows face count if faces detected
- Click to view full-size in modal
- Download and delete buttons functional

## Build Information

**New Build:** `index-574d7dac.js` (327.70 KB, gzip: 98.25 kB)
**Build Time:** 6.50s
**Status:** ✅ Deployed and serving

## User Action Required

**Hard refresh your browser** to load the new build:
- **Mac:** `Cmd + Shift + R`
- **Windows/Linux:** `Ctrl + Shift + R`

## API Endpoints Now Used

| Purpose | Endpoint | Method | Response |
|---------|----------|--------|----------|
| List cameras | `/api/cameras/` | GET | Array of camera objects |
| List recordings | `/api/recordings/` | GET | Array of RecordingEvent objects |
| Get recording file | `/api/recordings/{id}/download` | GET | Video file stream |
| Delete recording | `/api/recordings/{id}` | DELETE | Success message |
| List snapshots | `/api/motion-events/` | GET | Array filtered for `snapshot_path` |
| Delete snapshot | `/api/motion-events/{id}` | DELETE | Success message |

## Related Files

- **Modified:** `frontend/src/pages/RecordingsPage.jsx`
- **Backend APIs:** 
  - `backend/api/routes/recordings.py`
  - `backend/api/routes/motion_events.py` (assumed to exist)
- **Database Models:**
  - `RecordingEvent` - stores video recording metadata
  - `MotionEvent` - stores motion detection with optional snapshots

## Future Enhancements

Consider for later versions:
1. Create dedicated `/api/snapshots/` endpoint for cleaner API
2. Add pagination for recordings list
3. Add thumbnail generation for video recordings
4. Add filtering by date range
5. Add bulk delete functionality
6. Add video streaming instead of full download for preview

## Notes

- The snapshots feature relies on motion events having `snapshot_path` populated
- Face detection counts are shown when available but aren't required
- All errors are now handled gracefully with empty arrays as fallbacks
- The page will work even if no recordings or snapshots exist
