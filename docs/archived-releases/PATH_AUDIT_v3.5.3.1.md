# Path Handling Audit - OpenEye v3.5.3.1

**Date:** October 14, 2025  
**Purpose:** Comprehensive audit of file/directory path handling from UI → API → Backend  
**Issue:** Thumbnails showing red X - need to trace entire path flow

---

## 🎯 Audit Scope

### Files Being Served
1. **Snapshots** (motion detection images)
2. **Thumbnails** (auto-generated smaller versions)
3. **Recordings** (video files)
4. **Face Images** (face recognition training data)

### Path Flow Stages
```
Database Storage → Backend API → Middleware → Frontend Request → Browser Display
```

---

## 📊 Current Path Audit Results

### 1. DATABASE STORAGE

#### Motion Events Table
```sql
-- backend/database/models.py line 53
snapshot_path = Column(String, nullable=True)
```

**Stored Path Format:**
```
data/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg
```

**Characteristics:**
- ✅ Relative path (no leading slash)
- ✅ Includes directory structure
- ✅ Platform-agnostic (forward slashes)

---

### 2. BACKEND - PATH CREATION

#### Snapshot Save Location
**File:** `backend/core/camera_manager.py` lines 241-275

```python
def _save_motion_snapshot(self, frame: np.ndarray, motion_areas: list) -> Optional[str]:
    # Get snapshots directory from settings
    snapshots_dir = Path(self.snapshots_path)  # Default: "data/snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    camera_name = self.camera_id or "unknown"
    filename = f"motion_{camera_name}_{timestamp}.jpg"
    
    # Full path for saving
    snapshot_path = snapshots_dir / filename
    
    # Save the frame
    success = cv2.imwrite(str(snapshot_path), frame)
    
    # Return path as string
    return str(snapshot_path)  # Returns: "data/snapshots/motion_..."
```

**Output Format:**
```
data/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg
```

**Path Characteristics:**
- ✅ Relative to application root (`opencv-surveillance/`)
- ✅ Uses Path objects (cross-platform)
- ✅ Converted to string for database storage
- ✅ No leading slash

---

### 3. BACKEND - STATIC FILE MOUNTING

#### Current Configuration (PROBLEMATIC)
**File:** `backend/main.py` lines 107-156

**OLD LOCATION (Inside @app.on_event("startup")):**
```python
@app.on_event("startup")
async def startup_event():
    # ... other startup code ...
    
    # Mount SNAPSHOTS directory
    snapshots_path_obj = Path(snapshots_path_setting)  # "data/snapshots"
    app.mount(
        "/data/snapshots",
        StaticFiles(directory=str(snapshots_path_obj)),
        name="snapshots"
    )
    
    # Mount LEGACY snapshots (CONDITIONAL - BUG!)
    if str(snapshots_path_obj) != "data/snapshots":  # ❌ Always False!
        app.mount(
            "/legacy/snapshots",
            StaticFiles(directory=str(local_snapshots)),
            name="snapshots_local"
        )
```

**Problems Identified:**
1. ❌ Mounts defined INSIDE startup event (after route registration)
2. ❌ `/legacy/snapshots` mount is CONDITIONAL and never executes
3. ❌ Catch-all SPA route `@app.get("/{full_path:path}")` registered first
4. ❌ Catch-all intercepts static file requests before they reach mounts

**NEW LOCATION (Fixed - Before Routes):**
```python
# After app creation and middleware, BEFORE any routes
app.mount("/recordings", StaticFiles(directory="recordings"), name="recordings")
app.mount("/faces", StaticFiles(directory="faces"), name="faces")
app.mount("/data/snapshots", StaticFiles(directory="data/snapshots"), name="snapshots")
app.mount("/legacy/snapshots", StaticFiles(directory="data/snapshots"), name="snapshots_legacy")
app.mount("/data/thumbnails", StaticFiles(directory="data/thumbnails"), name="thumbnails")

# ... THEN routes are defined ...
```

**Expected Behavior:**
- FastAPI checks mounts BEFORE routes
- `/legacy/snapshots/file.jpg` → Served by StaticFiles
- `/unknown/path` → Caught by catch-all SPA route

---

### 4. BACKEND - API ENDPOINTS

#### Motion Events Endpoint
**File:** `backend/api/routes/motion_events.py`

```python
@router.get("/motion-events/")
async def get_motion_events(limit: int = 100):
    events = db.query(MotionEvent).order_by(
        MotionEvent.detected_at.desc()
    ).limit(limit).all()
    
    return {"events": events}
```

