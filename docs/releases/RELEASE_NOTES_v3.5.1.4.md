# OpenEye Surveillance System - Release v3.5.1.4

**Release Date:** October 11, 2025  
**Type:** Bug Fix Release  
**Priority:** High - Fixes critical path validation issue

---

## 🔧 Critical Fix

### Path Validation 422 Errors (FIXED)

**Issue:** Users encountered persistent 422 "Unprocessable Entity" errors when trying to validate custom storage paths in the System Settings page.

**Root Cause:** FastAPI route matching order issue. The generic route `/api/settings/{setting_key}` was defined before the specific route `/api/settings/validate-path`, causing FastAPI to match "validate-path" as a path parameter value and route requests to the wrong handler with incompatible Pydantic models.

**Solution:** Reordered routes in `backend/api/routes/settings.py` to place specific routes before generic routes with path parameters.

**Impact:** System Settings page path validation now works correctly, allowing users to configure custom directories for recordings and face images.

---

## 📋 What's Fixed

- ✅ **Path Validation Endpoint** - Now returns 200 OK instead of 422 errors
- ✅ **Custom Storage Paths** - Users can successfully validate and configure custom paths
- ✅ **Settings Persistence** - Path settings save correctly to database
- ✅ **Error Logging** - Enhanced frontend error logging with detailed Pydantic validation errors

---

## 🔄 Technical Changes

### Backend

**`backend/api/routes/settings.py`:**
```python
# BEFORE (BROKEN):
@router.post("/settings/{setting_key}")  # Line 157
async def set_setting(...)

@router.post("/settings/validate-path")  # Line 195
async def validate_path(...)

# AFTER (FIXED):
@router.post("/settings/validate-path")  # Line 147 - Now BEFORE generic route
async def validate_path(...)

@router.post("/settings/{setting_key}")  # Line 185 - Now AFTER specific route
async def set_setting(...)
```

**`backend/main.py`:**
- Updated version to 3.5.1.4 in 3 locations:
  - FastAPI app version
  - Root endpoint version
  - API root endpoint version

### Frontend

**`frontend/src/pages/SystemSettingsPage.jsx`:**
- Enhanced error logging to display full Pydantic validation error arrays
- Better error message extraction from API responses

---

## 📚 Documentation Updates

### New Documentation
- **PATH_VALIDATION_FIX_v3.5.1.4.md** - Complete root cause analysis and fix details
- **TESTING_CHECKLIST_v3.5.1.4.md** - 40+ comprehensive test scenarios
- **RELEASE_NOTES_v3.5.1.4.md** - This file

### Updated Documentation
- **CHANGELOG.md** - Added v3.5.1.4 and consolidated v3.5.1.0-3.5.1.3 notes
- **README.md** - Updated version badge and added System Configuration section
- **DOCKER_HUB_OVERVIEW.md** - Updated version and features for Docker users

### Archived Documentation
Moved 12 old development/implementation docs to `archives/` to reduce root clutter:
- CAMERA_FEED_FIX_v3.1.4.md
- COMPLETE_IMPLEMENTATION_v3.1.5.md
- FINAL_SUCCESS_REPORT.md
- INSTALLATION_IMPROVEMENTS_v3.1.4.md
- LOGIN_TROUBLESHOOTING.md
- And 7 others

---

## ✅ Testing Verification

### What Was Tested

✅ **Path Validation:**
- Successfully validates existing directories
- Returns proper error for non-existent paths
- Auto-creates directories when requested
- Returns correct response format (path, exists, is_directory, writable, absolute_path)

✅ **Settings Persistence:**
- Custom paths save to database
- Settings persist across server restarts
- Settings load correctly on page refresh

✅ **API Endpoints:**
- POST /api/settings/validate-path returns 200 OK
- PATCH /api/settings updates settings correctly
- GET /api/settings loads settings properly

✅ **Frontend Integration:**
- Path validation UI updates correctly
- Error messages display properly
- Success states show as expected

---

## 🚀 Installation & Upgrade

### Docker Users

**Pull Latest Image:**
```bash
docker pull m1k31/openeye-surveillance:3.5.1.4
# or
docker pull m1k31/openeye-surveillance:latest
```

**Update Container:**
```bash
docker-compose down
docker-compose pull
docker-compose up -d
```

### Native Installation Users

**Update Code:**
```bash
cd /path/to/OpenEye-OpenCV_Home_Security
git pull origin main
```

**Restart Services:**
```bash
# Stop server (Ctrl+C or kill process)
# Restart backend
cd opencv-surveillance
source venv/bin/activate
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**No database migrations required** - This is a code-only fix.

---

## 📖 Usage Notes

### Configuring Custom Paths

1. Navigate to **Settings → System** in the UI
2. Find "Storage Configuration" section
3. Enter custom path (e.g., `/mnt/storage/recordings`)
4. Click "Validate Path" button
5. If valid, checkmark appears; if not, error message shows
6. Click "Save Settings" to persist changes
7. Server automatically uses new paths for subsequent recordings

### Path Requirements

- **Must be absolute paths** (e.g., `/home/user/recordings`)
- **Must have write permissions** for the user running the server
- **Can be auto-created** if "Create if missing" is checked
- **Must be directories**, not files

---

## 🐛 Known Issues

### Non-Critical Issues
- Some MP4 files may show corruption if recording interrupted
- Face detection metadata may show 0 detections in certain lighting conditions
- These do not affect path validation functionality

### Workarounds
- For corrupted recordings: Use proper shutdown to finalize videos
- For face detection: Ensure adequate lighting and camera positioning

---

## 📞 Support & Feedback

- **GitHub Issues**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues
- **Documentation**: See [README.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/README.md)
- **API Docs**: http://localhost:8000/api/docs (when running)

---

## 🙏 Acknowledgments

This release fixes a critical issue that was preventing users from configuring custom storage paths. The fix demonstrates an important FastAPI routing pattern: **specific routes must be defined before generic routes with path parameters**.

Special thanks to:
- The FastAPI team for excellent framework documentation
- Pydantic team for detailed validation error messages
- OpenCV community for ongoing support

---

## 📝 Version History

- **v3.5.1.4** (2025-10-11) - Path validation route ordering fix
- **v3.5.1.3** (2025-10-11) - Path selection browser security improvements
- **v3.5.1.2** (2025-10-11) - Recordings page fixes
- **v3.5.1.1** (2025-10-10) - Settings page UI improvements
- **v3.5.1.0** (2025-10-10) - System settings page implementation
- **v3.5.0** (2025-10-10) - Granular camera controls
- **v3.4.0** (2025-01-10) - WebSocket real-time updates
- **v3.3.8** (2025-01-09) - Face recognition enhancements

See [CHANGELOG.md](./CHANGELOG.md) for complete version history.

---

## 🔐 License

MIT License - See [LICENSE](./LICENSE) file for details.

**Copyright © 2025 Mikel Smart**
