# OpenEye - Open Source AI Surveillance System

![Version](https://img.shields.io/badge/version-3.1.0-blue.svg) ![License](https://img.shields.io/badge/license-MIT-yellow.svg) ![Cost](https://img.shields.io/badge/cost-$0/month-success.svg)

A **100% free and open-source** AI-powered surveillance system with face recognition, motion detection, and smart home integration. Built with OpenCV, Python, and FastAPI.

---

## 🎯 Project Goal

OpenEye provides a **completely free alternative to expensive cloud-based surveillance systems** like Nest, Ring, or Arlo. Your data stays on your hardware, with no monthly fees, no cloud dependencies, and full control over your privacy.

**Key Benefits:**
- ✅ **$0/month** - No subscriptions ever
- 🔒 **Privacy First** - All data stays local
- 🧠 **AI-Powered** - Advanced face recognition with dlib
- 🏠 **Smart Home Ready** - HomeKit, Home Assistant, Nest integration
- 📱 **Remote Access** - Optional free VPN solutions (WireGuard, Tailscale)
- 🚀 **Production Ready** - Multi-user support, PostgreSQL, rate limiting

---

## ✨ Features

### Core Features
- 🎥 **Multi-Camera Support** - RTSP streams, USB cameras, mock cameras
- 🔍 **Motion Detection** - OpenCV MOG2 background subtraction
- 📹 **Automatic Recording** - Motion-triggered with configurable duration
- 🎬 **Live Streaming** - MJPEG streams with real-time overlays
- 👤 **Face Recognition** - AI-powered person identification
- 💾 **Recording Management** - Search, download, stream, auto-cleanup
- 🔎 **Camera Discovery** - Automatic USB and network camera detection (NEW in v3.1!)
- 📱 **Modern Web UI** - React dashboard with camera management

### Notifications & Alerts
- 📧 **Email Alerts** - SMTP notifications (FREE with Gmail)
- 💬 **SMS Alerts** - Twilio or Telegram Bot (Telegram is FREE!)
- 🔔 **Push Notifications** - Firebase or ntfy.sh (ntfy.sh is FREE!)
- 🎣 **Webhooks** - Custom integrations
- ⏱️ **Alert Throttling** - Configurable cooldown periods

### Smart Home Integration
- 🏠 **Home Assistant** - MQTT integration
- 🍎 **Apple HomeKit** - HomeKit bridge
- 🔥 **Google Nest** - Nest camera integration
- ⚡ **Automation** - Trigger devices on events

### Cloud & Storage (All Optional)
- ☁️ **Cloud Storage** - AWS S3, Google Cloud, Azure, MinIO (FREE!)
- 🗄️ **Database Options** - SQLite (default) or PostgreSQL
- 🌐 **Remote Access** - WireGuard VPN, Tailscale, ZeroTier (FREE!)

### Security & Management
- 👥 **Multi-User System** - Admin, User, Viewer roles
- 🔐 **JWT Authentication** - Secure API access
- 🛡️ **Rate Limiting** - API abuse protection
- 📊 **Advanced Analytics** - Activity tracking and statistics

---

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Pull the image
docker pull im1k31s/openeye-opencv_home_security:latest

# Run with default settings (SQLite database)
docker run -d \
  --name openeye \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/models:/app/models \
  im1k31s/openeye-opencv_home_security:latest

# Access the API documentation
open http://localhost:8000/api/docs
```

### Using Docker Compose

```bash
# Download docker-compose.yml
wget https://raw.githubusercontent.com/M1K31/OpenEye-OpenCV_Home_Security/main/opencv-surveillance/docker-compose.yml

# Create .env file (optional, see configuration below)
cp .env.example .env

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f
```

---

## ⚙️ Configuration

### Environment Variables

The image can be configured using environment variables. All features are **optional** and can be enabled/disabled as needed.

#### Core Settings

```bash
# Security (REQUIRED - change in production!)
SECRET_KEY=your-secret-key-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production

# Application
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
ENABLE_FACE_RECOGNITION=true      # Enable/disable face recognition
MAX_RECORDING_DURATION=300        # Max recording length in seconds
```

#### Database (Optional)

```bash
# Default: SQLite (no configuration needed)
# For PostgreSQL:
DATABASE_URL=postgresql://user:password@postgres:5432/openeye
```

#### Email Notifications (Optional - FREE with Gmail)

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password       # Use Gmail App Password
SMTP_FROM_ADDRESS=your-email@gmail.com
```

**To Enable/Disable:** Set or leave empty. If empty, email alerts are disabled.

#### SMS Notifications (Optional)

**Option 1: Telegram Bot (FREE!)**
```bash
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

**Option 2: Twilio (Paid)**
```bash
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1234567890
```

**To Enable/Disable:** Set or leave empty. If empty, SMS alerts are disabled.

#### Push Notifications (Optional)

**Option 1: ntfy.sh (FREE!)**
```bash
NTFY_TOPIC=your-unique-topic
NTFY_SERVER=https://ntfy.sh
```

**Option 2: Firebase (FREE tier available)**
```bash
FIREBASE_CREDENTIALS_PATH=/app/config/firebase-credentials.json
```

**To Enable/Disable:** Set or leave empty. If empty, push notifications are disabled.

#### Smart Home Integration (Optional)

**Home Assistant (FREE!)**
```bash
MQTT_BROKER=homeassistant.local
MQTT_PORT=1883
MQTT_USERNAME=openeye
MQTT_PASSWORD=your-password
```

**Apple HomeKit (FREE!)**
```bash
HOMEKIT_ENABLED=true
HOMEKIT_PIN=123-45-678
```

**Google Nest (Requires API access)**
```bash
NEST_PROJECT_ID=your-project-id
NEST_CLIENT_ID=your-client-id
NEST_CLIENT_SECRET=your-client-secret
```

**To Enable/Disable:** Set or leave empty. Each integration is independent.

#### Cloud Storage (Optional)

**MinIO (FREE self-hosted)**
```bash
MINIO_ENDPOINT=minio.local:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=openeye-recordings
```

**AWS S3**
```bash
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
```

**Google Cloud Storage**
```bash
GCS_BUCKET=your-bucket-name
GCS_CREDENTIALS_PATH=/app/config/gcs-credentials.json
```

**To Enable/Disable:** Set or leave empty. If empty, recordings stay local only.

---

## 📋 Complete Example with Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  openeye:
    image: im1k31s/openeye-opencv_home_security:latest
    container_name: openeye-surveillance
    ports:
      - "8000:8000"
    environment:
      # REQUIRED: Security keys
      - SECRET_KEY=change-this-in-production-use-long-random-string
      - JWT_SECRET_KEY=change-this-too-use-different-random-string
      
      # Database (optional - defaults to SQLite)
      - DATABASE_URL=sqlite:///./data/openeye.db
      
      # Email (optional - FREE with Gmail)
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USERNAME=your-email@gmail.com
      - SMTP_PASSWORD=your-gmail-app-password
      - SMTP_FROM_ADDRESS=your-email@gmail.com
      
      # Telegram (optional - FREE!)
      - TELEGRAM_BOT_TOKEN=your-bot-token
      - TELEGRAM_CHAT_ID=your-chat-id
      
      # Application settings
      - LOG_LEVEL=INFO
      - ENABLE_FACE_RECOGNITION=true
      - MAX_RECORDING_DURATION=300
    
    volumes:
      - ./data:/app/data           # Recordings, database, logs
      - ./config:/app/config       # Configuration files
      - ./models:/app/models       # Face recognition models
    
    restart: unless-stopped
    
    # Optional: Resource limits
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

Then run:
```bash
docker-compose up -d
```

---

## 🎮 Usage

### Access the API

- **Interactive API Docs:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc
- **Health Check:** http://localhost:8000/api/health
- **Web Dashboard:** http://localhost:8000/ (NEW in v3.1!)

### Discover Cameras Automatically (NEW!)

The easiest way to add cameras is through the Camera Discovery feature:

1. Open the web dashboard: http://localhost:8000/
2. Complete the first-run setup wizard
3. Click "🔍 Discover Cameras" in the dashboard
4. Choose USB or Network scanning:
   - **USB Cameras:** Click "Scan for USB Cameras" to detect webcams
   - **Network Cameras:** Click "Scan Network" to find RTSP/IP cameras (30-60 seconds)
5. Click "Test Connection" to verify camera works
6. Click "Quick Add" to add the camera

**What's Discovered:**
- ✅ USB webcams and built-in cameras
- ✅ RTSP/IP cameras (Hikvision, Dahua, Amcrest, Reolink, etc.)
- ✅ Auto-configured with resolution, FPS, and stream URLs
- ✅ Pre-validated before adding to database

### Add a Camera Manually

You can also add cameras via API or curl:

```bash
curl -X POST "http://localhost:8000/api/cameras/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door",
    "url": "rtsp://camera_ip:554/stream",
    "type": "rtsp",
    "enabled": true
  }'
