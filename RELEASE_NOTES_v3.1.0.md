# OpenEye v3.1.0 Release Notes

## 🎉 Major Release: Camera Discovery & Theme System

**Release Date:** October 7, 2025  
**Version:** 3.1.0  
**Status:** Production Ready

---

## 🆕 What's New

### 1. Automatic Camera Discovery 🔍

Say goodbye to manual RTSP URL configuration! OpenEye now automatically discovers cameras on your network and USB devices.

**Features:**
- **USB Camera Detection**: Scans indices 0-10, detects built-in and external webcams
- **Network RTSP Scanning**: Discovers IP cameras on local subnets (30-60 seconds)
- **Pre-Add Testing**: Validate camera connections before adding to database
- **Auto-Configuration**: Automatically generates camera configs with resolution/FPS
- **One-Click Addition**: Quick-add discovered cameras with a single click

**Supported Cameras:**
- ✅ Any USB webcam or built-in camera
- ✅ RTSP/IP cameras (Hikvision, Dahua, Amcrest, Reolink, etc.)
- ✅ ONVIF-compatible devices
- ❌ Proprietary cloud cameras (Nest, Ring, Arlo, Wyze without RTSP firmware)

### 2. Camera Management Interface 📹

Complete UI for managing your surveillance cameras without touching the API.

**Three-Tab Interface:**
- **List Tab**: View, enable/disable, and delete cameras
- **Discovery Tab**: Automatic camera detection
- **Manual Tab**: Custom camera configuration with form

**Features:**
- Camera list with status indicators
- Live stream viewing
- Enable/disable toggle
- Delete cameras with confirmation
- Common RTSP URL templates for major brands
- Form validation and error handling

### 3. Superhero Theme System 🎨

Transform your surveillance dashboard with 8 unique superhero-inspired themes!

 

**Theme Features:**
- Custom color palettes for each theme
- Unique typography (Arial Black, Impact, Georgia, Roboto Mono, Orbitron)
- Animated overlays (bat-signal, speed lines, water effects, etc.)
- Theme-specific button styles
- Persistent theme selection (saved in localStorage)
- Live theme preview

### 4. Updated Documentation 📚

- Docker Hub overview updated for v3.1.0
- Added camera discovery usage guide
- Web dashboard documentation
- Theme system documentation

---

## 📊 Statistics

- **Files Created/Modified**: 11
- **Lines of Code Added**: 3000+
- **New API Endpoints**: 6
- **New React Components**: 4
- **New Themes**: 8
- **Backend Services**: 1 (CameraDiscovery)

---

## 🚀 Upgrade Guide

### From v3.0.0 to v3.1.0:

1. **Pull the latest image:**
   ```bash
   docker pull im1k31s/openeye-opencv_home_security:v3.1.0
   ```

2. **Update your docker-compose.yml** (if applicable):
   ```yaml
   services:
     openeye:
       image: im1k31s/openeye-opencv_home_security:v3.1.0
       # ... rest of configuration
   ```

3. **Restart the container:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. **Access new features:**
   - Camera Management: `http://localhost:8000/camera-management`
   - Theme Selector: `http://localhost:8000/theme-selector`
   - Dashboard: `http://localhost:8000/`

---

## 💡 Usage Examples

### Automatic Camera Discovery

1. Navigate to the dashboard
2. Click "📹 Cameras" button
3. Click "Discovery" tab
4. Choose USB or Network scanning
5. Review discovered devices
6. Click "Quick Add" to add camera

### Manual Camera Configuration

1. Navigate to Camera Management
2. Click "Manual" tab
3. Fill in the form:
   ```
   Camera ID: front_door_cam
   Name: Front Door
   Type: RTSP
   Source: rtsp://admin:password@192.168.1.100:554/stream
   Resolution: 1920x1080
   FPS: 30
   ✓ Enable camera
   ✓ Record on motion
   ```
4. Click "Add Camera"

### Change Theme

1. Navigate to dashboard
2. Click "🎨 Themes" button
3. Browse theme gallery
4. Click on a theme card to preview
5. Click "Apply Theme"
6. Theme automatically saves

---

## 🔧 API Changes

### New Endpoints

```
POST   /api/cameras/discover/usb         - Discover USB cameras
POST   /api/cameras/discover/network     - Start network scan
GET    /api/cameras/discover/status      - Check scan progress
POST   /api/cameras/discover/test        - Test camera connection
POST   /api/cameras/quick-add            - Quick-add discovered camera
GET    /api/cameras/discover/help        - Discovery documentation
```

### New Dependencies

```
netifaces>=0.11.0  # Network interface discovery
```

---

## 🐛 Known Issues

1. Network scanning duration depends on subnet size (30-60 seconds typical)
2. Only common RTSP ports tested (554, 8554, 8080, 88)
3. Manual credential entry required for authenticated cameras
4. ONVIF auto-discovery not yet implemented (planned for v3.2)

---

## 🗺️ Roadmap

### v3.2 (Next Release)
- ONVIF device discovery
- mDNS/Bonjour camera detection
- Saved credential profiles
- Custom port range configuration
- Batch camera addition

### v3.3
- Camera thumbnails in discovery results
- PTZ camera detection and control
- Audio stream detection
- Camera grouping

---

## 🤝 Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md).

**Areas for contribution:**
- Additional themes
- Camera brand-specific RTSP URL patterns
- ONVIF discovery implementation
- Unit tests for discovery service
- Documentation improvements

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

---

## 🙏 Acknowledgments

- OpenCV for computer vision capabilities
- FastAPI for the robust backend framework
- React for the frontend framework
- Docker community for containerization support
- All contributors and testers

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues)
- **Discussions:** [GitHub Discussions](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/discussions)
- **Documentation:** [Wiki](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/wiki)

---

## ⭐ Star the Project

If you find OpenEye useful, please give it a star on [GitHub](https://github.com/M1K31/OpenEye-OpenCV_Home_Security)!

---

**Built with ❤️ by the open-source community**
