# OpenEye v3.5.2 - Quick Testing Guide

## ✅ All Tasks Complete

1. ✅ Database Migration (recording_id + last_active_at)
2. ✅ Wrapped API Responses with Metadata
3. ✅ Removed Duplicate Login Endpoint
4. ✅ Updated Frontend for Wrapped Responses

**Build:** `index-211a1e2f.js` (226.46 kB)

---

## Start Testing

### 1. Start Server
```bash
cd /Volumes/Storage/Dev/GitHubProjects/OpenEye-OpenCV_Home_Security
./start-local.sh
```

### 2. Open Browser
Navigate to: **http://localhost:8000**

### 3. Test Pages
- ✅ Login Page
- ✅ Dashboard (camera feeds + timeline)
- ✅ Recordings (list + playback)
- ✅ Face Management (people list)
- ✅ Alert Settings (notification logs)
- ✅ Camera Discovery

### 4. Check Console
- No 401 errors before login ✓
- No errors after login ✓
- API responses wrapped with metadata ✓

---

## API Response Examples

### Old (Legacy Array)
```json
[
  {"id": 1, "camera_id": "cam1"},
  {"id": 2, "camera_id": "cam2"}
]
```

### New (Wrapped with Metadata)
```json
{
  "recordings": [
    {"id": 1, "camera_id": "cam1"},
    {"id": 2, "camera_id": "cam2"}
  ],
  "total": 150,
  "filtered": 2
}
```

**Backward Compatible:** Frontend handles both formats!

---

## Test API Directly

```bash
# 1. Recordings
curl http://localhost:8000/api/recordings/ | jq .total

# 2. Face Detections
curl http://localhost:8000/api/history/detections | jq .total

# 3. People (requires auth)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/faces/people | jq .total

# 4. Alert Logs (requires auth)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/alerts/logs | jq .total
```

---

## Database Migration

**Already Applied:** ✅

Verify with:
```bash
cd opencv-surveillance
source venv/bin/activate
python scripts/migrate_database_v3.5.2.py
```

Should show:
- ✅ recording_id column exists
- ✅ last_active_at column exists
- ✅ recording_id is indexed

---

## Files Changed

**Backend (7 files):**
- models.py
- recordings.py
- face_history.py
- faces.py
- alerts.py
- users.py
- face.py (schemas)

**Frontend (4 files):**
- LiveDashboard.jsx
- RecordingsPage.jsx
- FaceManagementPage.jsx
- AlertSettingsPage.jsx

---

## Key Features

1. **Event → Recording Navigation**
   - Click timeline events to view recordings
   - Enabled by recording_id FK

2. **API Metadata**
   - Show "X of Y" records
   - Pagination-ready

3. **Single Auth Endpoint**
   - `/api/token` (OAuth2 standard)
   - Removed duplicate `/api/users/login`

4. **Backward Compatible**
   - No breaking changes
   - Safe to deploy anytime

---

## Troubleshooting

**Server won't start:**
```bash
lsof -ti:8000 | xargs kill -9
./start-local.sh
```

**Migration failed:**
```bash
# Check database
sqlite3 surveillance.db ".schema face_detection_events"
sqlite3 surveillance.db ".schema cameras"
```

**Frontend errors:**
```bash
cd opencv-surveillance/frontend
npm run build
```

---

## Success Criteria

- [ ] Server starts without errors
- [ ] Login works
- [ ] Dashboard shows camera feeds
- [ ] Timeline events clickable
- [ ] Recordings page loads
- [ ] Face management lists people
- [ ] Alert logs display
- [ ] No console errors
- [ ] API responses have metadata

---

## Need More Info?

See: `IMPLEMENTATION_SUMMARY_v3.5.2.md` for complete details.

---

**Status:** Ready for Testing! 🚀
