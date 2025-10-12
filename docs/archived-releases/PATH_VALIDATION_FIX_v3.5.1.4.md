# Path Validation Fix - v3.5.1.4

**Date:** October 11, 2025  
**Status:** ✅ COMPLETED

## Overview

Fixed critical path validation bug where the `/api/settings/validate-path` endpoint was returning 422 errors due to FastAPI route ordering issue.

## Problem

Path validation requests were failing with 422 Unprocessable Entity errors. The Pydantic validation errors showed:
```json
{
  "type": "missing",
  "loc": ["body", "setting_key"],
  "msg": "Field required"
}
```

## Root Cause

FastAPI matches routes in order. The generic route `/settings/{setting_key}` was defined **before** the specific route `/settings/validate-path`, causing FastAPI to match "validate-path" as a path parameter value for `setting_key`. This routed requests to the wrong endpoint which expected `SystemSettingBase` instead of `PathValidationRequest`.

## Solution

Reordered routes in `backend/api/routes/settings.py`:

**Before:**
```python
@router.post("/settings/{setting_key}")  # Line 157 - Generic route FIRST
async def set_setting(...)

@router.post("/settings/validate-path")  # Line 195 - Specific route SECOND
async def validate_path(...)
```

**After:**
```python
@router.post("/settings/validate-path")  # Specific route FIRST
async def validate_path(...)

@router.post("/settings/{setting_key}")  # Generic route SECOND  
async def set_setting(...)
```

### Key Principle
**Specific routes must be defined before generic routes with path parameters in FastAPI.**

## Files Modified

### Backend
- `backend/api/routes/settings.py`
  - Added `PathValidationRequest` Pydantic model (lines 59-61)
  - Updated `validate_path()` endpoint to accept request body (line 198)
  - **Reordered routes** - moved validate-path before generic {setting_key} route
  - Added explanatory comments about route ordering

### Frontend
- `frontend/src/pages/SystemSettingsPage.jsx`
  - Updated `validatePath()` to send JSON request body instead of query params
  - Added enhanced error logging with Pydantic error array expansion
  - Improved error message extraction for user display

## Testing Results

✅ **Path Validation Working:**
```bash
POST /api/settings/validate-path HTTP/1.1" 200 OK
```

✅ **Request Format:**
```javascript
{
  path: '/path/to/recordings',
  create_if_missing: true
}
```

✅ **Response Format:**
```json
{
  "path": "/path/to/recordings",
  "exists": true,
  "is_directory": true,
  "writable": true,
  "absolute_path": "/path/to/recordings"
}
```

## Related Issues

- **RecordingsPage Fix** (v3.5.1.2) - Fixed API integration
- **Settings Bug Fixes** (v3.5.1.1) - Fixed NaN input errors
- **Path Selection Improvements** (v3.5.1.3) - Added directory helper
- **Browser Security Workaround** - Changed from file picker to prompt dialog

## Impact

- ✅ Users can now validate custom storage paths
- ✅ Path validation happens in real-time with visual feedback
- ✅ Settings can be saved with confidence that paths are valid
- ✅ Directory creation on-demand works correctly

## Lessons Learned

1. **FastAPI Route Ordering Matters:** Always define specific routes before generic ones with path parameters
2. **Debug Logging is Essential:** Enhanced error logging helped identify the Pydantic validation errors
3. **Server Reload Issues:** uvicorn --reload may not always pick up changes; force restart if needed
4. **Testing is Critical:** Direct endpoint testing with curl revealed the routing issue

## Next Steps

- ✅ Path validation working
- 🔄 Comprehensive testing of all system features
- 📦 Docker build and push
- 🚀 GitHub commit and release

## Version History

- **v3.5.1.4** - Fixed path validation route ordering
- **v3.5.1.3** - Added path selection helper
- **v3.5.1.2** - Fixed RecordingsPage API integration
- **v3.5.1.1** - Fixed settings input NaN errors
- **v3.5.1** - UI Enhancements
- **v3.5.0** - Granular Controls Implementation
