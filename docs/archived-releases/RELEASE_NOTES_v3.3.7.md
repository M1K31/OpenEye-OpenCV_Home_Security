# OpenEye v3.3.7 Release Notes

**Release Date:** October 10, 2025  
**Type:** Patch Release - Bug Fixes & Enhancements

## 🎯 Overview

Version 3.3.7 resolves critical UI/UX issues that prevented face recognition photo uploads and adds password visibility controls for improved user experience.

---

## ✨ New Features

### Password Visibility Toggle
- **First-Run Setup:** Added show/hide password buttons for both password fields
- **Login Page:** Added show/hide password button
- **Icons:** Eye emoji (👁️) to show password, Hide emoji (🙈) to hide password
- **UX:** Improves accessibility and reduces password entry errors

---

## 🐛 Bug Fixes

### Critical Fixes

#### 1. Face Recognition Photo Upload (FIXED)
**Issue:** File upload button was completely invisible in the face management modal  
**Root Cause:** Button used undefined CSS variable `var(--primary-color)`  
**Impact:** Users couldn't upload photos for face recognition training  
**Fix:** Replaced with hardcoded blue color (#007bff) with enhanced styling
- Added file icon emoji 📁
- Bold, larger font
- Hover effects
- Explicit inline styles

**Verification:**
```bash
# Photos now upload successfully
docker exec openeye-v3.3.7 ls -lh /app/faces/asdf/
total 3.3M
-rw-r--r-- 1 openeye openeye 917K Oct 10 03:08 IMG_0181.jpeg
-rw-r--r-- 1 openeye openeye 1.2M Oct 10 03:08 IMG_0228.jpeg
-rw-r--r-- 1 openeye openeye 1.2M Oct 10 03:08 IMG_0234.jpeg

# Model trains successfully
-rw-r--r-- 1 openeye openeye 3.3K Oct 10 03:09 /app/face_encodings.pkl
```

#### 2. Camera Discovery 404 Errors (FIXED)
**Issue:** `/api/cameras/discover/status` returned 404 Not Found  
**Root Cause:** Router registration order - cameras router intercepted discovery routes  
**Impact:** Console spam, camera discovery status polling failed  
**Fix:** Moved discovery router registration BEFORE cameras router in `main.py`

**Verification:**
```bash
curl http://localhost:8000/api/cameras/discover/status
{"scanning":false,"cameras_found":0,"cameras":[]}  # ✅ Works!
```

### Minor Fixes

#### 3. Alert Configuration Data Validation
**Issue:** 422 errors when saving alert config with empty email fields  
**Root Cause:** Frontend sending empty strings `""` instead of `null`  
**Fix:** Clean empty strings to `null` before API submission

#### 4. Content Security Policy (CSP)
**Issue:** Inline SVG images blocked by restrictive CSP  
**Fix:** Updated CSP to allow `data:` URIs for images
```
default-src 'self';
img-src 'self' data:;
style-src 'self' 'unsafe-inline';
script-src 'self'
```

---

## 🔧 Technical Improvements

### Frontend Enhancements
- **Axios Interceptor:** Reads JWT token from localStorage on every request
- **Enhanced Logging:** Detailed console logs for debugging upload and modal issues
- **Modal Styling:** Explicit inline styles to prevent CSS conflicts
- **File Input UX:** Hidden native file input, custom styled label button

### Backend Enhancements
- **Router Order:** Discovery routes registered before parameterized camera routes
- **Middleware:** Updated CSP headers for better compatibility

---

## 📊 Testing & Verification

### Tests Performed
- ✅ Password visibility toggle (First-Run Setup)
- ✅ Password visibility toggle (Login Page)
- ✅ Face photo upload (3 photos, 3.3MB total)
- ✅ Face recognition training (57.8 seconds, 3 encodings)
- ✅ Camera discovery status endpoint
- ✅ Alert configuration save
- ✅ Authentication across all API endpoints

### Logs Validation
```
2025-10-10 03:08:05 - Uploaded photo: IMG_0181.jpeg for asdf
2025-10-10 03:08:05 - Uploaded photo: IMG_0234.jpeg for asdf
2025-10-10 03:08:05 - Uploaded photo: IMG_0228.jpeg for asdf
2025-10-10 03:08:07 - Starting face recognition training...
2025-10-10 03:09:05 - Training complete: total_people: 1, total_encodings: 3
```

---

## 📝 Migration Notes

### Upgrading from v3.3.0 - v3.3.6

**No database migrations required.** Simply pull the new Docker image:

```bash
# Stop current container
docker stop openeye-v3.3.6
docker rm openeye-v3.3.6

# Pull and run new version
docker pull im1k31s/openeye-opencv_home_security:v3.3.7
docker run -d --name openeye-v3.3.7 \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  im1k31s/openeye-opencv_home_security:v3.3.7
```

**Important:** Hard refresh your browser (Cmd+Shift+R / Ctrl+Shift+R) to load the new JavaScript bundle.

---

## 🔄 Version History

| Version | Date | Critical Fixes |
|---------|------|----------------|
| v3.3.7 | Oct 10, 2025 | ✅ File upload button visibility, Camera discovery 404 |
| v3.3.6 | Oct 9, 2025 | Router order fix, Enhanced modal debugging |
| v3.3.5 | Oct 9, 2025 | CSP update for data URIs |
| v3.3.4 | Oct 9, 2025 | Enhanced debugging logs |
| v3.3.3 | Oct 9, 2025 | ✅ Axios interceptor (401 auth errors) |
| v3.3.0 | Oct 8, 2025 | Dashboard theme fixes |

---

## 🐛 Known Issues

### Non-Critical
1. **SMTP/SMS/Push Config:** Currently requires environment variables. UI configuration coming in v3.4.0.
2. **Hardcoded Colors:** Some pages still have hardcoded colors (low priority).

### Workarounds
- **Notification Config:** Set environment variables in docker-compose.yml:
  ```yaml
  environment:
    - SMTP_HOST=smtp.gmail.com
    - SMTP_PORT=587
    - SMTP_USERNAME=your-email@gmail.com
    - SMTP_PASSWORD=your-app-password
  ```

---

## 📚 Documentation

### New Documentation
- **API Documentation:** Comprehensive API reference added at `/docs/API_DOCUMENTATION.md`
- **Examples:** Python and JavaScript integration examples
- **Webhook Guide:** Real-time event handling examples

### Updated Documentation
- README.md - Updated feature list and quick start
- DOCKER_HUB_OVERVIEW.md - Updated with v3.3.7 info
- CHANGELOG.md - Added v3.3.7 entry

---

## 🎉 Success Story

A user reported complete inability to use face recognition due to the invisible upload button. Through systematic debugging:

1. **Identified:** Modal rendering but button invisible
2. **Root Cause:** Undefined CSS variable `--primary-color`
3. **Fixed:** Hardcoded color with enhanced styling
4. **Verified:** User successfully uploaded 3 photos and trained model

**Result:** Face recognition fully operational! 🚀

---

## 🔮 What's Next (v3.4.0)

Planned features for the next release:

1. **Notification Settings UI**
   - Configure SMTP/SMS/Push in web interface
   - Test connections before saving
   - Secure credential storage

2. **Advanced Analytics Dashboard**
   - Detection heatmaps
   - Activity timelines
   - Export reports

3. **Mobile App**
   - iOS and Android apps
   - Push notifications
   - Live camera viewing

---

## 🙏 Credits

**Contributors:**
- Mikel Smart (@M1K31) - Core development

**Special Thanks:**
- Community testers who reported the file upload issue
- Everyone who provided detailed bug reports and logs

---

## 📞 Support

- **GitHub Issues:** https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues
- **Documentation:** `/docs` folder
- **Docker Hub:** https://hub.docker.com/r/im1k31s/openeye-opencv_home_security

---

**OpenEye** - Open Source Home Security with AI Face Recognition  
**License:** MIT  
**Copyright © 2025 Mikel Smart**
