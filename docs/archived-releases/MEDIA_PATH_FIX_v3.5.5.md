# Media Path Configuration Fix - v3.5.5

**Date:** October 18, 2025
**Status:** 🔄 In Progress
**Priority:** HIGH - Affects media file access and user experience

---

## 🐛 Problems Identified

### Issue 1: Path Confusion - Multiple Directories
**Symptom:** Files exist in multiple locations, UI doesn't show all snapshots

**Root Cause:**
- Multiple directories exist at different levels:
  - `./recordings/` (empty)
  - `./data/snapshots/` (empty)
  - `./opencv_surveillance/data/snapshots/` (211 files) ✅ ACTUAL
  - `./opencv_surveillance/recordings/` (37 metadata files) ✅ ACTUAL

**Impact:**
- User confusion about where files are stored
- Inconsistent file counts between UI and disk
- Maintenance burden from scattered directories

### Issue 2: Hardcoded Relative Paths
**Symptom:** Paths are relative to server start directory

**Root Cause:**
```python
# backend/main.py (lines 126-147)
recordings_mount_path = Path("recordings")  # Relative to CWD
snapshots_mount_path = Path("data/snapshots")  # Relative to CWD
```

**Problems:**
- If server starts from different directory, paths break
- Hard to change storage location
- No centralized configuration

### Issue 3: Database Path Mismatch
**Symptom:** 215 events in database but only 211 files on disk

**Analysis:**
```bash
Database events: 215
Actual files:    211
Missing files:   4
```

**Cause:** Files were deleted or moved without database cleanup

### Issue 4: No Path Migration Tool
**Symptom:** Users can't easily move media when changing storage location

**Impact:**
- Manual file management required
- Risk of broken references
- Poor user experience

---

## ✅ Proposed Solution

### Phase 1: Centralized Path Configuration

**Create:** `backend/core/paths.py`

```python
from pathlib import Path
import os

# Get project root (where opencv_surveillance/ is)
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Default paths (within opencv_surveillance/)
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_RECORDINGS_DIR = PROJECT_ROOT / "recordings"
DEFAULT_SNAPSHOTS_DIR = DEFAULT_DATA_DIR / "snapshots"
DEFAULT_THUMBNAILS_DIR = DEFAULT_DATA_DIR / "thumbnails"
DEFAULT_FACES_DIR = DEFAULT_DATA_DIR / "faces"

class PathManager:
    """Centralized path management with environment variable support"""

    def __init__(self):
        # Allow override via environment variables
        self.data_dir = Path(os.getenv("OPENEYE_DATA_DIR", DEFAULT_DATA_DIR))
        self.recordings_dir = Path(os.getenv("OPENEYE_RECORDINGS_DIR", DEFAULT_RECORDINGS_DIR))
        self.snapshots_dir = Path(os.getenv("OPENEYE_SNAPSHOTS_DIR", DEFAULT_SNAPSHOTS_DIR))
        self.thumbnails_dir = Path(os.getenv("OPENEYE_THUMBNAILS_DIR", DEFAULT_THUMBNAILS_DIR))
        self.faces_dir = Path(os.getenv("OPENEYE_FACES_DIR", DEFAULT_FACES_DIR))

        # Create directories if they don't exist
        self.ensure_directories()

    def ensure_directories(self):
        """Create all required directories"""
        for dir_path in [
            self.data_dir,
            self.recordings_dir,
            self.snapshots_dir,
            self.thumbnails_dir,
            self.faces_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_relative_path(self, absolute_path: Path) -> str:
        """Convert absolute path to relative (for database storage)"""
        try:
            return str(absolute_path.relative_to(PROJECT_ROOT))
        except ValueError:
            # Path is outside project root, store as absolute
            return str(absolute_path)

    def resolve_path(self, stored_path: str) -> Path:
        """Resolve stored path to absolute path"""
        path = Path(stored_path)
        if path.is_absolute():
            return path
        else:
            return PROJECT_ROOT / path

# Global instance
paths = PathManager()
```

### Phase 2: Update main.py to Use PathManager

```python
from backend.core.paths import paths

# Mount recordings directory
app.mount(
    "/recordings",
    StaticFiles(directory=str(paths.recordings_dir)),
    name="recordings"
)

# Mount snapshots directory
app.mount(
    "/data/snapshots",
    StaticFiles(directory=str(paths.snapshots_dir)),
    name="snapshots"
)

# Mount thumbnails directory
app.mount(
    "/data/thumbnails",
    StaticFiles(directory=str(paths.thumbnails_dir)),
    name="thumbnails"
)
```