**Response Format:**
```json
{
  "events": [
    {
      "id": 286,
      "camera_id": "usb_camera_0",
      "snapshot_path": "data/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg",
      "detected_at": "2025-10-13T23:25:06",
      "motion_percentage": 99.9
    }
  ]
}
```

**Path Characteristics:**
- ✅ Returns raw database path
- ✅ No URL conversion at backend level
- ✅ Frontend responsible for converting to web URL

---

### 5. MIDDLEWARE

#### CORS Configuration
**File:** `backend/main.py` lines 88-94

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Impact on Paths:**
- ✅ Allows cross-origin requests
- ✅ No path transformation
- ✅ Snapshots accessible from frontend

#### Security Middleware
- **SQLInjectionProtection:** No path impact
- **RateLimiter:** No path impact
- **SecurityHeadersMiddleware:** Adds headers, no path changes

---

### 6. FRONTEND - API CLIENT

#### Snapshot Fetching
**File:** `frontend/src/pages/RecordingsPage.jsx` lines 53-65

```javascript
const loadSnapshots = async () => {
  try {
    // Fetch motion events from API
    const response = await apiClient.get('/motion-events/?limit=100');
    
    // Extract events array
    const events = response.data.events || response.data;
    const snapshotsData = Array.isArray(events) ? events : [];
    
    // Filter events that have snapshot_path
    const filtered = snapshotsData.filter(event => event.snapshot_path);
    
    setSnapshots(filtered);
  } catch (err) {
    console.error('Error loading snapshots:', err);
    setSnapshots([]);
  }
};
```

**Data Received:**
```javascript
[
  {
    id: 286,
    camera_id: "usb_camera_0",
    snapshot_path: "data/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg",
    detected_at: "2025-10-13T23:25:06"
  }
]
```

---

### 7. FRONTEND - PATH CONVERSION

#### convertPathToUrl Function
**File:** `frontend/src/pages/RecordingsPage.jsx` lines 111-147

```javascript
const convertPathToUrl = (filePath) => {
  if (!filePath) return '';
  
  // If already a web URL, return as-is
  if (filePath.startsWith('http://') || filePath.startsWith('https://')) {
    return filePath;
  }
  
  // If already a web path (starts with /), return as-is
  if (filePath.startsWith('/data/') || filePath.startsWith('/legacy/') || 
      filePath.startsWith('/recordings/') || filePath.startsWith('/faces/')) {
    return filePath;
  }

  // Extract just the filename
  const filename = filePath.split('/').pop().split('\\').pop();
  
  // Check if this is a snapshot
  if (filePath.includes('data/snapshots') || filePath.includes('data\\snapshots')) {
    const url = `/legacy/snapshots/${filename}`;
    console.log('🔄 Converting snapshot path:', filePath, '→', url);
    return url;
  }
  
  // Check if this is a face detection snapshot
  if (filePath.includes('faces') || filePath.includes('Faces')) {
    return `/faces/${filename}`;
  }
  
  // Check if this is a recording
  if (filePath.includes('recordings') || filePath.includes('Recordings')) {
    return `/recordings/${filename}`;
  }
  
  // Default fallback - try legacy snapshots
  console.log('⚠️ Using fallback for path:', filePath, '→ /legacy/snapshots/' + filename);
  return `/legacy/snapshots/${filename}`;
};
```

**Conversion Examples:**
```javascript
Input:  "data/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg"
Output: "/legacy/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg"

Input:  "/legacy/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg"
Output: "/legacy/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg" (no change)
```

**Logic:**
1. ✅ Checks if already a full URL → pass through
2. ✅ Checks if already a web path → pass through
3. ✅ Extracts filename from full path
4. ✅ Routes `data/snapshots` paths to `/legacy/snapshots/`
5. ✅ Has fallback to `/legacy/snapshots/` for unknown paths

---

### 8. FRONTEND - IMAGE RENDERING

#### Snapshot Display
**File:** `frontend/src/pages/RecordingsPage.jsx` lines 273-288

```javascript
filteredSnapshots.map((snapshot) => {
  const imageUrl = convertPathToUrl(snapshot.snapshot_path);
  return (
    <div key={snapshot.id} style={styles.snapshotCard}>
      <img
        src={imageUrl}
        alt={snapshot.camera_id}
        style={styles.snapshotImage}
        onClick={() => setSelectedRecording(snapshot)}
        onError={(e) => {
          console.error(
            'Failed to load snapshot:', 
            snapshot.snapshot_path, 
            '→ Converted to:', imageUrl, 
            '→ Failed URL:', e.target.src
          );
          e.target.src = 'data:image/svg+xml,...';  // Red X fallback
        }}
      />
      {/* ... snapshot info ... */}
    </div>
  );
})
```

