# OpenEye Surveillance System

![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-green.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-red.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Free](https://img.shields.io/badge/cost-$0/month-success.svg)

An **100% free and open-source** surveillance system powered by **OpenCV**. This project emphasizes OpenCV's computer vision capabilities combined with deep learning for accurate face recognition, creating a powerful alternative to traditional (and expensive!) surveillance solutions.

## 💰 Completely Free!

- ✅ **No subscriptions** - $0/month forever
- ✅ **No cloud dependencies** - Works offline
- ✅ **No sign-ups required** - All services are optional
- ✅ **Open source** - Inspect and modify all code
- ✅ **Self-hosted** - Your data stays on your hardware

## 🎯 Why OpenEye?

**OpenEye leverages OpenCV's full power** for advanced computer vision tasks:
- ✨ **True OpenCV Implementation** - Direct use of OpenCV's algorithms, not Motion
- 🧠 **AI-Powered Face Recognition** - dlib-based face detection and recognition
- 🎥 **Real-time Processing** - Efficient video stream analysis
- 🏠 **Self-Hosted** - Complete control over your data
- 🚀 **Modern Stack** - FastAPI + React for a responsive experience
- 📊 **Rich Analytics** - Historical face detection tracking and statistics

---

## 📋 Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Development](#development)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## ✨ Features

### Phase 1-2 (Core Features) ✅
- ✅ **Multi-Camera Support** - RTSP streams and mock cameras for testing
- ✅ **Motion Detection** - OpenCV MOG2 background subtraction
- ✅ **Automatic Recording** - Motion-triggered video capture
- ✅ **Live Streaming** - MJPEG streams with real-time overlays
- ✅ **Face Recognition** - Identify known individuals automatically
- ✅ **Face Management** - Easy person management interface
- ✅ **Detection History** - Track all face detections with timestamps
- ✅ **Database Persistence** - SQLite or PostgreSQL storage

### Phase 3 (Notifications) ✅
- ✅ **Email Alerts** - SMTP notifications (FREE with Gmail)
- ✅ **SMS Alerts** - Twilio or Telegram Bot (Telegram is FREE!)
- ✅ **Push Notifications** - Firebase or ntfy.sh (ntfy.sh is FREE!)
- ✅ **Webhooks** - Custom integrations
- ✅ **Alert Throttling** - Prevent notification spam

### Phase 4 (Smart Home) ✅
- ✅ **Home Assistant** - MQTT integration (FREE!)
- ✅ **HomeKit** - Apple HomeKit bridge (FREE!)
- ✅ **Google Nest** - Nest integration (optional)
- ✅ **Automation Ready** - Trigger smart home devices

### Phase 5 (Cloud & Mobile) ✅
- ✅ **Cloud Storage** - AWS S3, GCS, Azure, or MinIO (MinIO is FREE!)
- ✅ **Mobile App Structure** - React Native foundation
- ✅ **Real-time Streaming** - WebSocket support
- ✅ **Remote Access** - WireGuard VPN (FREE!), Tailscale, ZeroTier

### Phase 6 (Advanced Features) ✅ **NEW!**
- ✅ **Recording Management** - Search, download, stream recordings
- ✅ **Advanced Analytics** - Hourly/daily activity breakdown
- ✅ **Storage Management** - Automatic cleanup, statistics
- ✅ **Multi-User System** - Admin, User, Viewer roles
- ✅ **Rate Limiting** - API abuse protection
- ✅ **SQL Injection Protection** - Enhanced security
- ✅ **PostgreSQL Support** - Production-ready database
- ✅ **Docker Deployment** - Easy containerized setup

### v3.1.0 Features ✅ **LATEST!**
- ✅ **Camera Discovery** - Automatic USB and network camera detection
  - USB webcam scanning
  - Network camera discovery (ONVIF protocol)
  - Auto-detection with one click
  - Manual camera configuration
  - See [Camera Discovery Guide](#camera-discovery)
  
- ✅ **Theme System** - 8 superhero themes with consistent styling
  - Sman (Classic red/blue)
  - Bman (Dark knight)
  - W Woman (Warrior gold)
  - Flah (Speed red)
  - Aman (Ocean teal)
  - Cy (Tech silver)
  - G Lantern (Willpower green)
  - Default (Professional blue)
  
- ✅ **Help System** - Comprehensive inline help with 36+ entries
  - Context-sensitive help buttons (?)
  - Theme-aware tooltips
  - Mobile responsive
  - Covers all features and settings
  - See [HELP_SYSTEM_IMPLEMENTATION.md](opencv-surveillance/HELP_SYSTEM_IMPLEMENTATION.md)
  
- ✅ **First-Run Setup** - User-friendly admin account creation
  - Interactive setup wizard
  - Strong password enforcement (12+ chars, complexity)
  - Real-time password strength indicator
  - Email validation
  - No more auto-generated passwords!

---

## 🚀 Quick Start

```bash
# 1. Clone repository
git clone https://github.com/M1K31/OpenEye.git
cd OpenEye/opencv-surveillance

# 2. Install dependencies (all free!)
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings (see docs/USER_GUIDE.md)

# 4. Start server
python -m backend.main

# 5. Access dashboard
open http://localhost:8000/api/docs
```

**That's it!** You now have a professional surveillance system running at **$0/month**! 🎉

---

## 📚 Documentation

### For Users
- **[User Guide](opencv-surveillance/docs/USER_GUIDE.md)** - Complete setup and usage guide
  - Free vs paid service options
  - Configuration examples
  - Telegram/Email/VPN setup
  - Troubleshooting common issues

- **[Uninstall Guide](opencv-surveillance/docs/UNINSTALL_GUIDE.md)** - Complete removal instructions
  - Step-by-step uninstallation
  - Selective removal options
  - Backup and restore procedures

### For Developers
- **[API Documentation](http://localhost:8000/api/docs)** - Interactive API reference (when running)
- **[Docker Guide](opencv-surveillance/DOCKER.md)** - Container deployment
- **[Implementation Status](opencv-surveillance/PHASE_4_5_COMPLETE.md)** - All phases completed

### Quick References
- **[Setup Guide](opencv-surveillance/docs/setup_guide.md)** - Initial setup
- **[API Reference](opencv-surveillance/docs/api_reference.md)** - Endpoint documentation
- **[Cleanup Report](opencv-surveillance/CLEANUP_REPORT.md)** - File organization

---

## 🏗️ Architecture

```
OpenEye System
│
├── Backend (FastAPI + OpenCV)
│   ├── Camera Management
│   │   ├── RTSP Camera Support
│   │   ├── Mock Camera (Testing)
│   │   └── Stream Processing
│   ├── Motion Detection (OpenCV MOG2)
│   ├── Face Recognition (face_recognition + dlib)
│   │   ├── Face Detection
│   │   ├── Face Encoding
│   │   └── Person Identification
│   ├── Video Recording
│   │   ├── Motion-Triggered
│   │   └── Metadata Tracking
│   └── REST API
│       ├── Authentication
│       ├── Camera Control
│       ├── Face Management
│       └── Analytics
│
└── Frontend (React + Vite)
    ├── Live Dashboard
    ├── Face Management
    ├── Detection History
    └── Settings

Database (SQLite)
├── Users
├── Face Detection Events
├── Recording Events
└── System Logs
```

---

## 🚀 Installation

### Prerequisites

- **Python 3.9+**
- **Node.js 16+** and npm
- **CMake** (required for dlib)
- **Git**

### System Dependencies

#### Ubuntu/Debian/Raspberry Pi:
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    libpng-dev \
    python3-dev
```

#### macOS:
```bash
brew install cmake openblas
```

#### Windows:
- Install Visual Studio Build Tools
- Install CMake from https://cmake.org/download/

### Quick Start

1. **Clone the repository:**
```bash
git clone https://github.com/M1K31/OpenEye.git
cd OpenEye
```

2. **Install backend dependencies:**
```bash
cd opencv-surveillance/backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r ../../requirements.txt
```

*Note: dlib installation may take 5-30 minutes to compile*

3. **Install frontend dependencies:**
```bash
cd ../frontend
npm install
```

4. **Create faces directory:**
```bash
cd ..
mkdir -p faces
```

5. **Start the backend:**
```bash
cd opencv-surveillance
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

6. **Start the frontend** (new terminal):
```bash
cd opencv-surveillance/frontend
npm run dev
```

7. **Access the application:**
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/api/docs

### Docker Installation

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## 💻 Usage

### First Time Setup

1. **Create a user:**
```bash
curl -X POST "http://localhost:8000/api/users/" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password", "email": "admin@example.com"}'
```

2. **Login** to the web interface at http://localhost:5173

3. **Add people for face recognition:**
   - Click "👤 Manage Faces"
   - Add a new person
   - Upload 3-5 clear photos
   - Click "Train Model"

4. **View live stream** and see face recognition in action!

### Adding Real Cameras

```python
# Via Python API
from backend.core.camera_manager import manager

manager.add_camera(
    camera_id="front_door",
    camera_type="rtsp",
    source="rtsp://username:password@camera-ip:554/stream",
    enable_face_detection=True
)
```

Or via REST API:
```bash
curl -X POST "http://localhost:8000/api/cameras/" \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "front_door",
    "camera_type": "rtsp",
    "source": "rtsp://camera-ip:554/stream"
  }'
```

---

## 📚 API Documentation

### Key Endpoints

#### Face Recognition
- `GET /api/faces/people` - List all registered people
- `POST /api/faces/people` - Add a new person
- `POST /api/faces/people/{name}/photos` - Upload photos
- `POST /api/faces/train` - Train the recognition model
- `GET /api/faces/statistics` - Get face detection stats
- `GET /api/faces/detections` - Get recent detections

#### Face Detection History
- `GET /api/faces/history/detections` - Query detection history
- `GET /api/faces/history/statistics` - Get analytics
- `GET /api/faces/history/person/{name}` - Person-specific history
- `GET /api/faces/history/timeline` - Hourly detection timeline

#### Cameras
- `GET /api/cameras/` - List all cameras
- `POST /api/cameras/` - Add a new camera
- `DELETE /api/cameras/{id}` - Remove a camera
- `GET /api/cameras/{id}/stream` - Live MJPEG stream

#### System
- `GET /api/health` - Health check
- `GET /api/system/info` - System information

**Full API documentation:** http://localhost:8000/api/docs

---

## ⚙️ Configuration

### Face Recognition Settings

Edit via UI or API:
```json
{
  "detection_method": "hog",  // "hog" (CPU) or "cnn" (GPU)
  "recognition_threshold": 0.6,  // 0.0-1.0, lower = stricter
  "faces_folder": "faces"
}
```

### Camera Settings

Per-camera configuration:
```json
{
  "face_detection_enabled": true,
  "motion_detection_enabled": true,
  "recording_enabled": true,
  "post_motion_cooldown": 5
}
```

### Camera Discovery

OpenEye v3.1.0 includes automatic camera discovery to simplify setup:

#### USB Camera Discovery
Automatically detects connected USB webcams:
```bash
# Via API
GET /api/cameras/discover/usb

# Returns list of available USB cameras with indices
```

#### Network Camera Discovery  
Scans local network for ONVIF-compatible IP cameras:
```bash
# Via API
GET /api/cameras/discover/network

# Returns list of discovered cameras with:
# - IP address
# - ONVIF port
# - Device information
# - RTSP stream URLs
```

#### Using the Discovery UI
1. Navigate to **Camera Management** page
2. Click the **Discovery** tab
3. Choose **USB** or **Network** scan
4. Click **Scan for Cameras**
5. Select discovered cameras to add
6. Configure settings and save

**Benefits:**
- ✅ No manual RTSP URL configuration
- ✅ Automatic detection of camera capabilities  
- ✅ One-click camera addition
- ✅ Works with most modern IP cameras

**Supported Protocols:**
- USB/Webcam (Video4Linux, DirectShow)
- ONVIF (Network cameras)
- RTSP streams (manual configuration)

### Environment Variables

Create `backend/.env`:
```ini
SECRET_KEY=your-super-secret-key-change-this
DATABASE_URL=sqlite:///./surveillance.db
```

---

## 🛠️ Development

### Project Structure

```
opencv-surveillance/
├── backend/
│   ├── core/
│   │   ├── face_recognition.py      # Face recognition engine
│   │   ├── face_detector.py         # Detection integration
│   │   ├── camera_manager.py        # Camera management
│   │   ├── motion_detector.py       # Motion detection
│   │   └── recorder.py              # Video recording
│   ├── api/
│   │   ├── routes/                  # API endpoints
│   │   └── schemas/                 # Pydantic models
│   ├── database/
│   │   ├── models.py                # SQLAlchemy models
│   │   └── face_crud.py             # Database operations
│   └── main.py                      # FastAPI application
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── DashboardPage.jsx
│       │   └── FaceManagementPage.jsx
│       └── App.jsx
├── faces/                           # Face images storage
├── recordings/                      # Video recordings
└── tests/                           # Test suite
```

### Running Tests

```bash
# Start the backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# In another terminal, run tests
python tests/test_face_recognition.py
```

### Code Style

```bash
# Format Python code
black backend/

# Lint Python code
pylint backend/

# Format JavaScript
cd frontend && npm run lint
```

---

## 🚢 Deployment

### Production Considerations

1. **Change default credentials** and secret keys
2. **Use HTTPS** with proper SSL certificates
3. **Set up firewall** rules to restrict access
4. **Configure CORS** for your domain
5. **Set up automated backups** for database and recordings
6. **Monitor disk space** for recordings
7. **Use production-grade database** (PostgreSQL) for high traffic

### Raspberry Pi Optimization

```python
# Use HOG detection method (CPU-only)
settings = {
    "detection_method": "hog",
    "recognition_threshold": 0.55
}

# Reduce frame processing rate
face_detector.detection_cooldown = 3.0  # Process every 3 seconds
```

### Systemd Service

Create `/etc/systemd/system/openeye.service`:
```ini
[Unit]
Description=OpenEye Surveillance System
After=network.target

[Service]
Type=simple
User=openeye
WorkingDirectory=/opt/openeye
ExecStart=/opt/openeye/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable openeye
sudo systemctl start openeye
```

---

## 🐛 Troubleshooting

### Common Issues

**Issue: dlib fails to install**
```bash
# Solution: Install CMake first
sudo apt-get install cmake
pip install --no-cache-dir dlib==19.24.2
```

**Issue: Face recognition is slow**
- Use 'hog' detection method instead of 'cnn'
- Increase detection cooldown
- Reduce video resolution

**Issue: Faces not detected**
- Ensure photos are high quality and well-lit
- Train the model after adding photos
- Lower recognition threshold
- Check that face_recognition is installed correctly

**Issue: Import errors**
```bash
pip install --force-reinstall -r requirements.txt
```

### Performance Tips

- **Raspberry Pi**: Use HOG detection, lower resolution
- **GPU Available**: Use CNN detection for better accuracy
- **High Traffic**: Use PostgreSQL instead of SQLite
- **Multiple Cameras**: Consider dedicated hardware per camera

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use ESLint rules for JavaScript
- Write tests for new features
- Update documentation
- Keep commits atomic and well-described

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **OpenCV** - Computer vision library
- **face_recognition** - Face recognition built on dlib
- **FastAPI** - Modern Python web framework
- **React** - Frontend library
- **dlib** - Machine learning toolkit

---

## 📧 Support

- 📖 **Documentation**: Check this README and [API docs](http://localhost:8000/api/docs)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/M1K31/OpenEye/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/M1K31/OpenEye/discussions)

---

## 🎯 Roadmap

- [x] Phase 1: Basic motion detection and recording
- [x] Phase 2: Face recognition and analytics
- [ ] Phase 3: Notifications and alerts
- [ ] Phase 4: Smart home integration
- [ ] Phase 5: Mobile applications
- [ ] Phase 6: Cloud storage options

---

**Made with ❤️ using OpenCV**

*OpenEye - See clearly, secure completely*
