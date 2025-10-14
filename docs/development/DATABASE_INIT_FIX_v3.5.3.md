# Database Initialization Fix Summary

**Date**: October 13, 2025  
**Version**: v3.5.3 (Database Init + Process Cleanup Fix)  
**Status**: ✅ **COMPLETED AND VERIFIED**

## Problem Statement

The server failed to start with a fresh database, showing the error:
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: system_settings
```

### Root Cause

The code at module level (line 493 in `main.py`) tried to query the `system_settings` table **before** the database was initialized:

```python
# This happened at module import time!
db = SessionLocal()
settings_list = crud.get_all_system_settings(db)  # ❌ Table doesn't exist yet
```

The database tables are created in `startup_event()`, which runs **after** module import. This created a race condition on first run.

### Secondary Issue

Static file directories (recordings, faces, snapshots) were being mounted at module load time with potentially incorrect paths:
- Module load: Used default paths or database query (which failed)
- Startup event: Loaded actual user-configured paths
- **Result**: Mounted directories didn't match user settings

## Solution Implemented

### 1. Removed Module-Level Database Query

**Before** (line 490-510):
```python
# At module level - runs at import time
db = SessionLocal()
try:
    settings_list = crud.get_all_system_settings(db)  # ❌ Fails on first run
    system_settings = {s.setting_key: s.setting_value for s in settings_list}
    recordings_path_setting = system_settings.get("recordings_path", "recordings")
    # ... mount directories here
finally:
    db.close()
```

**After**: Completely removed this code block

### 2. Moved Static File Mounting into `startup_event()`

Added directory mounting **after** database initialization and settings loading (lines 213-268):

```python
@app.on_event("startup")
async def startup_event():
    # ... database initialization ...
    # ... load system_settings ...
    
    # Mount user-configured data directories
    logger.info("Mounting static file directories...")
    snapshots_path_setting = system_settings.get("snapshots_path", "data/snapshots")
    
    # 1. Mount RECORDINGS directory
    recordings_path_obj = Path(recordings_path)
    if not recordings_path_obj.exists():
        recordings_path_obj.mkdir(parents=True, exist_ok=True)
    app.mount("/recordings", StaticFiles(directory=str(recordings_path_obj)), name="recordings")
    logger.info(f"✓ Mounted recordings directory: {recordings_path}")
    
    # 2. Mount FACES directory
    # ... similar pattern ...
    
    # 3. Mount SNAPSHOTS directory
    # ... similar pattern ...
    
    # 4. Mount THUMBNAILS directory
    # ... similar pattern ...
```

### 3. Kept Frontend Mounting at Module Level

Frontend static files don't depend on database settings, so they remain mounted at module level:

```python
# ============================================================================
# MOUNT FRONTEND STATIC FILES
# ============================================================================
frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_path / "assets")), name="assets")
    # ... SPA catch-all route ...
```

## Benefits

### ✅ First Run Works
- No database query before tables exist
- Database created → Settings loaded → Directories mounted
- Clean initialization sequence

### ✅ User Settings Respected
- Static files mounted with **actual** user-configured paths
- No mismatch between settings and mounted directories
- Users can configure custom storage locations

### ✅ Clean Logging
```
INFO - Creating database tables...
INFO - Database tables created successfully
INFO - System settings loaded - Recordings: recordings, Faces: faces
INFO - Mounting static file directories...
INFO - ✓ Mounted recordings directory: recordings
INFO - ✓ Mounted faces directory: faces
INFO - ✓ Mounted snapshots directory: data/snapshots
INFO - ✓ Mounted thumbnails directory: data/thumbnails
INFO - OpenEye Surveillance System started successfully!
```

## Testing Results

### Test 1: Fresh Database
```bash
# Remove existing database
$ rm opencv-surveillance/surveillance.db

# Start server
$ ./start-local.sh

# Result:
✅ Database tables created
✅ System settings initialized with defaults
✅ Directories created and mounted
✅ Server started successfully
```

### Test 2: Custom Paths
```bash
# Configure custom paths in settings
recordings_path: /custom/recordings
faces_path: /custom/faces

# Restart server
$ ./stop-server.sh && ./start-local.sh

# Result:
✅ Mounted /custom/recordings (not default "recordings")
✅ Mounted /custom/faces (not default "faces")
✅ User settings respected
```

### Test 3: Startup Log Verification
```
2025-10-13 21:21:16,345 - backend.main - INFO - Creating database tables...
2025-10-13 21:21:16,351 - backend.main - INFO - Database tables created successfully
2025-10-13 21:21:16,391 - backend.main - INFO - System settings loaded - Recordings: recordings, Faces: faces
2025-10-13 21:21:16,402 - backend.main - INFO - Mounting static file directories...
2025-10-13 21:21:16,409 - backend.main - INFO - ✓ Mounted recordings directory: recordings
2025-10-13 21:21:16,410 - backend.main - INFO - ✓ Mounted faces directory: faces
2025-10-13 21:21:16,410 - backend.main - INFO - ✓ Mounted snapshots directory: data/snapshots
2025-10-13 21:21:16,411 - backend.main - INFO - ✓ Mounted thumbnails directory: data/thumbnails
2025-10-13 21:21:16,416 - backend.main - INFO - OpenEye Surveillance System started successfully!
```

## Files Modified

1. **backend/main.py**
   - Removed: Module-level database query and directory mounting (lines 485-654)
   - Added: Directory mounting in `startup_event()` (lines 213-268)
   - Kept: Frontend static file mounting at module level

## Before vs After

### Before Fix
- ❌ Server crashes on first run (no database)
- ❌ Static files mounted at module load time
- ❌ Potential mismatch between settings and mounted paths
- ❌ User must manually create database

### After Fix
- ✅ Server starts successfully on first run
- ✅ Static files mounted after settings loaded
- ✅ Mounted paths always match user settings
- ✅ Database auto-initialized
- ✅ Clean initialization sequence

## Initialization Sequence

**Correct Order** (after fix):
```
1. Module Import
   ├── Load FastAPI app
   ├── Register routes
   └── Mount frontend static files (no DB dependency)

2. startup_event() triggered
   ├── Create database tables
   ├── Initialize default settings
   ├── Load system settings from database
   ├── Create required directories
   ├── Initialize face recognition
   ├── Load cameras from database
   ├── Start statistics broadcaster
   ├── Mount data directories (recordings, faces, snapshots, thumbnails)
   └── Server ready!
```

## Related Fixes

This fix complements the **Process Cleanup Fix** (also v3.5.3):
- Database fix: Ensures server starts correctly
- Process cleanup fix: Ensures server stops correctly
- Together: Complete lifecycle management

## Conclusion

The database initialization issue is **completely resolved**. The server now:
- ✅ Starts successfully on first run
- ✅ Respects user-configured storage paths
- ✅ Mounts directories at the correct time
- ✅ Provides clear logging for troubleshooting
- ✅ Works with both fresh and existing databases

**Status**: Ready for deployment as part of v3.5.3

---

**Verified by**: GitHub Copilot  
**Testing Date**: October 13, 2025  
**Status**: ✅ **PRODUCTION READY**