**Browser Request:**
```
GET http://localhost:8000/legacy/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg
```

---

### 9. BROWSER - HTTP REQUEST

#### Request Flow
```
Browser → http://localhost:8000/legacy/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg
         ↓
FastAPI Application
         ↓
Route Matching Process
         ↓
Option A: StaticFiles mount (/legacy/snapshots) ✅ DESIRED
Option B: Catch-all route (/{full_path:path})   ❌ CURRENTLY HAPPENING
```

#### Current Problem
**Catch-all Route Definition:**
```python
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # This matches EVERYTHING, including /legacy/snapshots/...
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    
    # Returns index.html for SPA routing
    return FileResponse(frontend_path / "index.html")
```

**What's Happening:**
1. Browser requests: `/legacy/snapshots/file.jpg`
2. FastAPI checks routes in registration order
3. Catch-all `/{full_path:path}` matches first (registered at module level)
4. Returns `index.html` instead of image
5. Browser tries to display HTML as JPEG → Red X

**Why Mounts Don't Work:**
- Mounts defined in `@app.on_event("startup")` are added AFTER route registration
- By the time mounts are added, catch-all is already registered and takes precedence
- FastAPI routes are matched in registration order

---

## 🔧 IDENTIFIED ISSUES

### Issue #1: Mount Timing
**Problem:** Static file mounts happen inside `startup` event, after catch-all route is registered

**Evidence:**
```python
# Module level (line 557) - Registered FIRST
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return FileResponse("index.html")

# Inside startup event (lines 221-265) - Registered SECOND
@app.on_event("startup")
async def startup_event():
    app.mount("/legacy/snapshots", StaticFiles(...))  # TOO LATE!
```

**Impact:** Catch-all intercepts ALL requests before mounts can handle them

---

### Issue #2: Legacy Mount Condition
**Problem:** `/legacy/snapshots` mount has incorrect conditional logic

**Code:**
```python
if str(snapshots_path_obj) != "data/snapshots":  # ❌ Always False for default config
    app.mount("/legacy/snapshots", ...)
```

**Impact:** Legacy endpoint never mounted when using default snapshot path

---

### Issue #3: Catch-all Route Too Broad
**Problem:** Catch-all matches ALL paths, not just SPA routes

**Current:**
```python
@app.get("/{full_path:path}")  # Matches: /any/path/including/static/files
```

**Should Be:**
- Either: Mount static files BEFORE catch-all is registered
- Or: Make catch-all more restrictive (exclude known static paths)

---

### Issue #4: No MIME Type Handling
**Observation:** When HTML is returned instead of image, Content-Type is `text/html`

**Browser Behavior:**
- Expects: `Content-Type: image/jpeg`
- Receives: `Content-Type: text/html; charset=utf-8`
- Result: Displays red X (cannot render HTML as image)

---

## ✅ PROPOSED FIX

### Fix #1: Move Static Mounts Before Routes
```python
# After app creation and middleware (line 107)
app = FastAPI(...)
app.add_middleware(...)

# Mount static files HERE (before any routes)
app.mount("/recordings", StaticFiles(directory="recordings"), name="recordings")
app.mount("/faces", StaticFiles(directory="faces"), name="faces")
app.mount("/data/snapshots", StaticFiles(directory="data/snapshots"), name="snapshots")
app.mount("/legacy/snapshots", StaticFiles(directory="data/snapshots"), name="snapshots_legacy")
app.mount("/data/thumbnails", StaticFiles(directory="data/thumbnails"), name="thumbnails")

# THEN define routes
@app.on_event("startup")
async def startup_event():
    # No more mounting here, just logging
    logger.info("Static files already mounted")

# Catch-all SPA route comes LAST
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    ...
```

**Benefits:**
- ✅ Mounts registered before catch-all
- ✅ FastAPI checks mounts first
- ✅ Static files served correctly
- ✅ SPA routing still works for other paths

---

### Fix #2: Always Mount Legacy Endpoint
```python
# Remove conditional - always mount both
app.mount("/data/snapshots", StaticFiles(...), name="snapshots")
app.mount("/legacy/snapshots", StaticFiles(...), name="snapshots_legacy")  # Always!
```