### Phase 3: Settings API for Path Configuration

**Add to Settings Model:**
```python
class SystemSettings(BaseModel):
    recordings_path: str = Field(default=str(DEFAULT_RECORDINGS_DIR))
    snapshots_path: str = Field(default=str(DEFAULT_SNAPSHOTS_DIR))
    faces_path: str = Field(default=str(DEFAULT_FACES_DIR))
```

**Add Update Endpoint:**
```python
@router.put("/settings/paths")
def update_storage_paths(
    settings: PathSettings,
    migrate: bool = Query(False, description="Migrate existing files"),
    current_user = Depends(require_admin)
):
    """
    Update storage paths with optional file migration

    - **recordings_path**: New recordings directory
    - **snapshots_path**: New snapshots directory
    - **faces_path**: New faces directory
    - **migrate**: If true, move existing files to new locations
    """
    ...
```

### Phase 4: File Migration Utility

**Create:** `backend/utils/migrate_media.py`

```python
def migrate_files(
    source_dir: Path,
    dest_dir: Path,
    file_pattern: str = "*",
    update_db: bool = True
) -> dict:
    """
    Migrate files from source to destination

    Returns:
        {
            "moved": int,
            "failed": int,
            "updated_records": int
        }
    """
    ...
```

### Phase 5: Database Cleanup Tool

**Create:** `backend/utils/cleanup_orphaned_records.py`

```python
def cleanup_orphaned_snapshots(db: Session) -> dict:
    """
    Remove database records for missing snapshot files

    Returns:
        {
            "total_records": int,
            "orphaned_records": int,
            "cleaned": int
        }
    """
    ...
```

---

## 🚀 Implementation Plan

### Step 1: Create Path Manager ✅
- [ ] Create `backend/core/paths.py`
- [ ] Add tests for path resolution
- [ ] Document environment variables

### Step 2: Update Backend ✅
- [ ] Update `backend/main.py` to use PathManager
- [ ] Update `backend/core/recorder.py` to use PathManager
- [ ] Update `backend/core/motion_detector.py` to use PathManager
- [ ] Update all database write operations

### Step 3: Add Migration Utility ✅
- [ ] Create `backend/utils/migrate_media.py`
- [ ] Add CLI interface: `python -m backend.utils.migrate_media`
- [ ] Add progress reporting

### Step 4: Database Cleanup ✅
- [ ] Create `backend/utils/cleanup_orphaned_records.py`
- [ ] Add dry-run mode
- [ ] Add CLI interface

### Step 5: Settings API ✅
- [ ] Add path configuration to settings
- [ ] Add migration option to update endpoint
- [ ] Update frontend settings page

### Step 6: Frontend Updates ✅
- [ ] Add path configuration UI
- [ ] Add "Migrate Files" button with confirmation
- [ ] Show disk usage statistics

---

## 📊 Current State Analysis

### Directory Structure
```
/Volumes/Storage/Dev/GitHubProjects/OpenEye-OpenCV_Home_Security/
├── recordings/                                    (empty, should delete)
├── data/
│   └── snapshots/                                 (empty, should delete)
└── opencv_surveillance/
    ├── data/
    │   ├── snapshots/                             ✅ 211 files (ACTIVE)
    │   ├── thumbnails/                            ✅ (ACTIVE)
    │   └── faces/                                 ✅ (ACTIVE)
    └── recordings/                                ✅ 37 metadata files (ACTIVE)
```

### Database State
```sql
-- Motion events
SELECT COUNT(*) FROM motion_detection_events;  -- 215 records

-- Check for missing files
SELECT id, snapshot_path
FROM motion_detection_events
WHERE snapshot_path NOT IN (
    -- List of actual files on disk
);
-- Expected: 4 missing files
```

### Recommended Defaults
```python
DEFAULT_DATA_DIR = "/Volumes/Storage/Dev/GitHubProjects/OpenEye-OpenCV_Home_Security/opencv_surveillance/data"
DEFAULT_RECORDINGS_DIR = "/Volumes/Storage/Dev/GitHubProjects/OpenEye-OpenCV_Home_Security/opencv_surveillance/recordings"
DEFAULT_SNAPSHOTS_DIR = "/Volumes/Storage/Dev/GitHubProjects/OpenEye-OpenCV_Home_Security/opencv_surveillance/data/snapshots"
```

---

## 🎯 User Experience Improvements

### Settings Page Additions

