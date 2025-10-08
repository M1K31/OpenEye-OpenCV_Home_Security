# OpenEye Surveillance System

![Version](https://img.shields.io/badge/version-3.2.8-blue.svg)
![Python](https://img.shields.io/badge/python-3.11-green.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-red.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Free](https://img.shields.io/badge/cost-$0/month-success.svg)

**100% free and open-source surveillance system** powered by OpenCV with AI face recognition, motion detection, and smart home integration.

## 🚀 Quick Start

```bash
docker pull im1k31s/openeye-opencv_home_security:latest
docker run -d --name openeye -p 8000:8000 -v ~/openeye-data:/app/data im1k31s/openeye-opencv_home_security:latest
```

Access the web interface at `http://localhost:8000`

Default credentials: `admin` / `admin` (change immediately!)

## ✨ Features

- ✅ **Multi-Camera Support** - RTSP streams, IP cameras, USB webcams
- ✅ **AI Face Recognition** - Identify known people automatically
- ✅ **Motion Detection** - OpenCV-based motion tracking
- ✅ **Automatic Recording** - Motion-triggered video capture
- ✅ **Live Streaming** - Real-time MJPEG streams
- ✅ **Smart Alerts** - Email, SMS, Push notifications
- ✅ **Smart Home Integration** - Home Assistant, HomeKit, Google Nest
- ✅ **Cloud Storage** - AWS S3, Google Cloud, Azure, MinIO
- ✅ **Modern UI** - React-based responsive interface with dark theme
- ✅ **No Subscriptions** - $0/month forever!

## 📦 What's New in v3.2.8

### UI/UX Improvements
- 🎨 Complete dark theme implementation (#262626 background, #ffffff text)
- 🔧 Fixed AlertSettingsPage CSS corruption
- ⚙️ Consolidated settings into tabbed interface
- 🎯 Improved text readability across all pages
- ⏳ Added loading spinner for face model training
- 🐛 Fixed JavaScript errors and null reference crashes

### Documentation
- 📚 Comprehensive macOS USB camera limitations guide
- 🔌 4 documented workarounds for USB cameras on macOS
- 💡 Recommended solutions for production use

## 🖥️ System Requirements

- **CPU**: 2+ cores recommended (4+ for multiple cameras)
- **RAM**: 2GB minimum, 4GB+ recommended
- **Storage**: 10GB+ for recordings
- **OS**: Linux, macOS, Windows (Docker Desktop)
- **Network**: For IP cameras and remote access

## ⚠️ Important: USB Camera Limitations on macOS

**USB cameras have limitations when running in Docker on macOS** due to Docker Desktop's VM architecture. The VM doesn't have direct access to USB devices.

### Recommended Solutions:

**Option 1: Use Network/IP Cameras (Recommended)**
- Works perfectly across all platforms
- Better for multi-camera setups
- Examples: Wyze Cam v3, Reolink cameras

**Option 2: Run Backend Natively on macOS**
```bash
cd opencv-surveillance/backend
python3 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Option 3: USB/IP Forwarding (Experimental)**
Recent Docker Desktop versions support experimental USB/IP forwarding:
```bash
docker run --rm -it --privileged --pid=host alpine
nsenter -t 1 -m
usbip list -r host.docker.internal
usbip attach -r host.docker.internal -d <BUSID>
```

**Option 4: Use Linux**
- Native USB passthrough support
- Raspberry Pi or similar Linux device
- Best for production deployments

**For production use with macOS**, we strongly recommend network/IP cameras for reliability and scalability.

## 🔧 Configuration

### Environment Variables

```bash
# Security
SECRET_KEY=your-super-secret-key-change-this

# Database
DATABASE_URL=sqlite:///./surveillance.db

# SMTP Email Alerts (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=openeye@yourdomain.com

# Twilio SMS (optional)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1234567890

# Firebase Push Notifications (optional)
FIREBASE_CREDENTIALS=/path/to/firebase-credentials.json
```

### Volume Mounts

```bash
docker run -d \
  --name openeye \
  -p 8000:8000 \
  -v ~/openeye-data:/app/data \
  -e SECRET_KEY=your-secret-key \
  im1k31s/openeye-opencv_home_security:latest
```

## 🏗️ Architecture

- **Backend**: FastAPI + Python 3.11
- **Frontend**: React 18 + Vite
- **Computer Vision**: OpenCV 4.8+
- **Face Recognition**: dlib with ResNet model
- **Database**: SQLite (default) or PostgreSQL
- **Streaming**: MJPEG for live feeds

## 📊 Camera Support

### Network/IP Cameras
✅ **ONVIF Protocol** - Auto-discovery
✅ **RTSP Streams** - Universal support
✅ **HTTP/MJPEG** - Webcam servers

### USB Cameras
⚠️ **Linux**: Full support
⚠️ **macOS**: Requires native backend or USB/IP (see limitations above)
⚠️ **Windows**: Experimental support via Docker Desktop

### Tested Cameras
- Wyze Cam v3
- Reolink cameras
- Hikvision
- Dahua
- Generic ONVIF cameras

## 🔐 Security Features

- ✅ Password hashing with bcrypt
- ✅ JWT-based authentication
- ✅ Role-based access control (Admin, User, Viewer)
- ✅ Rate limiting for API endpoints
- ✅ SQL injection protection
- ✅ CORS configuration
- ✅ Secure session management

## 📱 Smart Home Integration

### Home Assistant
```yaml
camera:
  - platform: mjpeg
    mjpeg_url: http://openeye:8000/api/cameras/1/stream
```

### HomeKit
Automatic bridge configuration via python-homekit

### Google Nest
OAuth2 integration for Nest devices

## 💾 Storage Options

- **Local Storage**: Default file system storage
- **MinIO**: Self-hosted S3-compatible (FREE!)
- **AWS S3**: Cloud storage with lifecycle policies
- **Google Cloud Storage**: GCS integration
- **Azure Blob Storage**: Azure cloud support

## 🔗 Links

- **GitHub**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security
- **Documentation**: [README.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/README.md)
- **Issues**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues
- **Changelog**: [CHANGELOG](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/opencv-surveillance/CHANGELOG_v3.2.0.md)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Credits

Built with:
- OpenCV for computer vision
- dlib for face recognition
- FastAPI for backend API
- React for frontend UI
- Docker for containerization

---

**Made with ❤️ by the OpenEye community**

*This is a hobby project focused on privacy, security, and learning. No data leaves your network unless you explicitly configure cloud features.*
