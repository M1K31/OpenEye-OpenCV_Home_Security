# OpenEye Quick Reference Card
## Version 3.4.1 - October 11, 2025

---

## 🚀 Quick Start

```bash
# Start Server
cd /path/to/OpenEye-OpenCV_Home_Security
./start-local.sh

# Stop Server
lsof -ti:8000 | xargs kill -9

# View Logs
tail -f server.log

# Run Tests
./test_application.sh
```

---

## 🔗 Access Points

| Service | URL | Status |
|---------|-----|--------|
| **Web App** | http://localhost:8000 | ✅ |
| **API Docs** | http://localhost:8000/api/docs | ✅ |
| **Health** | http://localhost:8000/api/health | ✅ |
| **Camera Stream** | http://localhost:8000/api/cameras/usb_camera_0/stream | ✅ |

---

## 🔑 Test Credentials

```
Username: testuser
Password: testpass123
Email: test@openeye.local
```

---

## 📊 System Status

```bash
# Quick Health Check
curl http://localhost:8000/api/health

# Get Token
curl -X POST "http://localhost:8000/api/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass123"

# List Cameras (with token)
curl "http://localhost:8000/api/cameras/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## ✅ Current Status

- **Server**: Running on port 8000
- **Camera**: USB camera active (index 0)
- **Face Recognition**: 5 encodings loaded
- **Motion Detection**: Active
- **Video Recording**: ✅ **WORKING** (H.264)
- **Resolution**: 1920x1080 @ 15fps
- **Storage**: recordings/ directory

---

## 🎯 What's Working

✅ API endpoints  
✅ Authentication  
✅ Camera streaming  
✅ Face detection  
✅ Motion detection  
✅ **Video recording** (FIXED!)  
✅ WebSocket updates  
✅ Security middleware  

---

## 📁 Important Locations

```
Project Root: /path/to/OpenEye-OpenCV_Home_Security/
Application: opencv-surveillance/
Database: opencv-surveillance/surveillance.db
Recordings: opencv-surveillance/recordings/
Faces: opencv-surveillance/faces/
Logs: server.log
```

---

## 🔧 Troubleshooting

**Server won't start?**
```bash
lsof -ti:8000 | xargs kill -9  # Kill existing process
./start-local.sh               # Restart
```

**No recordings?**
```bash
ls -lh opencv-surveillance/recordings/
tail -f server.log | grep recording
```

**Camera not working?**
```bash
# Check camera
ls /dev/video*  # Linux
system_profiler SPCameraDataType  # macOS
```

---

## 📞 Quick Help

**View API docs**: http://localhost:8000/api/docs  
**Check logs**: `tail -f server.log`  
**Test API**: `./test_application.sh`  
**View recordings**: `ls -lh opencv-surveillance/recordings/`

---

## 🎉 Version 3.4.1 Changes

**Major Fix**: Video recording now working!
- Implemented codec fallback system
- Uses H.264 (avc1) for macOS
- Files saved as MP4 format
- ~10 MB per minute @ 1080p

---

**Last Updated**: October 11, 2025 at 6:45 PM  
**Status**: ✅ Fully Operational
