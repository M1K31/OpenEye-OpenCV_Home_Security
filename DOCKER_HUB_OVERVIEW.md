# OpenEye - Advanced Home Security System

![Version](https://img.shields.io/badge/version-3.3.8-blue.svg) ![License](https://img.shields.io/badge/license-MIT-yellow.svg) ![Cost](https://img.shields.io/badge/cost-$0/month-success.svg)

**100% free and open-source** AI-powered surveillance with face recognition, motion detection, and smart home integration. Your data stays on your hardware - no subscriptions, no cloud dependencies.

🔗 **GitHub**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security  
📚 **Full Documentation**: [README.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/README.md)  
🚀 **API Documentation**: [API_DOCUMENTATION.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/opencv-surveillance/docs/API_DOCUMENTATION.md)  
📝 **Changelog**: [CHANGELOG.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/CHANGELOG.md)  
📝 **Release Notes**: [v3.3.7](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/RELEASE_NOTES_v3.3.7.md)

---

## ✨ Key Features

### Core Surveillance
- 🎥 **Multi-Camera Support** - RTSP, USB, network cameras
- 👤 **AI Face Recognition** - dlib-powered identification
- 🔍 **Motion Detection** - OpenCV MOG2 algorithm
- 📹 **Auto Recording** - Motion-triggered with metadata
- 🎬 **Live Streaming** - MJPEG with real-time overlays
- 📊 **Detection History** - Full event tracking

### User Experience (v3.1.0+)
- 🔎 **Camera Discovery** - Automatic USB/network detection
- 🎨 **8 Superhero Themes** - Customizable UI (Superman, Batman, etc.)
- ❓ **Help System** - 36+ inline help entries
- 🔐 **First-Run Wizard** - Easy admin setup
- 📱 **Responsive Design** - Works on any device

### Integrations
- 📧 **Free Alerts** - Email (Gmail), Telegram Bot, ntfy.sh
- 🏠 **Smart Home** - HomeKit, Home Assistant (MQTT)
- ☁️ **Cloud Storage** - AWS S3, Azure, MinIO (self-hosted)
- 👥 **Multi-User** - Admin, User, Viewer roles

**Cost**: $0/month forever • **Privacy**: All data stays local • **Control**: You own everything

---

## 🚀 Quick Start Guide

### ⚠️ IMPORTANT: Generate Secret Keys First

Before running, you **MUST** generate secure random keys:

**Mac/Linux:**
```bash
openssl rand -hex 32  # SECRET_KEY
openssl rand -hex 32  # JWT_SECRET_KEY
```

**Windows (PowerShell):**
```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

**Python (All Platforms):**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Online Tool** (use at your own risk): https://www.uuidgenerator.net/

---

### 🐳 Docker Run

**Simple start (for testing only - generates random keys):**
```bash
docker run -d \
  --name openeye \
  -p 8000:8000 \
  -v ~/openeye-data:/app/data \
  -v ~/openeye-recordings:/app/recordings \
  -v ~/openeye-faces:/app/faces \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -e JWT_SECRET_KEY=$(openssl rand -hex 32) \
  im1k31s/openeye-opencv_home_security:latest
```

**Production start (recommended):**
```bash
docker run -d \
  --name openeye \
  -p 8000:8000 \
  -v ~/openeye-data:/app/data \
  -v ~/openeye-recordings:/app/recordings \
  -v ~/openeye-faces:/app/faces \
  -e SECRET_KEY=your_generated_secret_key_here \
  -e JWT_SECRET_KEY=your_generated_jwt_secret_here \
  -e ALGORITHM=HS256 \
  -e ACCESS_TOKEN_EXPIRE_MINUTES=30 \
  --restart unless-stopped \
  im1k31s/openeye-opencv_home_security:latest
```

---

### 🐳 Docker Compose (Recommended)

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
      # REQUIRED: Replace with your generated keys
      - SECRET_KEY=your_generated_secret_key_here
      - JWT_SECRET_KEY=your_generated_jwt_secret_here
      
      # Authentication settings
      - ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=30
      
      # Optional: Email notifications
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USERNAME=your-email@gmail.com
      - SMTP_PASSWORD=your-app-password
      - SMTP_FROM_EMAIL=your-email@gmail.com
      
      # Optional: Telegram notifications (100% FREE!)
      - TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
      - TELEGRAM_CHAT_ID=123456789
      
      # Optional: Database (default is SQLite)
      # - DATABASE_URL=postgresql://user:pass@postgres:5432/openeye
    restart: unless-stopped
    # Uncomment for GPU acceleration (if available)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

# Optional: PostgreSQL for production
#  postgres:
#    image: postgres:15-alpine
#    container_name: openeye-db
#    environment:
#      - POSTGRES_USER=openeye
#      - POSTGRES_PASSWORD=secure_password_here
#      - POSTGRES_DB=openeye
#    volumes:
#      - postgres-data:/var/lib/postgresql/data
#    restart: unless-stopped

#volumes:
#  postgres-data:
```

**Start the stack:**
```bash
docker-compose up -d
```

**View logs:**
```bash
docker-compose logs -f
```

**Stop the stack:**
```bash
docker-compose down
```

---

## 🌐 Access the Application

1. **Open your browser** to: `http://localhost:8000`
2. **Follow first-run wizard** to create admin account
3. **Add cameras** via auto-discovery or manual configuration
4. **Upload faces** for recognition
5. **Customize** theme and settings

---

## 🎥 Camera Support

| Camera Type | Docker Support | Example |
|-------------|---------------|---------|
| **RTSP/IP Cameras** | ✅ Full | `rtsp://admin:pass@192.168.1.100:554/stream` |
| **ONVIF Cameras** | ✅ Full | Auto-discovered |
| **USB Webcams** | ⚠️ Linux only | `/dev/video0` |
| **Mock (Testing)** | ✅ Full | Built-in test camera |

### ⚠️ macOS Docker Limitation

USB cameras have limited support in Docker on macOS due to USB passthrough limitations. **Solutions**:

1. **Use Network/IP Cameras** (Recommended)
2. **Run backend natively** on macOS (not in Docker)
3. **Use USB/IP forwarding** (experimental)
4. **Develop on Linux** VM or native Linux

**Network cameras work perfectly** on all platforms including macOS!

### Common RTSP URLs

```bash
# Hikvision
rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101

# Dahua
rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0

# Amcrest
rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1

# Reolink
rtsp://admin:password@192.168.1.100:554/h264Preview_01_main
```

---

## 📦 Available Tags

- `latest` - Most recent stable release
- `3.3.0` - Current version (bug fixes and stability)
- `3.2.8` - Previous stable version
- `3.1.0` - Camera discovery and themes release
- `3.0.0` - Initial release

**Recommended**: Use `latest` for automatic updates or specific version tags for stability.

---

## 🔧 Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **Yes** | - | Application secret key (generate with openssl) |
| `JWT_SECRET_KEY` | **Yes** | - | JWT signing key (generate with openssl) |
| `ALGORITHM` | No | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Token expiration time |
| `DATABASE_URL` | No | `sqlite:///./surveillance.db` | Database connection string |
| `SMTP_HOST` | No | - | Email server hostname |
| `SMTP_PORT` | No | `587` | Email server port |
| `SMTP_USERNAME` | No | - | Email username |
| `SMTP_PASSWORD` | No | - | Email password |
| `SMTP_FROM_EMAIL` | No | - | Email from address |
| `TELEGRAM_BOT_TOKEN` | No | - | Telegram bot token |
| `TELEGRAM_CHAT_ID` | No | - | Telegram chat ID |

### Volume Mounts

| Container Path | Purpose | Recommended Host Path |
|---------------|---------|----------------------|
| `/app/data` | Database, thumbnails, config | `./data` |
| `/app/recordings` | Video recordings | `./recordings` |
| `/app/faces` | Face recognition images | `./faces` |
| `/app/models` | AI models (optional) | `./models` |

---

## 🔔 Setting Up Notifications

### Email (Gmail - FREE)

1. Enable 2FA on your Google account
2. Generate app password: https://myaccount.google.com/apppasswords
3. Add to `docker-compose.yml`:

```yaml
environment:
  - SMTP_HOST=smtp.gmail.com
  - SMTP_PORT=587
  - SMTP_USERNAME=your-email@gmail.com
  - SMTP_PASSWORD=your-16-char-app-password
  - SMTP_FROM_EMAIL=your-email@gmail.com
```

### Telegram Bot (100% FREE)

1. Create bot with [@BotFather](https://t.me/botfather)
2. Get Chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add to `docker-compose.yml`:

```yaml
environment:
  - TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
  - TELEGRAM_CHAT_ID=123456789
```

### ntfy.sh Push (100% FREE)

1. Choose unique topic: `openeye-yourname-alerts`
2. Configure in web UI (no environment variables needed)
3. Subscribe on phone: Download [ntfy app](https://ntfy.sh/)

---

## 🏠 Smart Home Integration

### Home Assistant

Add to `configuration.yaml`:

```yaml
mqtt:
  sensor:
    - name: "Front Door Motion"
      state_topic: "openeye/front_door/motion"
      
    - name: "Front Door Face"
      state_topic: "openeye/front_door/face"

automation:
  - alias: "Alert on Unknown Face"
    trigger:
      platform: state
      entity_id: sensor.front_door_face
      to: "unknown"
    action:
      service: notify.mobile_app
      data:
        message: "Unknown person at front door"
```

### Apple HomeKit

1. Enable HomeKit in OpenEye settings
2. Open **Home** app on iOS
3. Tap **+** → **Add Accessory**
4. Scan QR code shown in OpenEye
5. Add motion sensors and occupancy sensors

---

## 🔒 Security Best Practices

1. ✅ **Always generate unique secret keys** - Never use defaults
2. ✅ **Use strong passwords** - For admin account and cameras
3. ✅ **Keep Docker updated** - `docker pull` regularly
4. ✅ **Use HTTPS** - Behind reverse proxy (nginx, Traefik)
5. ✅ **Limit network access** - Firewall rules, VPN
6. ✅ **Regular backups** - Data, recordings, database
7. ✅ **Monitor logs** - `docker-compose logs -f`

---

## 📊 System Requirements

### Minimum

- **CPU**: 2 cores
- **RAM**: 2GB
- **Storage**: 20GB + recording space
- **OS**: Linux, macOS, Windows with Docker

### Recommended

- **CPU**: 4 cores or more
- **RAM**: 4GB or more
- **Storage**: 100GB+ SSD
- **OS**: Ubuntu 22.04 LTS
- **Network**: Gigabit ethernet

### For Multiple Cameras

- **CPU**: 8 cores
- **RAM**: 8GB
- **GPU**: NVIDIA (optional, for acceleration)

---

## 🐛 Troubleshooting

### Can't access web interface

```bash
# Check if container is running
docker ps

# Check logs
docker logs openeye

# Restart container
docker restart openeye
```

### Camera connection issues

- Verify RTSP URL with VLC or ffmpeg
- Check camera is on same network
- Verify credentials (username/password)
- Check firewall rules

### High CPU usage

- Lower camera resolution/FPS
- Disable face recognition on less important cameras
- Use motion detection zones
- Consider GPU acceleration

### Database errors

For production with >5 users, switch to PostgreSQL:

```yaml
services:
  openeye:
    environment:
      - DATABASE_URL=postgresql://openeye:password@postgres:5432/openeye
  
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=openeye
      - POSTGRES_PASSWORD=secure_password
      - POSTGRES_DB=openeye
    volumes:
      - postgres-data:/var/lib/postgresql/data
```

---

## 📈 Performance Optimization

### For Raspberry Pi

```yaml
environment:
  - FACE_DETECTION_MODEL=hog  # Faster, less accurate
  - MOTION_DETECTION_SCALE=0.5  # Process smaller frames
  - RECORDING_FPS=15  # Lower FPS
```

### For GPU Systems

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

### Storage Management

- Enable automatic cleanup: Settings → Storage → Auto-delete after X days
- Use cloud storage: AWS S3, MinIO, etc.
- Mount external drive for recordings

---

## 🆕 What's New in v3.3.0

### Critical Bug Fixes
- ✅ Fixed async/await context issues in camera threads
- ✅ Fixed missing camera_id attribute causing identification errors
- ✅ Standardized password hashing across all code paths
- ✅ Added automatic directory creation on startup
- ✅ Implemented thread-safe camera management
- ✅ Fixed face detection metadata not being saved to recordings
- ✅ Added database schema consistency verification

### Improvements
- Better error handling for motion alerts
- Enhanced thread safety preventing race conditions
- Improved metadata tracking for face detections
- More robust first-run experience

See full [CHANGELOG.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/CHANGELOG.md)

---

## 🆘 Getting Help

- 📖 **Documentation**: [GitHub README](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/README.md)
- 📚 **User Guide**: [User Guide](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/opencv-surveillance/docs/USER_GUIDE.md)
- 🐛 **Issues**: [GitHub Issues](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/discussions)
- 🔧 **API Docs**: `http://localhost:8000/api/docs` (after starting)

---

## 📄 License

MIT License - Free to use, modify, and distribute.

---

## ⭐ Support the Project

If you find OpenEye useful:
- ⭐ **Star** the [GitHub repository](https://github.com/M1K31/OpenEye-OpenCV_Home_Security)
- 🐛 **Report bugs** to help improve the project
- 💡 **Suggest features** in GitHub Discussions
- 🤝 **Contribute** code or documentation
- 📢 **Share** with others who need free surveillance

---

**Made with ❤️ using OpenCV and AI**

*OpenEye - See clearly, secure completely. 100% Free Forever.*
