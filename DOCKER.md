# OpenEye - AI-Powered Home Security System

![Version](https://img.shields.io/badge/version-3.11.4-blue.svg) ![License](https://img.shields.io/badge/license-MIT-yellow.svg) ![Cost](https://img.shields.io/badge/cost-$0/month-success.svg)

**100% free and open-source** AI-powered surveillance with face recognition, motion detection, and smart home integration. Your data stays on your hardware - no subscriptions, no cloud dependencies.

🔗 **GitHub**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security
📚 **Full Documentation**: [README.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/README.md)
🚀 **API Documentation**: [API_DOCUMENTATION.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/opencv_surveillance/docs/API_DOCUMENTATION.md)
📝 **Changelog**: [CHANGELOG.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/CHANGELOG.md)

---

## ✨ Key Features

### Core Surveillance
- 🎥 **Multi-Camera Support** - RTSP, USB, network cameras with auto-discovery
- 👤 **AI Face Recognition** - dlib-powered identification with clustering
- 🔍 **Motion Detection** - OpenCV MOG2 algorithm with configurable sensitivity
- 📹 **Auto Recording** - Motion-triggered H.264 video with metadata
- ⚡ **Hardware Encoding** - GPU-accelerated video (70-90% CPU reduction) with NVENC, QuickSync, VideoToolbox, VAAPI
- 🎬 **Live Streaming** - MJPEG with real-time overlays
- 📊 **Timeline View** - Interactive playback with event markers

### User Experience
- 🔎 **Camera Discovery** - Automatic USB/network detection (ONVIF support)
- 🎨 **9 Themes** - Superman, Batman, Wonder Woman, Flash, Aquaman, Cyborg, Green Lantern, Aqua Security, Default
- ❓ **Help System** - 36+ context-sensitive help entries
- 🔐 **First-Run Wizard** - Easy admin account setup
- 📱 **Responsive Design** - Works on desktop, tablet, mobile
- 🧠 **Face Clustering** - DBSCAN-based grouping of unknown faces

### Notifications & Alerts
- 📧 **Email Alerts** - SMTP notifications (FREE with Gmail)
- 📱 **SMS** - Twilio integration
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

**Cost**: $0/month forever • **Privacy**: All data stays local • **Control**: You own everything

---

## 🆕 What's New in v3.11.4 (December 2025)

### 📅 Scheduled Tasks System
- ✅ **Automated Maintenance** - Background scheduler for model retraining, cleanup tasks
- ✅ **Retroactive Face Search** - Re-identify faces in past events after model updates
- ✅ **Database Cleanup** - Remove old detection events and snapshots with configurable retention
- ✅ **Cluster Cleanup** - Remove empty or stale face clusters automatically

### 🔍 MagicMirror Face Search API
- ✅ **Voice Command Support** - "Search for John on December 24th"
- ✅ **Natural Language Dates** - Parses "today", "yesterday", and date formats
- ✅ **Voice Response Generation** - Natural language summaries for voice assistants

### 📊 Ecosystem Statistics
- ✅ **Event Counts API** - Motion, face, recording counts per camera
- ✅ **Configurable Time Range** - Query 1-168 hours of data

### Previous: v3.11.1 (Multi-User & Ecosystem)
- ✅ **Complete Multi-User System** - Role-based access control (admin/user/viewer)
- ✅ **MagicMirror Integration** - Secure token exchange, event streaming
- ✅ **Multi-Device Support** - Smart notification routing

See [CHANGELOG.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/CHANGELOG.md) for full details.

---

## 🚀 Quick Start Guide

### Method 1: One-Command Start (Simplest)

```bash
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

**Access**: http://localhost:8000

---

### Method 2: Docker Compose (Recommended)

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
      # Security Keys (REQUIRED - generate unique keys for production)
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - NOTIFICATION_ENCRYPTION_KEY=${NOTIFICATION_ENCRYPTION_KEY}

      # Authentication Settings
      - ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=30

      # Database (Optional - default is SQLite)
      - DATABASE_URL=sqlite:///./surveillance.db

      # CORS (Optional)
      - CORS_ORIGINS=http://localhost:8000

      # Logging (Optional)
      - LOG_LEVEL=INFO
    restart: unless-stopped

    # Uncomment for NVIDIA GPU acceleration
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

# Optional: PostgreSQL for production (>5 concurrent users)
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
#
#volumes:
#  postgres-data:
```

**Generate Secret Keys** (save in `.env` file):
```bash
# Create .env file with generated keys
cat > .env << EOF
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
NOTIFICATION_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
EOF
```

**Start the stack:**
```bash
docker-compose up -d
```

**View logs:**
```bash
docker-compose logs -f openeye
```

**Stop the stack:**
```bash
docker-compose down
```

---

## 🌐 First-Run Setup

1. **Access the application**: http://localhost:8000
2. **Create admin account**: Follow the setup wizard
3. **Add cameras**:
   - Click **"Camera Discovery"** to auto-find cameras
   - Or manually add RTSP/USB cameras
4. **Train face recognition** (optional):
   - Go to **"AI & Faces"** → **"Upload Faces"**
   - Create folders for each person with 5-10 clear photos
5. **Configure notifications** (optional):
   - Go to **"System & Alerts"** → **"Configure Notification Providers"**
   - Add email, SMS, Telegram, or webhook providers (no coding required!)

**You're ready!** View live cameras on the dashboard.

---

## 🎥 Camera Support

| Camera Type | Docker Support | Example |
|-------------|---------------|---------|
| **RTSP/IP Cameras** | ✅ Full | `rtsp://admin:pass@192.168.1.100:554/stream` |
| **ONVIF Cameras** | ✅ Full | Auto-discovered |
| **USB Webcams** | ⚠️ Linux only | `/dev/video0` |
| **Mock (Testing)** | ✅ Full | Built-in test camera |

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

# Generic
rtsp://username:password@camera-ip:554/stream
```

### ⚠️ macOS Docker Limitation

USB cameras have limited support in Docker on macOS due to USB passthrough limitations.

**Solutions**:
1. **Use Network/IP Cameras** (Recommended - works perfectly!)
2. **Run natively** on macOS (see [README.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security#option-2-local-installation-automated-setup))
3. **Use Linux VM** or native Linux

---

## 📦 Available Tags

- `latest` - Most recent stable release (v3.11.4)
- `v3.11.4` - **Current version** - Scheduled tasks, MagicMirror search API
- `v3.11.1` - Multi-user system, ecosystem integration
- `v3.10.2` - Face detection fix, timeline playback improvements
- `v3.10.0` - Object detection (YOLOv8), two-way audio
- `v3.9.0` - Security hardening, performance optimization
- `v3.7.1` - FFmpeg hardware encoding (70-90% CPU reduction)
- `v3.6.0` - Security hardening (2FA, rate limiting, CSRF protection)

**Recommended**: Use `latest` for automatic updates or specific version tags for production stability.

---

## 🔧 Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **Yes** | - | Application secret key (32+ hex chars) |
| `JWT_SECRET_KEY` | **Yes** | - | JWT signing key (32+ hex chars) |
| `NOTIFICATION_ENCRYPTION_KEY` | **Yes** | - | Fernet key for encrypting notification credentials |
| `ALGORITHM` | No | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Token expiration time |
| `DATABASE_URL` | No | `sqlite:///./surveillance.db` | Database connection string |
| `CORS_ORIGINS` | No | `http://localhost:8000` | Allowed CORS origins (comma-separated) |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Volume Mounts

| Container Path | Purpose | Recommended Host Path |
|---------------|---------|----------------------|
| `/app/data` | Database, thumbnails, snapshots | `./data` |
| `/app/recordings` | Video recordings | `./recordings` |
| `/app/faces` | Face recognition training images | `./faces` |
| `/app/models` | AI models (auto-downloaded) | `./models` |

---

## 🔔 Setting Up Notifications

All notification providers are configured through the **Web UI** - no environment variables or coding required!

1. Go to **"System & Alerts"** → **"Configure Notification Providers"**
2. Click **"Add Provider"** and choose:
   - 📧 **Email (SMTP)** - Gmail, Outlook, custom SMTP
   - 📱 **SMS** - Twilio
   - 💬 **Telegram Bot** - 100% FREE!
   - 🌐 **Discord** - Webhook integration
   - 🔔 **Push Notifications** - Firebase FCM
   - 🪝 **Custom Webhooks** - Any HTTP endpoint

3. Enter credentials (encrypted automatically with Fernet)
4. Test the provider
5. Enable in alert rules

### Quick Setup: Telegram Bot (100% FREE)

1. Create bot with [@BotFather](https://t.me/botfather)
2. Get Chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add provider in OpenEye UI:
   - **Bot Token**: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`
   - **Chat ID**: `123456789`
4. Test and enable!

### Quick Setup: Email (Gmail - FREE)

1. Enable 2FA on your Google account
2. Generate app password: https://myaccount.google.com/apppasswords
3. Add provider in OpenEye UI:
   - **Host**: `smtp.gmail.com`
   - **Port**: `587`
   - **Username**: `your-email@gmail.com`
   - **Password**: `your-16-char-app-password`
4. Test and enable!

---

## 🏠 Smart Home Integration

### Home Assistant (via MQTT)

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

1. Go to **System & Alerts** → **Smart Home**
2. Enable **HomeKit Bridge**
3. Open **Home** app on iOS
4. Tap **+** → **Add Accessory**
5. Scan QR code shown in OpenEye
6. Add motion sensors and occupancy sensors

---

## 🔒 Security Best Practices

1. ✅ **Generate unique secret keys** - Use `openssl rand -hex 32` (never use defaults)
2. ✅ **Strong passwords** - For admin account and camera credentials
3. ✅ **Keep Docker updated** - Run `docker pull im1k31s/openeye-opencv_home_security:latest` regularly
4. ✅ **Use HTTPS** - Behind reverse proxy (nginx, Traefik, Caddy)
5. ✅ **Limit network access** - Configure firewall rules, use VPN for remote access
6. ✅ **Regular backups** - Backup `/app/data`, `/app/recordings`, `/app/faces` volumes
7. ✅ **Monitor logs** - Check `docker-compose logs -f` for errors
8. ✅ **Restrict CORS** - Set `CORS_ORIGINS` to your domain only
9. ✅ **Use PostgreSQL** - For production with >5 concurrent users
10. ✅ **Never commit .env** - Add `.env` to `.gitignore`

### Production Checklist

- [ ] Unique `SECRET_KEY` and `JWT_SECRET_KEY` generated
- [ ] `NOTIFICATION_ENCRYPTION_KEY` generated
- [ ] HTTPS enabled (reverse proxy)
- [ ] CORS_ORIGINS restricted to your domain
- [ ] Firewall rules configured (only allow port 443/8000)
- [ ] Regular backup schedule configured
- [ ] Admin password changed from default
- [ ] PostgreSQL configured for multi-user access
- [ ] Log monitoring enabled

---

## 📊 System Requirements

### Minimum (1-2 cameras)
- **CPU**: Dual-core 2.0GHz
- **RAM**: 2GB
- **Storage**: 20GB + recording space
- **OS**: Linux, macOS, Windows with Docker

### Recommended (3-5 cameras)
- **CPU**: Quad-core 2.5GHz+
- **RAM**: 4GB+
- **Storage**: 100GB+ SSD
- **OS**: Ubuntu 22.04 LTS
- **Network**: Gigabit ethernet

### High-Performance (6+ cameras)
- **CPU**: 8 cores
- **RAM**: 8GB+
- **GPU**: NVIDIA (optional, for acceleration)
- **Storage**: 500GB+ SSD
- **Network**: 10GbE recommended

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

# Check port binding
lsof -i:8000
```

### Camera connection issues

- Verify RTSP URL with VLC: `vlc rtsp://username:password@camera-ip:554/stream`
- Check camera is on same network as Docker host
- Verify credentials (username/password)
- Check firewall rules on camera and host
- Try lower resolution/FPS in camera settings

### High CPU usage

- Lower camera resolution/FPS in camera settings
- Disable face recognition on less important cameras
- Use motion detection zones to ignore busy areas
- Consider GPU acceleration for multiple cameras
- Increase `MOTION_DETECTION_SCALE` to process smaller frames

### Database errors

For production with >5 concurrent users, switch to PostgreSQL:

```yaml
services:
  openeye:
    environment:
      - DATABASE_URL=postgresql://openeye:password@postgres:5432/openeye
    depends_on:
      - postgres

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=openeye
      - POSTGRES_PASSWORD=secure_password
      - POSTGRES_DB=openeye
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  postgres-data:
```

### Permission errors (Linux)

```bash
# Fix volume permissions
sudo chown -R 1000:1000 ./data ./recordings ./faces

# Or run container with your UID
docker run ... -e PUID=$(id -u) -e PGID=$(id -g) ...
```

---

## 📈 Performance Optimization

### For Raspberry Pi 4/5

```yaml
environment:
  - MOTION_DETECTION_SCALE=0.5  # Process 50% size frames
  - RECORDING_FPS=15  # Lower FPS
  - LOG_LEVEL=WARNING  # Reduce log overhead
```

### For NVIDIA GPU Systems

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

Then configure cameras to use GPU acceleration in settings.

### Storage Management

- **Automatic cleanup**: Settings → Storage → Auto-delete recordings after X days
- **Cloud storage**: Configure AWS S3, Azure Blob, or MinIO for offsite backup
- **External drive**: Mount external drive for recordings volume
- **Compression**: Enable H.265 (HEVC) if cameras support it

---

## 🆘 Getting Help

- 📖 **Full Documentation**: [GitHub README](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/README.md)
- 📚 **User Guide**: [USER_GUIDE.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/opencv_surveillance/docs/USER_GUIDE.md)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/discussions)
- 🔧 **API Documentation**: `http://localhost:8000/docs` (Swagger UI after starting)
- ✅ **TODO Roadmap**: [TODO.md](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/TODO.md)

---

## 📄 License

MIT License - Free to use, modify, and distribute.

Copyright (c) 2025 Mikel Smart

---

## ⭐ Support the Project

If you find OpenEye useful:
- ⭐ **Star** the [GitHub repository](https://github.com/M1K31/OpenEye-OpenCV_Home_Security)
- 🐛 **Report bugs** to help improve the project
- 💡 **Suggest features** in [GitHub Discussions](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/discussions)
- 🤝 **Contribute** code or documentation
- 📢 **Share** with others who need free surveillance
- 📝 **Write a review** or blog post about your experience

---

**Made with ❤️ using OpenCV, FastAPI, and React**

*OpenEye - See clearly, secure completely. 100% Free Forever.*
