# OpenEye v3.5.6 Release Notes
**Release Date**: October 19, 2025
**Version**: 3.5.6

## 🎯 Major Features

### Timeline Playback System
- **Interactive Timeline**: Scrollable ruler-style timeline with drag-to-scroll
- **Event Icons**: Visual event markers on timeline axis with color coding
- **Media Viewer**: Persistent video/snapshot viewer below playback controls
- **Playback Controls**: Play, Previous, Next, Live buttons with speed control (0.5x - 8x)
- **Time Intervals**: 5min, 15min, 30min, 1hr viewing intervals
- **Time Formats**: 12hr/24hr toggle support
- **Auto-play**: Videos and snapshots display automatically during playback
- **Apple HIG Compliance**: Clean, hierarchical UI following Apple Human Interface Guidelines

### UI/UX Improvements
- **Segmented Button Controls**: Professional button groups for settings
- **Enhanced Media Info**: Detailed event information grid below media viewer
- **Improved Layout**: Clean separation of header, timeline, controls, viewer, and events
- **Event Details**: Display camera, person, duration, faces detected below videos
- **Responsive Sizing**: Media viewer properly contains videos/images with aspect ratio preservation

## 🐛 Bug Fixes

### Snapshot Path Normalization (v3.5.6)
- **Issue**: Timeline and motion events returning paths with `data/snapshots/` prefix causing 404 errors
- **Fix**: Added Pydantic field validators to normalize snapshot paths
- **Files Modified**:
  - `backend/api/schemas/motion.py` - Added `normalize_snapshot_path` validator
  - `backend/api/routes/timeline.py` - Added `normalize_thumbnail_path` validator
- **Result**: All snapshot APIs now return just filenames

### Snapshot Endpoint Addition (v3.5.6)
- **Issue**: Frontend requesting `/api/snapshots/` but endpoint didn't exist
- **Fix**: Added static file mount at `/api/snapshots/`
- **Files Modified**:
  - `backend/main.py` - Added `/api/snapshots/` mount point
- **Backwards Compatibility**: Kept `/data/snapshots/` and `/legacy/snapshots/` for older code

### Recording ID Field Mapping (v3.5.6)
- **Issue**: Frontend using `recording.id` instead of `recording.recording_id`
- **Fix**: Updated frontend to use correct field from API response
- **Files Modified**:
  - `frontend/src/sections/LiveDashboard.jsx` - Added `recording_id` mapping
  - `frontend/src/pages/RecordingsPage.jsx` - Fixed `recording_id` usage

### Browser Cache Issues (v3.5.6)
- **Issue**: Users seeing old JavaScript builds after updates
- **Documentation**: Added clear hard-refresh instructions for all major browsers
- **Build Hash**: New build `index-e4c0c3c1.js`

## 📁 Files Modified

### Backend
1. `backend/api/schemas/motion.py` - Snapshot path validator
2. `backend/api/routes/timeline.py` - Timeline event response schema and validator
3. `backend/main.py` - Version update to 3.5.6, added `/api/snapshots/` endpoint

### Frontend
1. `frontend/src/pages/TimelineView.jsx` - Complete Timeline Playback implementation
2. `frontend/src/pages/TimelineView.css` - HIG-compliant styling (767 lines)
3. `frontend/src/sections/LiveDashboard.jsx` - Recording ID mapping
4. `frontend/src/pages/RecordingsPage.jsx` - Recording ID field fixes

### Configuration
1. `opencv_surveillance/.gitignore` - Added snapshots/, webm, mov, gif, bmp, database.pkl
2. `README.md` - Updated version badge to 3.5.6

### Documentation
- Moved 24 session documentation files to `docs/archived-releases/`
- No developer-specific paths in main documentation
- All installation instructions verified and up-to-date

## 🚀 Deployment

### Docker Build
```bash
cd opencv_surveillance

# Build with version tag and latest
docker build -t im1k31s/openeye-opencv_home_security:v3.5.6 \
             -t im1k31s/openeye-opencv_home_security:latest \
             -f Dockerfile .

# Push to Docker Hub
docker push im1k31s/openeye-opencv_home_security:v3.5.6
docker push im1k31s/openeye-opencv_home_security:latest
```

### Git Commit and Push
```bash
# Verify changes
git status

# Add all changes
git add -A

# Commit
git commit -m "Release v3.5.6: Timeline Playback + UI improvements

- Added interactive Timeline Playback with scrollable ruler
- Event icons on timeline axis with Apple HIG styling
- Persistent media viewer with enhanced event details
- Fixed snapshot path normalization (404 errors)
- Added /api/snapshots/ endpoint
- Fixed recording ID field mapping
- Updated .gitignore for media files
- Organized session documentation
- Version bumped to 3.5.6"

# Push to GitHub
git push origin main

# Create release tag
git tag -a v3.5.6 -m "Version 3.5.6 - Timeline Playback System"
git push origin v3.5.6
```

## 📦 Installation

### Docker (Recommended)
```bash
docker pull im1k31s/openeye-opencv_home_security:v3.5.6

docker run -d \
  --name openeye \
  -p 8000:8000 \
  -v ./data:/app/data \
  -v ./recordings:/app/recordings \
  -v ./faces:/app/faces \
  -e SECRET_KEY=your_secret_key \
  -e JWT_SECRET_KEY=your_jwt_secret \
  im1k31s/openeye-opencv_home_security:v3.5.6
```

