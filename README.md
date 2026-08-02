# OpenEye - AI-Powered Home Security with OpenCV & Face Recognition

![Version](https://img.shields.io/badge/version-3.11.8-blue.svg)
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
- ✅ **No AI API costs** - Uses free local face recognition (dlib)

---

## 🎯 Why OpenEye?

**OpenEye leverages OpenCV's full power** for advanced computer vision:
- ✨ **True OpenCV Implementation** - Direct use of OpenCV algorithms
- 🧠 **AI Face Recognition** - dlib-based detection and recognition with clustering
- 🎥 **Real-time Processing** - Efficient video stream analysis
- 🏠 **Self-Hosted** - Complete control over your data
- 🚀 **Modern Stack** - FastAPI + React with WebSockets
- 📊 **Rich Analytics** - Historical tracking and statistics
- 🎨 **Beautiful UI** - 9 customizable themes with 8pt grid design

---

## ✨ Key Features

### Core Surveillance
- 🎥 **Multi-Camera Support** - RTSP, USB, network cameras with auto-discovery
- 👁️ **Motion Detection** - OpenCV MOG2 background subtraction
- 📹 **Auto Recording** - Motion-triggered H.264 video with metadata
- ⚡ **Hardware Encoding** - GPU-accelerated video (70-90% CPU reduction) with NVENC, QuickSync, VideoToolbox, VAAPI
- 🎬 **Live Streaming** - MJPEG streams with real-time overlays
- 👤 **Face Recognition** - AI-powered identification with confidence scores
- 🧠 **Face Clustering** - DBSCAN-based grouping of unknown faces
- 🔍 **Object Detection** - YOLOv8-powered AI detection for vehicles, animals, packages (v3.10.0)
- 🏷️ **Object Identification** - Track specific vehicles, pets, or items with named detection (v3.10.0)
- 🎤 **Two-Way Audio** - WebRTC bidirectional audio communication with cameras (v3.10.0)
- 📊 **Timeline View** - Interactive playback with event markers
- 💾 **Dual Database** - SQLite (development) or PostgreSQL (production)

### User Interface
- 🎨 **9 Themes** - Man of Steel, Dark Knight, Amazonian Demigod, Hermes, King of Atlantis, Cyborg, Lantern, Aqua Security, Default
- ❓ **Integrated Help System** - 36+ context-sensitive help entries
- 🎯 **First-Run Wizard** - Easy setup for new installations
- 📱 **Responsive Design** - Works on desktop, tablet, mobile
- 🔐 **Multi-User Support** - Admin, User, Viewer roles with JWT authentication
- ⚡ **Optimized Performance** - React code splitting, lazy loading, 77% smaller bundle size

### Security
- 🔐 **Two-Factor Authentication** - TOTP-based 2FA with QR code setup
- 🛡️ **Rate Limiting** - Per-endpoint rate limits with category-based controls
- 🔒 **CSRF Protection** - Double-submit cookie pattern (optional)
- 📝 **Audit Logging** - Comprehensive security event tracking (42 event types)
- 🔐 **Encrypted Credentials** - Fernet encryption for notification provider secrets
- 🚫 **SQL Injection Protection** - Request validation middleware

### Notifications & Alerts
- 📧 **Email Alerts** - SMTP notifications (FREE with Gmail)
- 📱 **SMS Alerts** - Twilio integration
- 💬 **Telegram Bot** - FREE push notifications
- 🌐 **Discord/Webhooks** - Custom integrations
- 🔔 **FCM Push** - Firebase Cloud Messaging
- 🚗 **Object Detection Alerts** - Class-based and entity-based notifications (vehicles, animals, packages) (v3.10.0)
- ⏱️ **Smart Throttling** - Prevent notification spam

### Smart Home Integration
- 🏠 **Home Assistant** - MQTT integration (FREE!)
- 🍎 **HomeKit** - Apple HomeKit bridge (FREE!)
- ⚙️ **Automation Engine** - Person-based triggers and rules
- 🪝 **Webhook System** - RESTful integrations

### Cloud & Storage
- ☁️ **Cloud Storage** - AWS S3, Google Cloud, Azure, MinIO (FREE!)
- 🗄️ **Automatic Cleanup** - Configurable retention policies
- 📈 **Storage Analytics** - Monitor disk usage
- 🔄 **Backup Options** - Multiple storage backends

---

## 🚀 Quick Start

### Option 1: Docker (Recommended for Production)

**One-command deployment** with Docker Compose:

```bash
# Pull and run
docker run -d \
  -p 8000:8000 \
  -v ./data:/app/data \
  -v ./recordings:/app/recordings \
  -v ./faces:/app/faces \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -e JWT_SECRET_KEY=$(openssl rand -hex 32) \
  -e NOTIFICATION_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  --restart unless-stopped \
  --name openeye \
  im1k31s/openeye-opencv_home_security:latest
```

**Or use Docker Compose** (see [DOCKER.md](DOCKER.md) for full guide):

```yaml
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
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - NOTIFICATION_ENCRYPTION_KEY=${NOTIFICATION_ENCRYPTION_KEY}
    restart: unless-stopped
```

Then run: `docker-compose up -d`

**Access**: http://localhost:8000

---

### Option 2: Local Installation (Automated Setup)

**NEW**: One-command automated installation with `setup-production.sh`

#### Prerequisites
- Python 3.9+ (3.11+ recommended)
- Node.js 20+ and npm (20.19+ or 22.12+ required for Vite 7)
- Git

#### Installation

```bash
# Clone repository
git clone https://github.com/M1K31/OpenEye-OpenCV_Home_Security.git
cd OpenEye-OpenCV_Home_Security

# Run automated setup (creates .venv, installs deps, generates keys, builds frontend)
./setup-production.sh

# (Optional) Install heavy dependencies (face recognition, YOLO, two-way audio)
./install-deps.sh

# Start the server
./start-local.sh
```

**The setup script automatically**:
- ✅ Creates virtual environment
- ✅ Installs all dependencies
- ✅ **Generates all secret keys automatically** (no manual steps!)
- ✅ Runs database migrations
- ✅ Builds frontend production bundle
- ✅ Creates required directories
- ✅ Verifies installation

> **Graceful Degradation**: OpenEye automatically disables features when optional dependencies aren't installed. Core surveillance (motion detection, recording, notifications) works without face recognition, YOLO, or two-way audio packages.

**Access**: http://localhost:8000

#### Management Commands

```bash
./start-local.sh          # Start server (graceful shutdown on Ctrl+C)
./stop-server.sh          # Gracefully stop server
./kill-server.sh          # Force kill server (emergency)
./uninstall.sh            # Complete removal with backup options
```

---

### Option 3: Manual Installation (Advanced)

<details>
<summary>Click to expand manual installation steps</summary>

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
brew install opencv pkg-config cmake python@3.11
```

#### Installation Steps

```bash
# Clone and navigate
git clone https://github.com/M1K31/OpenEye-OpenCV_Home_Security.git
cd OpenEye-OpenCV_Home_Security/opencv_surveillance

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Generate secret keys
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" > .env
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))" >> .env
python3 -c "from cryptography.fernet import Fernet; print('NOTIFICATION_ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env

