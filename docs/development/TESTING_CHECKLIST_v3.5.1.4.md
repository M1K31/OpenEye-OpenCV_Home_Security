# Comprehensive Testing Checklist - v3.5.1.4

**Date:** October 11, 2025  
**Version:** 3.5.1.4

## Testing Status Summary

### ✅ Completed Tests
- [x] Path validation endpoint working
- [x] Settings save functionality
- [x] Frontend builds successfully
- [x] Backend starts without errors
- [x] WebSocket connections working
- [x] Camera streaming functional
- [x] Recording started successfully

### 🔄 Manual Testing Required (User to Complete)

## Test Scenarios

### 1. Display Modes Testing
**Location:** Main Dashboard

- [ ] **Grid Mode**
  - Open dashboard
  - Select Grid display mode
  - Verify cameras arranged in grid layout
  - Check responsive sizing

- [ ] **Vertical Mode**
  - Switch to Vertical mode
  - Verify cameras stacked vertically
  - Check scrolling if many cameras

- [ ] **Horizontal Mode**
  - Switch to Horizontal mode
  - Verify cameras arranged horizontally
  - Check horizontal scrolling

- [ ] **Cycle Mode**
  - Switch to Cycle mode
  - Verify single camera displays
  - Confirm automatic rotation every N seconds
  - Check cycle interval matches settings

### 2. System Settings Testing
**Location:** Settings → System

- [ ] **Recordings Path**
  - Click "📝 Set Path" button
  - Enter custom path (e.g., `/path/to/recordings`)
  - Verify green checkmark appears
  - Verify message shows "Valid and writable"
  - Try invalid path - verify red X appears

- [ ] **Faces Path**
  - Click "📝 Set Path" button
  - Enter custom path (e.g., `/path/to/faces`)
  - Verify validation feedback
  - Try invalid path - verify error message

- [ ] **Display Mode Settings**
  - Change display mode dropdown
  - Click Save
  - Verify success message
  - Go to Dashboard - confirm mode changed

- [ ] **Cycle Interval**
  - Set cycle interval (1-60 seconds)
  - Save settings
  - Go to Dashboard in Cycle mode
  - Verify cameras rotate at correct interval

- [ ] **Max Recording Duration**
  - Set duration (30-1800 seconds)
  - Save settings
  - Trigger recording
  - Verify recording stops at max duration

- [ ] **Theme Selection**
  - Toggle between Light/Dark
  - Save settings
  - Verify theme applies immediately

### 3. Camera Settings Testing
**Location:** Settings → Cameras

- [ ] **Per-Camera Motion Detection Toggle**
  - Disable motion detection for one camera
  - Save settings
  - Verify no motion alerts for that camera
  - Re-enable and verify alerts resume

- [ ] **Per-Camera Recording Toggle**
  - Disable recording for one camera
  - Save settings
  - Trigger motion
  - Verify no new recordings for that camera

- [ ] **Per-Camera Face Detection Toggle**
  - Disable face detection for one camera
  - Save settings
  - Trigger motion with face
  - Verify no face detections for that camera
  - Check recording metadata has 0 faces

### 4. Recording with Custom Paths
**Prerequisites:** Custom paths set in settings

- [ ] **Trigger New Recording**
  - Ensure motion detection enabled
  - Trigger motion event
  - Wait for recording to start
  - Verify recording appears in custom path
  - Check file exists on disk

- [ ] **Recording Metadata**
  - Open recording details
  - Verify metadata includes:
    - Duration
    - File size
    - Face detections (if enabled)
    - Timestamp

- [ ] **Recording Playback**
  - Play recording in browser
  - Verify video loads and plays
  - Check audio (if applicable)
  - Verify no corruption

### 5. Settings Persistence Testing

- [ ] **Restart Server Test**
  - Set custom paths in settings
  - Save
  - Restart the backend server
  - Check logs: `System settings loaded - Recordings: /your/path`
  - Verify paths loaded correctly on startup

- [ ] **Database Persistence**
  - Set all custom settings
  - Save
  - Close browser
  - Restart server
  - Reopen browser
  - Verify all settings persisted

### 6. Face Saving Location Testing

- [ ] **Custom Face Path**
  - Set custom faces path
  - Save and restart server
  - Trigger face detection
  - Check logs: `faces_dir=/your/custom/path`
  - Verify new faces saved to custom path

- [ ] **Face Recognition**
  - Add known face via Faces page
  - Trigger detection
  - Verify face recognized correctly
  - Check face saved in custom directory

### 7. Edge Cases & Error Handling

- [ ] **Invalid Path Entry**
  - Enter non-existent path
  - Verify error message displayed
  - Verify save disabled or warning shown

- [ ] **Permission Issues**
  - Enter path without write permissions
  - Verify error: "Path is not writable"

- [ ] **Empty Path**
  - Clear path field
  - Verify defaults to "recordings" or "faces"

- [ ] **Very Long Recording**
  - Set max duration to 1800 seconds (30 min)
  - Trigger extended recording
  - Verify stops at 30 minutes
  - Check file not corrupted

- [ ] **Multiple Cameras**
  - If multiple cameras available
  - Test individual toggles
  - Verify settings apply per-camera

## API Testing (Optional - for developers)

```bash
# Test path validation
curl -X POST http://localhost:8000/api/settings/validate-path \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"path": "/custom/path", "create_if_missing": true}'

# Expected: 200 OK with validation response

# Test settings save
curl -X PATCH http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"recordings_path": "/custom/recordings", "max_recording_duration": 600}'

# Expected: 200 OK with updated settings

# Test camera settings
curl -X PATCH http://localhost:8000/api/cameras/usb_camera_0 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"motion_detection_enabled": false}'

# Expected: 200 OK with camera updated
```

## Known Issues

1. **Face Detection Count:** Metadata may show 0 detections if:
   - Face detection was disabled during recording
   - Faces not clearly visible (angle, lighting, distance)
   - Video recorded before enabling face detection

2. **Video Corruption:** MP4 files may be corrupted if:
   - Recording interrupted (server crash, power loss)
   - File header not finalized properly
   - Disk space ran out during recording

3. **Path Loading:** Server must be restarted for custom paths to take effect fully

## Post-Testing Checklist

After completing all tests:

- [ ] All display modes work correctly
- [ ] Path validation working for both paths
- [ ] Settings persist across server restarts
- [ ] Custom paths being used for new recordings/faces
- [ ] Per-camera toggles working independently
- [ ] No console errors in browser
- [ ] No backend errors in logs
- [ ] Ready for production deployment

## Notes

- Test with actual camera if possible
- Test on different browsers (Chrome, Firefox, Safari)
- Test on different screen sizes
- Monitor backend logs during testing
- Check disk space before long recordings

## Version Comparison

| Feature | v3.5.0 | v3.5.1.4 |
|---------|--------|----------|
| Custom Paths | ❌ | ✅ |
| Path Validation | ❌ | ✅ |
| Per-Camera Toggles | ✅ | ✅ |
| Display Modes | ✅ | ✅ |
| Settings UI | ✅ | ✅ (Enhanced) |

---

**Testing Started:** October 11, 2025  
**Tester:** User  
**Version Tested:** v3.5.1.4