```

### Register a Face

```bash
# Upload image with person's name
curl -X POST "http://localhost:8000/api/faces/upload" \
  -F "name=John Doe" \
  -F "file=@photo.jpg"
```

### View Live Stream

```
http://localhost:8000/api/cameras/{camera_id}/stream
```

### Enable/Disable Features

Features are controlled via environment variables. To **enable** a feature, set the required environment variables. To **disable** a feature, leave those variables empty or unset them.

**Examples:**

```bash
# Disable face recognition
ENABLE_FACE_RECOGNITION=false

# Disable email alerts (leave SMTP variables empty)
SMTP_USERNAME=
SMTP_PASSWORD=

# Disable cloud storage (leave AWS variables empty)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

---

## 📦 Volumes

The image uses three volumes for persistent data:

| Volume | Purpose | Required |
|--------|---------|----------|
| `/app/data` | Recordings, database, logs | Yes |
| `/app/config` | Configuration files, credentials | Recommended |
| `/app/models` | Face recognition models | Optional |

**Example:**
```bash
docker run -d \
  -v /path/to/data:/app/data \
  -v /path/to/config:/app/config \
  -v /path/to/models:/app/models \
  im1k31s/openeye-opencv_home_security:latest
```

---

## 🌐 Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 8000 | HTTP | API and streaming |

