# OpenEye - Advanced Home Security with OpenCV & AI Face Recognition

![Version](https://img.shields.io/badge/version-3.5.1.4-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-green.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-red.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Free](https://img.shields.io/badge/cost-$0/month-success.svg)

A **100% free and open-source** AI-powered surveillance system using **OpenCV** and **face recognition**. Self-hosted, private, and completely free - forever.

🐳 **Docker Hub**: [im1k31s/openeye-opencv_home_security](https://hub.docker.com/r/im1k31s/openeye-opencv_home_security)

---

## 💰 Completely Free!

- ✅ **No subscriptions** - $0/month forever
- ✅ **No cloud dependencies** - Works completely offline
- ✅ **No sign-ups required** - All cloud services are optional
- ✅ **Open source** - Inspect and modify all code
- ✅ **Self-hosted** - Your data stays on your hardware
- ✅ **No AI API costs** - Uses free local face recognition

---

## 🎯 Why OpenEye?

**OpenEye leverages OpenCV's full power** for advanced computer vision:
- ✨ **True OpenCV Implementation** - Direct use of OpenCV algorithms, not Motion
- 🧠 **AI Face Recognition** - dlib-based detection and recognition
- 🎥 **Real-time Processing** - Efficient video stream analysis
- 🏠 **Self-Hosted** - Complete control over your data
- 🚀 **Modern Stack** - FastAPI + React
- 📊 **Rich Analytics** - Historical tracking and statistics
- 🎨 **Beautiful UI** - 8 customizable superhero themes

---

## ✨ Features

### Core Surveillance (v3.0+)
- 🎥 **Multi-Camera Support** - RTSP, USB, network cameras
- 👁️ **Motion Detection** - OpenCV MOG2 background subtraction
- 📹 **Auto Recording** - Motion-triggered video capture with metadata
- 🎬 **Live Streaming** - MJPEG streams with real-time overlays
- 👤 **Face Recognition** - AI-powered identification
- 📊 **Detection History** - Track all events with timestamps
- 💾 **Database** - SQLite or PostgreSQL storage

### Camera Discovery (v3.1.0+)
- 🔍 **USB Auto-Detection** - Scans and tests USB webcams
- 🌐 **Network Scanning** - Discovers RTSP/IP cameras on local network
- ⚡ **One-Click Setup** - Quick-add discovered cameras
- ✅ **Pre-Add Testing** - Validate before adding to system
- 🎛️ **Smart Configuration** - Auto-detect resolution/FPS

### User Interface (v3.1.0+)
- 🎨 **8 Superhero Themes** - Superman, Batman, Wonder Woman, Flash, Aquaman, Cyborg, Green Lantern, Default
- ❓ **Integrated Help System** - 36+ context-sensitive help entries
- 🎯 **First-Run Wizard** - Easy setup for new installations
- 📱 **Responsive Design** - Works on desktop, tablet, mobile
- 🔐 **Multi-User Support** - Admin, User, Viewer roles

### System Configuration (v3.5.1+)
- ⚙️ **System Settings Page** - Comprehensive configuration interface
- 📁 **Custom Storage Paths** - Configure recording and face image directories
- ✅ **Path Validation** - Verify paths with auto-creation support
- 🖼️ **Display Modes** - Grid, Vertical, Horizontal, or Auto-Cycle layouts
- 🎛️ **Granular Camera Controls** - Per-camera motion/recording/face detection toggles
- ⏱️ **Recording Settings** - Configurable duration and cycle intervals
- 💾 **Persistent Settings** - All settings saved to database

### Notifications (Phase 3)
- 📧 **Email Alerts** - SMTP notifications (FREE with Gmail)
- 📱 **SMS Alerts** - Twilio or Telegram Bot (Telegram is FREE!)
- 🔔 **Push Notifications** - Firebase or ntfy.sh (ntfy.sh is FREE!)
- 🪝 **Webhooks** - Custom integrations
- ⏱️ **Smart Throttling** - Prevent notification spam

### Smart Home Integration (Phase 4)
- 🏠 **Home Assistant** - MQTT integration (FREE!)
- 🍎 **HomeKit** - Apple HomeKit bridge (FREE!)
- 🏡 **Google Nest** - Nest integration
- ⚙️ **Automation** - Trigger smart home devices on events

### Cloud & Storage (Phase 5)
- ☁️ **Cloud Storage** - AWS S3, Google Cloud, Azure, or MinIO (FREE!)
- 🗄️ **Automatic Cleanup** - Configurable retention policies
- 📈 **Storage Analytics** - Monitor disk usage
- 🔄 **Backup Options** - Multiple storage backends

### Advanced Features (Phase 6)
- 🎬 **Recording Management** - Search, download, stream recordings
- 📊 **Advanced Analytics** - Hourly/daily activity reports
- 👥 **Multi-User System** - Role-based access control
- 🛡️ **Security Hardening** - Rate limiting, SQL injection protection
- 🗃️ **PostgreSQL Support** - Production-ready database
- 🐳 **Docker Ready** - Easy containerized deployment

---

## 🚀 Quick Start

### Option 1: Docker (Recommended)

#### 1. Generate Security Keys

**REQUIRED**: Generate secure random keys before running:

```bash
# Mac/Linux
openssl rand -hex 32  # Copy this as SECRET_KEY
openssl rand -hex 32  # Copy this as JWT_SECRET_KEY

# Windows PowerShell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))

# Python (all platforms)
python -c "import secrets; print(secrets.token_hex(32))"
```

#### 2. Create Docker Compose File

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  openeye:
    image: im1k31s/openeye-opencv_home_security:latest
    container_name: openeye
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./recordings:/app/recordings
      - ./faces:/app/faces
    environment:
      - SECRET_KEY=your_generated_secret_key_here
      - JWT_SECRET_KEY=your_generated_jwt_secret_here
      - ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=30
    restart: unless-stopped
```

#### 3. Start OpenEye

```bash
docker-compose up -d
```

#### 4. Access the Application

Open your browser to: **http://localhost:8000**

Follow the first-run setup wizard to create your admin account.

---

### Option 2: Local Installation (Automated)

**🚀 NEW**: Use our automated installation script for a one-command setup!

#### Prerequisites

- Python 3.8+ (Python 3.12+ recommended)
- Node.js 16+ and npm (for frontend)
- Git
- macOS or Linux

#### Automated Installation

```bash
# Clone repository
git clone https://github.com/M1K31/OpenEye-OpenCV_Home_Security.git
cd OpenEye-OpenCV_Home_Security/opencv-surveillance

# Run the installation script
./scripts/install-local.sh
```

The script will:
- ✅ Check Python version and system dependencies
- ✅ Install required system packages (OpenCV, CMake, etc.)
- ✅ Create Python virtual environment
- ✅ Install all Python dependencies
- ✅ Generate secure secret keys automatically
- ✅ Create configuration files (.env)
- ✅ Build frontend (if Node.js installed)
- ✅ Create launch scripts (start.sh, stop.sh)
- ✅ Optionally create systemd service (Linux)

#### Starting OpenEye

```bash
# After installation, simply run:
./start.sh

# Or manually:
source venv/bin/activate
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Stop the server:
./stop.sh
# Or press Ctrl+C in the terminal
```

Access at: **http://localhost:8000**

---

### Developer & Maintenance Tools

- **Audit Tool (Phase Verification)**: A lightweight auditor is included at `opencv-surveillance/scripts/audit-system.py`. Run it from the `opencv-surveillance` folder to verify backend classes, methods, and Phase 2/3 compliance. It helps identify naming mismatches and missing APIs.

```bash
cd opencv-surveillance
python3 scripts/audit-system.py
```

- **Token Refresh UX**: The frontend includes an automatic token refresh flow. When a request fails with 401 due to an expired JWT the UI will show an inline "Session Expired" modal asking the user to re-authenticate. After a successful login the original request is retried automatically so the user keeps their current state.

> Quick recovery: If the session modal fails, see the "Troubleshooting: Session & Token Refresh" section in the API docs (`opencv-surveillance/docs/API_DOCUMENTATION.md`) or the User Guide (`opencv-surveillance/docs/USER_GUIDE.md`).


### Option 3: Manual Installation (Advanced)

If you prefer manual control or the script doesn't work for your system:

#### Prerequisites

- Python 3.8+
- Node.js 16+ and npm
- CMake (for dlib)
- Git

#### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update && sudo apt-get install -y \
    python3-dev python3-pip python3-venv \
    build-essential cmake pkg-config \
    libopencv-dev libavcodec-dev libavformat-dev \
    libswscale-dev libv4l-dev libatlas-base-dev \
    gfortran libhdf5-dev libjpeg-dev libpng-dev
```

**macOS:**
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install opencv pkg-config cmake python@3.12
```

#### Installation Steps

```bash
# Clone repository
git clone https://github.com/M1K31/OpenEye-OpenCV_Home_Security.git
cd OpenEye-OpenCV_Home_Security/opencv-surveillance

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Upgrade pip and install Python dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Create required directories
mkdir -p data/faces data/thumbnails models/face_detection_model

# Generate secret keys and create .env file
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
ADMIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Create .env file
cat > .env << EOF
# Security Keys - KEEP THESE SECRET!
JWT_SECRET_KEY=$JWT_SECRET
ADMIN_TOKEN=$ADMIN_TOKEN

# Database
DATABASE_URL=sqlite:///./surveillance.db

# Server Configuration
HOST=0.0.0.0
PORT=8000

# CORS Settings
CORS_ORIGINS=http://localhost:8000,http://localhost:3000

# Feature Flags
ENABLE_MOTION_DETECTION=true
ENABLE_FACE_RECOGNITION=true
ENABLE_RECORDING=true

# Logging
LOG_LEVEL=INFO
EOF

# Install frontend dependencies and build (optional but recommended)
cd frontend
npm install
npm run build
cd ..

# Start the application
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Access at: **http://localhost:8000**

#### Important Notes

1. **Always activate venv**: Run `source venv/bin/activate` before starting the server
2. **Keep .env secure**: Never commit this file to version control
3. **Change admin password**: On first login, change the default admin credentials
4. **Regular backups**: Backup your `surveillance.db` file regularly

**🚀 Production Setup (Linux):** For running OpenEye as a system service with auto-start and auto-restart, see [Linux Systemd Service Guide](opencv-surveillance/docs/LINUX_SYSTEMD_SERVICE.md)

---

## 📚 Documentation

### Quick Links
- 📖 [Installation Guide](#quick-start)
- 🐧 [Linux Systemd Service](opencv-surveillance/docs/LINUX_SYSTEMD_SERVICE.md) - Run as system service
- 🔄 [Docker vs Linux Comparison](DOCKER_VS_LINUX_INSTALLATION_ANALYSIS.md) - Feature parity analysis
- 🎨 [Theme System](#themes)
- 🎥 [Camera Setup](#camera-setup)
- 👤 [Face Management](#face-management)
- 🔔 [Notification Setup](#notifications)
- 🏠 [Smart Home Integration](#smart-home)
- 🐛 [Troubleshooting](#troubleshooting)
- 🗑️ [Uninstall Guide](opencv-surveillance/docs/UNINSTALL_GUIDE.md)
- 📚 [Full User Guide](opencv-surveillance/docs/USER_GUIDE.md)
- 🔧 [API Reference (Old)](opencv-surveillance/docs/api_reference.md)
- **🚀 [API Documentation (NEW)](opencv-surveillance/docs/API_DOCUMENTATION.md)** ⭐
- 📊 [Statistics Polling Alternatives](STATISTICS_POLLING_ALTERNATIVES.md) - WebSockets guide
- 📝 [Release Notes v3.3.8](RELEASE_NOTES_v3.3.8.md)
- 📝 [Changelog](CHANGELOG.md)

---

## 🎥 Camera Setup

### Supported Camera Types

| Type | Example | macOS Docker | Linux/Native |
|------|---------|--------------|--------------|
| **RTSP/IP Cameras** | `rtsp://192.168.1.100:554/stream` | ✅ | ✅ |
| **USB Webcams** | `/dev/video0` or index `0` | ⚠️ Limited | ✅ |
| **ONVIF Cameras** | Auto-discovered | ✅ | ✅ |
| **Mock (Testing)** | Built-in test camera | ✅ | ✅ |

⚠️ **macOS Docker Limitation**: USB cameras have limited support in Docker on macOS. Use network/IP cameras or run natively.

### Adding Cameras

#### Method 1: Auto-Discovery (Recommended)

1. Navigate to **Camera Management**
2. Click **Discovery** tab
3. Select **USB** or **Network** scan
4. Click **Quick Add** on discovered cameras

#### Method 2: Manual Configuration

1. Navigate to **Camera Management**
2. Click **Manual** tab
3. Fill in camera details:
   - **Camera ID**: Unique identifier (e.g., `front_door`)
   - **Name**: Friendly name
   - **Type**: RTSP or Mock
   - **Source**: RTSP URL or device path
4. Click **Add Camera**

### Common RTSP URLs

```
# Hikvision
rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101

# Dahua
rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0

# Amcrest
rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1

# Reolink
rtsp://admin:password@192.168.1.100:554/h264Preview_01_main

# Generic
rtsp://username:password@ip_address:port/stream_path
```

---

## 👤 Face Management

### Adding Known Faces

1. Navigate to **Face Management**
2. Click **Upload Face**
3. Enter person's name
4. Upload 3-5 clear photos:
   - Front-facing
   - Well-lit
   - Different expressions
   - Various angles
5. Click **Train Model**

### Best Practices

- ✅ Use high-quality, well-lit photos
- ✅ Include multiple angles and expressions
- ✅ Ensure face is clearly visible
- ❌ Avoid sunglasses or masks
- ❌ Don't use blurry or low-resolution images

---

## 🔔 Notifications

### Email Setup (FREE with Gmail)

1. Navigate to **Alert Settings**
2. Enable **Email Notifications**
3. Configure SMTP:

```
SMTP Host: smtp.gmail.com
SMTP Port: 587
Username: your-email@gmail.com
Password: your-app-password (not your regular password!)
```

**Gmail App Password**: [Generate here](https://myaccount.google.com/apppasswords)

### Telegram Bot (100% FREE!)

1. Create bot with [@BotFather](https://t.me/botfather)
2. Get your Chat ID from [@userinfobot](https://t.me/userinfobot)
3. Configure in OpenEye:

```
Bot Token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
Chat ID: 123456789
```

### Push Notifications (FREE with ntfy.sh)

1. Choose a unique topic name: `openeye-alerts-yourname`
2. Configure in OpenEye:

```
ntfy Server: https://ntfy.sh
Topic: openeye-alerts-yourname
```

3. Subscribe on your phone: [ntfy.sh app](https://ntfy.sh/)

---

## 🏠 Smart Home Integration

### Home Assistant (MQTT)

```yaml
# configuration.yaml
sensor:
  - platform: mqtt
    name: "Front Door Motion"
    state_topic: "openeye/front_door/motion"
    
  - platform: mqtt
    name: "Front Door Face"
    state_topic: "openeye/front_door/face"

automation:
  - alias: "Alert on Unknown Face"
    trigger:
      - platform: state
        entity_id: sensor.front_door_face
        to: "unknown"
    action:
      - service: notify.mobile_app
        data:
          message: "Unknown person detected at front door"
```

### Apple HomeKit

OpenEye exposes motion sensors and occupancy sensors to HomeKit automatically. Add in Home app:

1. Open **Home** app
2. Tap **+** → **Add Accessory**
3. Scan QR code (displayed in OpenEye settings)
4. Add cameras as sensors

---

## 🎨 Themes

OpenEye includes 8 superhero-inspired themes:

1. **Default** - Professional dark theme
2. **Superman** - Classic red and blue
3. **Batman** - Dark knight aesthetic
4. **Wonder Woman** - Warrior princess
5. **Flash** - Speed force energy
6. **Aquaman** - Ocean depths
7. **Cyborg** - Tech enhanced
8. **Green Lantern** - Willpower green

**To change theme**: Click **Themes** button → Select theme → Apply

Themes persist across sessions and include custom animations!

---

## 🐛 Troubleshooting

### Cannot access web interface

**Check if service is running:**
```bash
docker ps  # Should show openeye container
curl http://localhost:8000/api/health  # Should return OK
```

**Solution**: Restart container
```bash
docker-compose restart
```

### Camera not connecting

**Test RTSP URL:**
```bash
ffmpeg -i "rtsp://admin:pass@192.168.1.100:554/stream" -frames:v 1 test.jpg
```

**Common issues:**
- Wrong credentials
- Incorrect RTSP URL
- Camera not on same network
- Firewall blocking ports

### Face recognition not working

**Check model files:**
```bash
ls opencv-surveillance/models/face_detection_model/
# Should contain: shape_predictor_68_face_landmarks.dat
```

**Solution**: Download models
```bash
cd opencv-surveillance/models
./download_models.sh
```

### High CPU usage

**Optimization tips:**
- Lower camera resolution
- Reduce FPS
- Disable face recognition on less important cameras
- Use motion detection zones

### Database locked errors

**Solution**: Switch to PostgreSQL for production
```yaml
environment:
  - DATABASE_URL=postgresql://user:pass@postgres:5432/openeye
```

### Docker build fails

**Common causes:**
- Insufficient disk space
- Network issues during dependency download
- Out of memory

**Solution**: Increase Docker resources (Settings → Resources → 4GB RAM minimum)

---

## 🗑️ Uninstallation

### Docker Cleanup

```bash
# Stop and remove containers
docker-compose down

# Remove images
docker rmi im1k31s/openeye-opencv_home_security:latest

# Remove volumes (WARNING: Deletes all data!)
docker volume prune

# Remove data directories
rm -rf data recordings faces
```

### Manual Cleanup

```bash
# Remove application directory
rm -rf OpenEye-OpenCV_Home_Security

# Remove virtual environment
rm -rf venv

# Remove any created databases
rm surveillance.db
```

Full uninstall guide: [opencv-surveillance/docs/UNINSTALL_GUIDE.md](opencv-surveillance/docs/UNINSTALL_GUIDE.md)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    OpenEye System                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Frontend (React)              Backend (FastAPI)         │
│  ├── Dashboard                 ├── Camera Manager        │
│  ├── Camera Mgmt               ├── Motion Detector       │
│  ├── Face Mgmt                 ├── Face Recognition      │
│  ├── Settings                  ├── Recorder              │
│  └── Themes                    ├── Alert Manager         │
│                                ├── API Routes            │
│                                └── Database (SQLite/PG)  │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  External Integrations (Optional)                        │
│  ├── Email (SMTP)                                        │
│  ├── Telegram Bot                                        │
│  ├── ntfy.sh Push                                        │
│  ├── Home Assistant (MQTT)                               │
│  ├── HomeKit Bridge                                      │
│  └── Cloud Storage (S3/MinIO)                            │
└─────────────────────────────────────────────────────────┘
```

**Technology Stack:**
- **Backend**: Python 3.11, FastAPI, OpenCV, face_recognition, dlib
- **Frontend**: React 18, Vite, React Router
- **Database**: SQLite (default) or PostgreSQL (production)
- **Deployment**: Docker, Docker Compose

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

### Development Guidelines

- Follow PEP 8 for Python
- Use ESLint for JavaScript/React
- Write tests for new features
- Update documentation
- Keep commits atomic and descriptive

### Areas for Contribution

- 🧪 Additional test coverage
- 📝 Documentation improvements
- 🌐 Translations/i18n
- 🎨 New theme designs
- 🔌 Smart home integrations
- 📱 Mobile app development
- 🐛 Bug fixes and performance

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

You are free to:
- ✅ Use commercially
- ✅ Modify
- ✅ Distribute
- ✅ Private use

---

## 🙏 Acknowledgments

- **OpenCV** - Computer vision library powering detection and processing
- **face_recognition** - Simple face recognition built on dlib
- **dlib** - Machine learning toolkit for face detection
- **FastAPI** - Modern, fast Python web framework
- **React** - UI library for building the interface

---

## 📧 Support & Community

- 📖 **Documentation**: This README + [User Guide](opencv-surveillance/docs/USER_GUIDE.md)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/discussions)
- 🐳 **Docker Hub**: [im1k31s/openeye-opencv_home_security](https://hub.docker.com/r/im1k31s/openeye-opencv_home_security)

---

## 🎯 Roadmap

- [x] Phase 1-2: Core surveillance and face recognition
- [x] Phase 3: Notifications and alerts
- [x] Phase 4: Smart home integration  
- [x] Phase 5: Cloud storage and mobile prep
- [x] Phase 6: Advanced features and security
- [x] v3.1.0: Camera discovery and theme system
- [x] v3.2.0: UI/UX improvements
- [x] v3.3.0: Critical bug fixes and stability
- [ ] v3.4.0: Timeline playback system
- [ ] v3.5.0: Two-way audio support
- [ ] v4.0.0: License plate recognition (ALPR)
- [ ] v4.1.0: Object detection (YOLO)
- [ ] v5.0.0: Complete mobile app

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

**Made with ❤️ using OpenCV and AI**

*OpenEye - See clearly, secure completely. 100% Free Forever.*

---

**⭐ If you find OpenEye useful, please star this repository!**
