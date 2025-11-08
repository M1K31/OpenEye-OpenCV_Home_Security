# OpenEye - AI-Powered Home Security with OpenCV & Face Recognition

![Version](https://img.shields.io/badge/version-3.7.1-blue.svg)
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
- 📊 **Timeline View** - Interactive playback with event markers
- 💾 **Dual Database** - SQLite (development) or PostgreSQL (production)

### User Interface
- 🎨 **9 Themes** - Superman, Batman, Wonder Woman, Flash, Aquaman, Cyborg, Green Lantern, Aqua Security, Default
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
- Node.js 16+ and npm
- Git

#### Installation

```bash
# Clone repository
git clone https://github.com/M1K31/OpenEye-OpenCV_Home_Security.git
cd OpenEye-OpenCV_Home_Security

# Run automated setup (creates venv, installs deps, generates keys, builds frontend)
./setup-production.sh

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
python3 -m venv venv
source venv/bin/activate

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
- 📘 **[User Guide](opencv_surveillance/docs/USER_GUIDE.md)** - Complete usage instructions
- 🔧 **[Setup Guide](opencv_surveillance/docs/setup_guide.md)** - Smart home integrations
- 🗑️ **[Uninstall Guide](opencv_surveillance/docs/UNINSTALL_GUIDE.md)** - Safe removal instructions

### Technical Documentation
- 🔌 **[API Reference](opencv_surveillance/docs/API_DOCUMENTATION.md)** - Complete API documentation
- ⚡ **[WebSocket Implementation](opencv_surveillance/docs/WEBSOCKET_IMPLEMENTATION.md)** - Real-time updates
- 🐧 **[Systemd Service](opencv_surveillance/docs/LINUX_SYSTEMD_SERVICE.md)** - Production deployment
- 🔧 **[Quick Reference](docs/QUICK_REFERENCE.md)** - Common tasks

### Project Documentation
- 📝 **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- 👨‍💻 **[CLAUDE.md](CLAUDE.md)** - Developer guide and coding standards
- 🐞 **[Fix History](docs/development/FIXES_HISTORY.md)** - Complete fix history
- 📋 **[Project Roadmap](docs/PROJECT_AUDIT_AND_TODO_v3.5.3.md)** - Planned features and audit

---

## 🎬 First-Run Setup

1. **Access the application**: http://localhost:8000
2. **Create admin account**: Follow the first-run wizard
3. **Add cameras**:
   - Click **"Camera Discovery"** to auto-find cameras
   - Or manually add RTSP/USB cameras
4. **Train face recognition** (optional):
   - Go to **"AI & Faces"** → **"Upload Faces"**
   - Create folders for each person with 3-10 clear photos
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

**Current Version**: 3.7.1 (FFmpeg Hardware Encoding Release)

### Recent Updates (v3.7.1)
- ✅ FFmpeg hardware-accelerated video recording (70-90% CPU reduction)
- ✅ Multi-platform GPU support (NVENC, QuickSync, VideoToolbox, VAAPI)
- ✅ Async frame buffer (300-frame queue, 0% dropped frames)
- ✅ Performance Settings UI in System Settings
- ✅ UI/UX improvements (contrast fixes, Apple HIG compliance)
- ✅ Documentation consolidation (252+ files organized)

### Previous Major Release (v3.6.0 - Security Hardening)
- ✅ Per-endpoint rate limiting with granular API category limits
- ✅ CSRF protection using double-submit cookie pattern
- ✅ Two-factor authentication (2FA) with TOTP support
- ✅ Enhanced audit logging system (42 event types, JSONL format)
- ✅ Face clustering for unknown faces (DBSCAN algorithm)

### Roadmap
See [TODO.md](docs/TODO.md) for complete feature roadmap.

**Next Up** (v3.8.0):
- Two-way audio support (backend complete, frontend pending)
- License plate recognition (ALPR)
- Object detection (YOLO integration)
- Advanced analytics dashboard
- Mobile app (React Native/Flutter)

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

For more help, see [User Guide](opencv_surveillance/docs/USER_GUIDE.md) or open an issue.

---

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

Copyright (c) 2025 Mikel Smart (with help from Claude)

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

**Made with ❤️ by Mikel Smart** | **100% Free Forever** | **No Subscriptions**