**Example with custom port:**
```bash
docker run -d -p 9000:8000 im1k31s/openeye-opencv_home_security:latest
# Access at http://localhost:9000
```

---

## 🔧 Advanced Configuration

### First-Run Setup (NEW in v3.1!)

On first launch, OpenEye will guide you through an interactive setup wizard:

1. **Welcome Screen**
   - Introduction to OpenEye security features
   - Password requirements overview

2. **Admin Account Creation**
   - Set admin username (default: 'admin')
   - Choose a strong password with:
     * Minimum 12 characters
     * At least one uppercase letter
     * At least one lowercase letter
     * At least one number
     * At least one special character (!@#$%^&*)
   - Real-time password strength indicator (Weak/Fair/Good/Strong)
   - Email address for notifications

3. **Completion**
   - Setup complete confirmation
   - Automatic redirect to login page

**No more auto-generated passwords that need to be reset!** 🎉

### Multi-User Setup

After creating the admin account through the first-run wizard, you can add additional users via API:
```bash
curl -X POST "http://localhost:8000/api/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "viewer",
    "email": "viewer@example.com",
    "password": "secure-password",
    "role": "viewer"
  }'
```

### PostgreSQL Database

For production deployments, use PostgreSQL:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: openeye
      POSTGRES_USER: openeye
      POSTGRES_PASSWORD: secure-password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  openeye:
    image: im1k31s/openeye-opencv_home_security:latest
    depends_on:
      - postgres
    environment:
      - DATABASE_URL=postgresql://openeye:secure-password@postgres:5432/openeye
      # ... other environment variables
    volumes:
      - ./data:/app/data
    ports:
      - "8000:8000"
    restart: unless-stopped

volumes:
  postgres_data:
```

### Remote Access with WireGuard (FREE!)

1. Set up WireGuard VPN on your server
2. Connect from anywhere securely
3. Access OpenEye at http://10.0.0.1:8000

See the [User Guide](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/opencv-surveillance/docs/USER_GUIDE.md) for detailed VPN setup instructions.

---

## 🛠️ Troubleshooting

### Container won't start
```bash
# Check logs
docker logs openeye

# Common issues:
# - SECRET_KEY not set (required!)
# - Port 8000 already in use
# - Insufficient permissions on volumes
```

### Face recognition not working
```bash
# Ensure it's enabled
ENABLE_FACE_RECOGNITION=true

# Check if dlib models are loaded
docker logs openeye | grep "face_recognition"
```

### No alerts received
```bash
# Verify environment variables are set
docker exec openeye env | grep SMTP

# Test email configuration via API
curl -X POST "http://localhost:8000/api/test/email"
```

### High CPU/Memory usage
```bash
# Limit resources in docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```

---

## 📚 Documentation

- **[GitHub Repository](https://github.com/M1K31/OpenEye-OpenCV_Home_Security)**
- **[User Guide](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/opencv-surveillance/docs/USER_GUIDE.md)** - Complete setup guide
- **[API Documentation](http://localhost:8000/api/docs)** - Interactive API reference
- **[Uninstall Guide](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/opencv-surveillance/docs/UNINSTALL_GUIDE.md)** - Removal instructions

---

## 💡 Tips

### Recommended Free Services

1. **Notifications:** Use Telegram Bot (100% free, no limits)
2. **VPN:** WireGuard or Tailscale (both free!)
3. **Storage:** MinIO self-hosted (free unlimited)
4. **Smart Home:** Home Assistant (free and powerful)
5. **Email:** Gmail with App Password (free tier sufficient)

### Cost Breakdown

| Service | Cost | Alternative |
|---------|------|-------------|
| Surveillance software | **$0** | Nest ($6-20/month) |
| Face recognition | **$0** | AWS Rekognition (pay per use) |
| Cloud storage | **$0** (local) | Ring ($3-10/month) |
| Notifications | **$0** (Telegram) | Push services ($5+/month) |
| Remote access | **$0** (WireGuard) | Cloud subscriptions ($10+/month) |
| Smart home | **$0** (Home Assistant) | Proprietary ecosystems ($$) |

**Total: $0/month forever** vs. **$24-45+/month** for commercial alternatives

---

## 🤝 Contributing

Contributions are welcome! Please visit our [GitHub repository](https://github.com/M1K31/OpenEye-OpenCV_Home_Security) to:
- Report bugs
- Request features
- Submit pull requests
- Star the project ⭐

---

## 📄 License

MIT License - Free to use, modify, and distribute.

---

## 🙏 Support

- **Issues:** [GitHub Issues](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues)
- **Discussions:** [GitHub Discussions](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/discussions)
- **Documentation:** [Wiki](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/wiki)

---

## ⭐ Star the Project

If you find OpenEye useful, please consider giving it a star on [GitHub](https://github.com/M1K31/OpenEye-OpenCV_Home_Security)!

---

**Built with ❤️ by the open-source community**