# Add default config to .env
cat >> .env << EOF
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite:///./surveillance.db
CORS_ORIGINS=http://localhost:8000
LOG_LEVEL=INFO
EOF

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Start server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

</details>

---

## 📖 Documentation

### User Documentation
- 📘 **[User Guide](docs/USER_GUIDE.md)** - Complete usage instructions
- 🔧 **[Setup Guide](docs/deployment/setup_guide.md)** - Smart home integrations
- 🗑️ **[Uninstall Guide](docs/UNINSTALL_GUIDE.md)** - Safe removal instructions

### Technical Documentation
- 🔌 **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation
- ⚡ **[WebSocket Implementation](docs/development/WEBSOCKET_IMPLEMENTATION.md)** - Real-time updates
- 🐧 **[Systemd Service](docs/deployment/LINUX_SYSTEMD_SERVICE.md)** - Production deployment
- 🔧 **[Quick Reference](docs/QUICK_REFERENCE.md)** - Common tasks

### Project Documentation
- 📝 **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- 🐳 **[DOCKER.md](DOCKER.md)** - Docker deployment guide

---

## 🎬 First-Run Setup

1. **Access the application**: http://localhost:8000
2. **Create admin account**: Follow the first-run wizard
3. **Add cameras**:
   - Click **"Camera Discovery"** to auto-find cameras
   - Or manually add RTSP/USB cameras
4. **Train face recognition** (optional) — two ways:
   - **From detections** (easiest): open **Detections → People**, review the faces the
     system captured, tick a few clear ones, and choose **Assign to person…** to create
     a new profile (e.g. "Mikel") or add to an existing one. Training runs automatically.
   - **By upload**: go to **Face Management → Upload Faces** and add 3–10 clear photos
     per person.
5. **Configure notifications** (optional):
   - Go to **"System & Alerts"** → **"Configure Notification Providers"**
   - Add email, SMS, Telegram, or webhook providers

**You're ready!** View live cameras on the dashboard.

---

## 🛠️ System Requirements

### Minimum
- **CPU**: Dual-core 2.0GHz
- **RAM**: 2GB
- **Storage**: 10GB + recording space
- **OS**: Linux, macOS, Windows (WSL2)

### Recommended
- **CPU**: Quad-core 2.5GHz+
- **RAM**: 4GB+
- **Storage**: 50GB+ SSD
- **OS**: Ubuntu 20.04+ or macOS 11+
- **GPU**: Optional (CUDA support for faster processing)