**Benefits:**
- ✅ Backward compatibility guaranteed
- ✅ Works with default or custom snapshot paths
- ✅ No conditional logic bugs

---

### Fix #3: Update Startup Logging
```python
@app.on_event("startup")
async def startup_event():
    # ... other startup code ...
    
    # Log that static files are already mounted
    logger.info("Static file directories already mounted during app initialization")
    logger.info(f"✓ Recordings: {recordings_path}")
    logger.info(f"✓ Faces: {faces_path}")
    logger.info(f"✓ Snapshots: data/snapshots")
    logger.info(f"✓ Legacy snapshots: data/snapshots")
    logger.info(f"✓ Thumbnails: data/thumbnails")
```

---

## 🧪 TESTING PLAN

### Test 1: Backend Static File Serving
```bash
# Test legacy snapshots endpoint
curl -I http://localhost:8000/legacy/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg

# Expected:
# HTTP/1.1 200 OK
# Content-Type: image/jpeg
# Content-Length: 456000

# NOT:
# HTTP/1.1 200 OK
# Content-Type: text/html; charset=utf-8  ❌
```

### Test 2: Download Actual File
```bash
curl -s -o /tmp/test.jpg http://localhost:8000/legacy/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg
file /tmp/test.jpg

# Expected:
# /tmp/test.jpg: JPEG image data

# NOT:
# /tmp/test.jpg: HTML document text  ❌
```

### Test 3: Frontend Path Conversion
```javascript
// In browser console
const path = "data/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg";
console.log(convertPathToUrl(path));

// Expected:
// "/legacy/snapshots/motion_usb_camera_0_20251013_232506_559018.jpg"
```

### Test 4: Image Display
```
1. Navigate to http://localhost:8000/events
2. Check browser console for:
   🔄 Converting snapshot path: data/snapshots/... → /legacy/snapshots/...
3. Verify no "Failed to load snapshot" errors
4. Verify thumbnails display (no red X)
```

### Test 5: Network Tab
```
1. Open DevTools → Network tab
2. Filter: Img
3. Check snapshot requests:
   - Status: 200 OK ✅
   - Type: jpeg ✅
   - Size: ~450 KB ✅
   
NOT:
   - Status: 200 OK but Type: html ❌
```

---

## 📁 FILE SUMMARY

### Files Involved in Path Handling

| File | Purpose | Status |
|------|---------|--------|
| `backend/database/models.py` | Stores snapshot paths | ✅ OK |
| `backend/core/camera_manager.py` | Creates snapshots, returns paths | ✅ OK |
| `backend/main.py` | Mounts static files, routes | ❌ NEEDS FIX |
| `backend/api/routes/motion_events.py` | Returns snapshot data | ✅ OK |
| `frontend/src/pages/RecordingsPage.jsx` | Converts paths, displays images | ✅ OK |
| `frontend/src/components/HelpButton.css` | (Not related to paths) | ✅ OK |

---

## 🎯 ROOT CAUSE SUMMARY

### The Problem
```
FastAPI Route Registration Order:
1. @app.get("/{full_path:path}") - Catch-all ← Registered at module level
2. app.mount("/legacy/snapshots", ...) - Static files ← Registered in startup event

Result: Catch-all intercepts /legacy/snapshots/ requests before StaticFiles can serve them
```

### The Solution
```
FastAPI Route Registration Order (Fixed):
1. app.mount("/legacy/snapshots", ...) - Static files ← Registered at module level
2. @app.get("/{full_path:path}") - Catch-all ← Registered at module level (after mounts)

Result: StaticFiles handles /legacy/snapshots/ requests, catch-all only gets remaining paths
```

---

## 📝 IMPLEMENTATION STATUS

- [x] Issue identified and documented
- [x] Fix designed (move mounts before routes)
- [x] Code changes prepared
- [ ] Server restart required
- [ ] Testing required
- [ ] Verification required

---

## 🚀 NEXT STEPS

1. **Apply Fix:** Move static file mounts from startup event to module level (after middleware, before routes)
2. **Restart Server:** Kill and restart to apply changes
3. **Test Backend:** Verify `/legacy/snapshots/` serves JPEG not HTML
4. **Test Frontend:** Verify thumbnails display in browser
5. **Document:** Update this audit with test results

---

**Audit Completed:** October 14, 2025, 00:05 PST  
**Auditor:** Development Team  
**Status:** Root cause identified, fix ready for implementation