```
┌─────────────────────────────────────────────┐
│ Storage Paths                                │
├─────────────────────────────────────────────┤
│                                              │
│ Recordings Directory:                        │
│ ┌──────────────────────────────────────────┐│
│ │ /...opencv_surveillance/recordings       ││
│ └──────────────────────────────────────────┘│
│ [Browse]  Current size: 245 MB               │
│                                              │
│ Snapshots Directory:                         │
│ ┌──────────────────────────────────────────┐│
│ │ /...opencv_surveillance/data/snapshots   ││
│ └──────────────────────────────────────────┘│
│ [Browse]  Current size: 1.2 GB               │
│                                              │
│ ☑ Migrate existing files to new locations  │
│                                              │
│ [Save Changes]  [Reset to Defaults]         │
└─────────────────────────────────────────────┘
```

### Migration Dialog

```
┌─────────────────────────────────────────────┐
│ Migrate Storage Paths?                       │
├─────────────────────────────────────────────┤
│                                              │
│ This will move files to the new locations:  │
│                                              │
│ Recordings:                                  │
│ FROM: /old/path/recordings                   │
│ TO:   /new/path/recordings                   │
│ Files: 37 items (245 MB)                     │
│                                              │
│ Snapshots:                                   │
│ FROM: /old/path/snapshots                    │
│ TO:   /new/path/snapshots                    │
│ Files: 211 items (1.2 GB)                    │
│                                              │
│ ⚠ This operation may take several minutes   │
│                                              │
│ [Cancel]  [Start Migration]                 │
└─────────────────────────────────────────────┘
```

---

## 🔍 Testing Plan

### Manual Testing

1. **Default Paths Test**
   ```bash
   # Start server normally
   ./start-local.sh

   # Verify paths in logs
   # Expected: All paths point to opencv_surveillance/
   ```

2. **Custom Paths Test**
   ```bash
   # Set environment variables
   export OPENEYE_RECORDINGS_DIR="/custom/recordings"
   export OPENEYE_SNAPSHOTS_DIR="/custom/snapshots"

   # Start server
   ./start-local.sh

   # Verify new directories are created
   ls -la /custom/recordings
   ls -la /custom/snapshots
   ```

3. **Migration Test**
   ```bash
   # Create test files
   mkdir -p /tmp/test_recordings
   touch /tmp/test_recordings/test.mp4

   # Update paths via API with migrate=true
   curl -X PUT http://localhost:8000/api/settings/paths \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"recordings_path": "/tmp/new_recordings", "migrate": true}'

   # Verify files moved
   ls -la /tmp/new_recordings/test.mp4
   ```

4. **Database Cleanup Test**
   ```bash
   python -m backend.utils.cleanup_orphaned_records --dry-run
   # Expected: Shows 4 orphaned records

   python -m backend.utils.cleanup_orphaned_records --confirm
   # Expected: Removes 4 orphaned records
   ```

---

## 📚 Documentation Updates

### Environment Variables

Add to README.md:

```markdown
## Storage Configuration

By default, OpenEye stores media in `opencv_surveillance/`:
- Recordings: `opencv_surveillance/recordings/`
- Snapshots: `opencv_surveillance/data/snapshots/`
- Faces: `opencv_surveillance/data/faces/`

To customize storage locations, set environment variables:

\`\`\`bash
export OPENEYE_RECORDINGS_DIR="/mnt/storage/recordings"
export OPENEYE_SNAPSHOTS_DIR="/mnt/storage/snapshots"
export OPENEYE_FACES_DIR="/mnt/storage/faces"
\`\`\`

Or update via the Settings page in the UI.
```

---

## 🎯 Summary

### What's Broken
1. ❌ Multiple empty directories causing confusion
2. ❌ Hardcoded relative paths in main.py
3. ❌ 4 orphaned database records
4. ❌ No way for users to configure storage paths
5. ❌ No file migration tool

### What Will Be Fixed
1. ✅ Centralized path management (`PathManager`)
2. ✅ Environment variable support
3. ✅ Settings API for path configuration
4. ✅ File migration utility
5. ✅ Database cleanup tool
6. ✅ Frontend UI for path management

### Next Steps
1. Create `PathManager` class
2. Update backend to use `PathManager`
3. Create migration utilities
4. Update settings API
5. Update frontend
6. Test thoroughly
7. Document for users

---

**Implementation By:** Development Team
**Date:** October 18, 2025
**Status:** 📋 Planning Complete - Ready for Implementation

---

**End of Document**