---

## 🔐 Security (v3.6.0 Enhanced)

OpenEye implements multiple security layers:
- 🔒 **JWT Authentication** - Secure token-based auth with automatic refresh
- 🔢 **Two-Factor Authentication (2FA)** - TOTP-based 2FA with QR code setup
- 🔑 **Password Hashing** - bcrypt with salt
- 🛡️ **Per-Endpoint Rate Limiting** - Granular limits per API category (auth: 10/min, write: 30/min, read: 100/min)
- 🛡️ **CSRF Protection** - Double-submit cookie pattern for state-changing requests
- 🚫 **SQL Injection Protection** - Parameterized queries + middleware
- 🔐 **Encrypted Credentials** - Fernet encryption for notification provider secrets
- 📝 **Enhanced Audit Logging** - Comprehensive security event tracking (42 event types, JSONL format)
- 🌐 **CORS Protection** - Configurable origin whitelist

**Production Checklist**:
- ✅ Change default admin password immediately
- ✅ Use strong, unique secret keys (auto-generated by setup script)
- ✅ Enable HTTPS with valid SSL certificate (nginx/Caddy reverse proxy)
- ✅ Restrict CORS_ORIGINS to your domain
- ✅ Configure firewall rules (only port 8000 or HTTPS 443)
- ✅ Never commit .env file to version control

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

**Development Workflow**:
```bash
# Setup development environment
./setup-production.sh

# Start with hot reload
./start-local.sh

# Run tests
cd opencv_surveillance
pytest
```

---

## 📊 Project Status

**Current Version**: 3.11.8 (Face-Management Workflow & Stability)

### Recent Updates (v3.11.8)
**Face management (UI):**
- 👥 **Assign detections to a person** — from any face card, add it to an existing
  saved profile *or* create a new person; the selected snapshots are used to train
  recognition immediately (no separate train step).
- ☑️ **Batch selection** — tick multiple detections and save them as a new person or
  add them to an existing profile in one action.
- 🏷️ **Accurate known/unknown labels** — auto-enumerated `unknownN` placeholders are
  shown as *Unknown*, not as identified people; only named profiles read as "known".

**Stability & noise:**
- 🎥 **Recording crash fix** — thread-safe video writer (no more segfault when a
  recording stops while a frame is being written).
- 📹 **Camera startup** — reliable USB/AVFoundation open on macOS; unavailable cameras
  no longer block startup.
- 🔇 **Quieter logs** — suppressed benign FFmpeg `Invalid pts` warnings and fixed a
  chatty event-publish retry loop.

### Previous Updates (v3.11.5)
**Bug Fixes:**
- Fixed camera discovery API error (`get_all_cameras` → `get_cameras`)
- Fixed CameraDiscoveryPage.jsx styling (hardcoded colors → CSS theme variables)

**Documentation:**
- Added comprehensive Docker platform limitations documentation
- Documented USB camera limitations on macOS/Windows Docker
- Added Linux-specific device passthrough and host networking examples

### Previous Updates (v3.11.4)
**New Features:**
- 📅 **Scheduled Tasks System** - Background scheduler for automated maintenance
  - Model retraining: Automatically retrain face recognition on schedule
  - Retroactive face search: Re-identify faces in past events
  - Database & snapshot cleanup with configurable retention
- 🔍 **MagicMirror Face Search API** - Voice command support for detection queries
  - Natural language date parsing ("today", "yesterday", "December 24")
  - `/api/ecosystem/faces/search` endpoint with voice response generation
- 📊 **Ecosystem Statistics** - Event counts for companion apps

### Previous Updates (v3.11.1 - Multi-User & Ecosystem)
- 👥 **Complete Multi-User System** - Role-based access control (admin/user/viewer)
- 🌐 **Ecosystem Integration** - MagicMirror, mobile app support with WebSocket events
- 📱 **Multi-Device Support** - Smart notification routing with per-device preferences

### Previous Updates (v3.10.0 - Object Detection & Two-Way Audio)
- 🔍 **YOLOv8 Object Detection** - Vehicles, animals, packages with named tracking
- 🎤 **Two-Way Audio** - WebRTC bidirectional communication with cameras
- 🔔 **Object Detection Alerts** - Class-based and entity-based notifications

See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## 🐛 Troubleshooting

### Common Issues

**Port 8000 already in use**:
```bash
./kill-server.sh  # Force kill any hanging processes
# Or manually: lsof -ti:8000 | xargs kill -9
```

**Database locked error**:
```bash
# Stop server, remove locks
./stop-server.sh
rm opencv_surveillance/surveillance.db-shm opencv_surveillance/surveillance.db-wal
```