### Local Installation
```bash
git clone https://github.com/M1K31/OpenEye-OpenCV_Home_Security.git
cd OpenEye-OpenCV_Home_Security/opencv_surveillance
./scripts/install-local.sh
./start.sh
```

## 🔍 Verification Checklist

After deployment, verify:

### Timeline Playback
- [ ] Timeline page loads without errors
- [ ] Event icons visible on timeline axis
- [ ] Click event icon shows media in viewer below
- [ ] Previous/Next buttons navigate between events
- [ ] Play button auto-plays videos/snapshots
- [ ] Speed selector works (0.5x, 1x, 2x, 4x, 8x)
- [ ] Interval selector works (5m, 15m, 30m, 1h)
- [ ] Time format toggle works (12hr/24hr)
- [ ] Drag-to-scroll timeline works smoothly

### Media Display
- [ ] Snapshots load without 404 errors in browser console
- [ ] Videos play correctly
- [ ] Event details display below media (camera, person, etc.)
- [ ] Media viewer sizing correct (no overflow)

### API Endpoints
- [ ] `/api/motion-events/` returns normalized snapshot paths (just filename)
- [ ] `/api/timeline/events` returns normalized thumbnail paths
- [ ] `/api/snapshots/{filename}` serves images (200 OK)
- [ ] `/api/recordings/{id}/download` works with correct ID field

### Browser Compatibility
- [ ] Hard refresh clears cache (`⌘+Shift+R` / `Ctrl+Shift+R`)
- [ ] New build hash loads: `index-e4c0c3c1.js`
- [ ] No JavaScript errors in console

## 🎨 UI/UX Highlights

### Apple Human Interface Guidelines Compliance
- **Segmented Controls**: Connected button groups for settings
- **Visual Hierarchy**: Clear separation of sections
- **Consistent Spacing**: 8pt grid system
- **Typography**: Uppercase labels, proper font weights
- **Interaction States**: Hover, active, selected states
- **Responsive Layout**: Adapts to different screen sizes

### Timeline Design
- **Event Icons**: 32px circular icons with event type emoji
- **Color Coding**: Motion (blue), Face (green), Person (purple)
- **Selected State**: Blue border with glow effect
- **Hover Effect**: Scale 1.2x with shadow
- **Drag Cursor**: Grab cursor during timeline drag

## 📊 Technical Details

### API Response Format (v3.5.6)
```json
{
  "events": [
    {
      "id": 248,
      "camera_id": "usb_camera_0",
      "event_type": "motion",
      "timestamp": "2025-10-19T15:41:58.198849",
      "snapshot_path": "motion_usb_camera_0_20251019_114158_198849.jpg",
      "recording_id": 94,
      "faces_detected": 0
    }
  ]
}
```

**Key Points**:
- `snapshot_path` is just filename (no directory prefix)
- `recording_id` links to recordings table (may be null)

### Frontend Build
- **Build Hash**: `index-e4c0c3c1.js` (409.08 kB)
- **CSS Hash**: `index-6dee8028.css` (97.57 kB)
- **Vite Version**: 4.5.14
- **Bundle Size**: 409 KB (gzipped: 120 KB)

## 🔐 Security & Privacy

- ✅ All media files excluded from git (.gitignore)
- ✅ No developer-specific paths in documentation
- ✅ Database files excluded from Docker image
- ✅ .env files not committed to repository
- ✅ Secure default CORS configuration
- ✅ JWT token authentication
- ✅ Non-root Docker user (openeye)

## 🐳 Docker Image Details

### Multi-stage Build
1. **Frontend Builder** (node:18-alpine): Builds React app
2. **Python Builder** (python:3.11-slim): Compiles dependencies
3. **Runtime** (python:3.11-slim): Minimal production image

### Image Size
- **Optimized**: Multi-stage build reduces final image size
- **Dependencies**: Only runtime libraries included
- **User**: Runs as non-root user `openeye` (UID 1000)

### Health Check
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1
```

## 📝 Migration Notes

### From v3.5.5 to v3.5.6

#### Database
- **No schema changes** - Fully backward compatible
- **No migration required**

#### Configuration
- **No new environment variables**
- **No breaking changes**

#### API
- **Snapshot paths** now normalized (just filename)
- **Backwards compatible** - Old endpoints still work:
  - `/data/snapshots/{filename}` ✅
  - `/legacy/snapshots/{filename}` ✅
  - `/api/snapshots/{filename}` ✅ **NEW - Recommended**

#### Frontend
- **Hard refresh required** to load new build
- **No localStorage changes**
- **No breaking UI changes**

## 🎯 Next Steps (Future Releases)

### v3.6.0 (Planned)
- Face clustering for unknown faces
- Advanced analytics dashboard
- Export timeline data to video
- Multi-camera synchronization

### v3.7.0 (Planned)
- Mobile app (React Native)
- Cloud backup integration
- AI-powered event categorization
- Advanced search and filtering

## 📞 Support

### Documentation
- **README**: Installation and quick start
- **API Docs**: http://localhost:8000/api/docs
- **User Guide**: `docs/USER_GUIDE.md`
- **Docker Guide**: `docs/DOCKER_INSTALLATION.md`

### Issues
- **GitHub Issues**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues
- **Docker Hub**: https://hub.docker.com/r/im1k31s/openeye-opencv_home_security

## 🙏 Acknowledgments

- **OpenCV**: Computer vision library
- **dlib**: Face recognition
- **FastAPI**: Backend framework
- **React**: Frontend framework
- **Vite**: Build tool
- **Apple HIG**: Design guidelines

---

**Full Changelog**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/compare/v3.5.5...v3.5.6