**Face recognition not working**:
- Ensure camera has good lighting
- Upload 5-10 clear photos per person
- Check logs: `tail -f opencv_surveillance/logs/app.log`

**Frontend not loading**:
```bash
cd opencv_surveillance/frontend
npm run build
```

**Complete reset** (removes all data):
```bash
./uninstall.sh  # Choose "No backup" option
./setup-production.sh
```

**macOS: USB or built-in camera not detected (native install)**:
macOS grants camera access per *app*, and it will only prompt an app that has its own
identity. A plain background/launchd service has none, so camera discovery silently
finds nothing.

**Recommended — use OpenEye.app** (created automatically by the installer in
`~/Applications`, or build it with `opencv_surveillance/scripts/build-macos-app.sh`):
1. Launch **OpenEye** from `~/Applications` or Spotlight.
2. **Approve the camera prompt** the first time it appears.
3. The UI opens automatically at http://localhost:8200.

The grant persists across restarts. If no prompt appears, enable **OpenEye** under
**System Settings → Privacy & Security → Camera**, then relaunch. After granting
permission for the first time, restart OpenEye so the running process picks it up.

**Alternative — run from a Terminal** (fully supported; the Terminal's own camera
grant is used). This is the same workflow Linux uses and remains first-class:
```bash
cd ~/.local/share/openeye/app && ./start.sh    # ./stop.sh to stop
```
From a git checkout, `./restart.sh --foreground` does the same thing. To skip building
the app bundle entirely, install with `OPENEYE_SKIP_APP_BUNDLE=1`.

> Logs for the app launcher: `~/.local/share/openeye/logs/openeye-app.log`

**macOS: changing storage paths (System → Storage Paths)**
Recordings, snapshots and face directories stay fully configurable in the UI under the
app bundle — it is not sandboxed, so it can use any location your user account can.
macOS does separately protect a few locations, so if you point a path at **Documents,
Desktop, Downloads, an external drive or a network volume**, approve the macOS prompt
that appears (OpenEye declares these uses). If a path silently fails to save, enable
**OpenEye** under **System Settings → Privacy & Security → Files and Folders**.
Storing data on an internal disk remains the recommended default — an external volume
that unmounts while recording can interrupt capture.

**Docker: USB cameras not discovered (macOS/Windows)**:
Docker Desktop runs containers in a Linux VM, preventing USB device access.
- Use RTSP/IP cameras instead (add manually with RTSP URLs)
- Or run OpenEye natively: `pip install -r requirements.txt && python main.py`
- See [DOCKER.md](DOCKER.md) for detailed platform limitations

**Docker: Network cameras not discovered**:
The container uses bridge networking, scanning Docker's virtual network instead of your LAN.
- Add cameras manually using their RTSP URLs
- On Linux, use `network_mode: host` in docker-compose.yml

For more help, see [User Guide](docs/USER_GUIDE.md) or open an issue.

---

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

Copyright (c) 2025 Smart Industries LLC (Mikel Smart)

---

## 🙏 Acknowledgments

Built with:
- [OpenCV](https://opencv.org/) - Computer vision library
- [dlib](http://dlib.net/) - Face recognition
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://reactjs.org/) - UI library
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM

UI Design Inspiration:
- [Material-UI Switch Component](https://github.com/mui/material-ui/tree/v7.3.4/packages/mui-material/src/Switch) - Toggle switch design (MIT License)

---

## 📞 Support

- 📧 **Issues**: [GitHub Issues](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues)
- 📖 **Documentation**: [docs/](docs/)
- 🐳 **Docker Hub**: [im1k31s/openeye-opencv_home_security](https://hub.docker.com/r/im1k31s/openeye-opencv_home_security)

---

**Made with ❤️ by Smart Industries LLC** | **100% Free Forever** | **No Subscriptions**

## 📦 Deployment Notes

### Raspberry Pi Deployment

`requirements-pi.txt` installs a lightweight subset of dependencies suitable for ARM Linux (Raspberry Pi 4+), omitting heavy optional packages like face recognition and YOLO that cannot build on ARM.

```bash
# Lightweight install — core surveillance only (motion detection, recording, notifications)
pip install -r opencv_surveillance/requirements-pi.txt

# Alternatively, use install-deps.sh for selective installation on supported platforms
# (installs only the packages whose system prerequisites are available)
./install-deps.sh
```

### Platform Support
| Platform | Status | Notes |
|----------|--------|-------|
| Intel macOS | Fully supported | All features including face recognition, YOLO, two-way audio |
| ARM Linux (Pi 4+) | Partial | Use `requirements-pi.txt` or `install-deps.sh`; face recognition and YOLO unavailable |
| Intel Linux | Fully supported | All features; use `install-deps.sh` to add heavy optional packages |

Minimum Python version: 3.10 (recommended 3.11+)
