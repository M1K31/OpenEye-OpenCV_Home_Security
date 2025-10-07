# OpenEye User Guide - Phase 6

## 🎉 Welcome to OpenEye 3.0!

OpenEye is a **completely free and open-source** home surveillance system. All core features work without any paid services!

---

## 🆓 100% Free Features (No Sign-ups Required)

### Core Surveillance
- ✅ **Multi-camera support** - Monitor unlimited cameras
- ✅ **Motion detection** - Automatic detection and recording
- ✅ **Face recognition** - Identify known people
- ✅ **Video recording** - Save footage locally
- ✅ **Live streaming** - Watch cameras in real-time
- ✅ **Analytics dashboard** - View activity patterns

### Security & Access
- ✅ **Multi-user support** - Create admin, user, and viewer accounts
- ✅ **Rate limiting** - Protect against API abuse
- ✅ **SQL injection protection** - Built-in security
- ✅ **HTTPS/SSL support** - Secure connections (with free Let's Encrypt)

### Storage & Database
- ✅ **SQLite** (default) - Works out of the box
- ✅ **PostgreSQL** - Free production database
- ✅ **Local storage** - Save recordings on your hard drive

### Notifications (Free Options)
- ✅ **Email** - Use Gmail or any SMTP server (free)
- ✅ **Telegram Bot** - Free instant messages
- ✅ **ntfy.sh** - Free push notifications (open source)

### Remote Access (Free Options)
- ✅ **WireGuard VPN** - Free, secure remote access
- ✅ **Tailscale** - Free for up to 20 devices
- ✅ **ZeroTier** - Free for up to 25 devices

---

## 💎 Optional Paid Services

These are completely optional - OpenEye works perfectly without them!

### Cloud Storage (Optional)
Use these if you want off-site backup:

| Service | Free Tier | Paid Cost | When to Use |
|---------|-----------|-----------|-------------|
| **AWS S3** | 5GB for 12 months | ~$0.023/GB/month | Large scale, enterprise |
| **Google Cloud** | 5GB always free | ~$0.020/GB/month | Google ecosystem |
| **Azure Blob** | 5GB for 12 months | ~$0.018/GB/month | Microsoft ecosystem |
| **MinIO** | ✅ FREE (self-hosted) | $0 | Recommended free alternative! |

**Recommendation**: Use **MinIO** (100% free, runs on your server)

### SMS Notifications (Optional)
Only needed if you want text messages:

| Service | Free Tier | Paid Cost | When to Use |
|---------|-----------|-----------|-------------|
| **Twilio** | $15 trial credit | ~$0.0075/SMS | Professional SMS |
| **Telegram** | ✅ FREE | $0 | **Use this instead!** |

**Recommendation**: Use **Telegram Bot** (completely free)

### Push Notifications (Optional)
For mobile app notifications:

| Service | Free Tier | Paid Cost | When to Use |
|---------|-----------|-----------|-------------|
| **Firebase** | Unlimited | $0 | Mobile apps, Google services |
| **ntfy.sh** | ✅ FREE | $0 | **Recommended!** Open source |

**Recommendation**: Use **ntfy.sh** (no registration required!)

### Remote Access (Optional)
If you need access outside your home:

| Service | Free Tier | Paid Cost | When to Use |
|---------|-----------|-----------|-------------|
| **WireGuard** | ✅ FREE | $0 | **Best option!** Self-hosted VPN |
| **Tailscale** | 20 devices | $5/user/month | Easy setup, managed |
| **ZeroTier** | 25 devices | $5/network/month | Alternative to Tailscale |
| **Cloudflare Tunnel** | FREE | $7/user/month for Zero Trust | If you have a domain |

**Recommendation**: Use **WireGuard** (completely free, most secure)

---

## 📖 Quick Start Guide

### 1. Installation

```bash
# Navigate to project
cd opencv-surveillance

# Install dependencies (all free!)
pip install -r requirements.txt

# Start the server
python -m backend.main
```

### 2. First Login

1. Open browser: `http://localhost:8000/api/docs`
2. Create your first user account
3. Login to get access token

### 3. Add a Camera

```bash
curl -X POST "http://localhost:8000/api/cameras/add" \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "front_door",
    "camera_type": "rtsp",
    "source": "rtsp://your-camera-ip:554/stream"
  }'
```

### 4. View Live Stream

Open: `http://localhost:8000/api/cameras/front_door/stream`

---

## 🔧 Configuration Guide

### Email Notifications (FREE)

Edit `.env`:
```bash
# Using Gmail (free)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Generate in Gmail settings
SMTP_FROM=openeye@yourdomain.com
```

**How to get Gmail App Password**:
1. Go to Google Account → Security
2. Enable 2-Step Verification
3. App Passwords → Generate new password
4. Copy password to `.env` file

### Telegram Bot (FREE - Recommended!)

1. **Create Bot**:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot`
   - Follow prompts to create bot
   - Save the token

2. **Get Chat ID**:
   - Message your bot
   - Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find `"chat":{"id":` and copy the number

3. **Configure OpenEye**:
```bash
# Add to .env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

4. **Enable in code**:
```python
# backend/services/notification_service.py
async def send_telegram_alert(message: str):
    import requests
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": message})
```

### PostgreSQL Database (FREE - Production)

1. **Install PostgreSQL**:
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql
```

2. **Create Database**:
```bash
sudo -u postgres psql
CREATE DATABASE openeye_db;
CREATE USER openeye WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE openeye_db TO openeye;
\q
```

3. **Update `.env`**:
```bash
DATABASE_URL=postgresql://openeye:your_secure_password@localhost:5432/openeye_db
```

### WireGuard VPN (FREE - Remote Access)

1. **Install WireGuard**:
```bash
# Ubuntu/Debian
sudo apt-get install wireguard

# macOS
brew install wireguard-tools
```

2. **Generate Keys**:
```bash
wg genkey | tee privatekey | wg pubkey > publickey
```

3. **Configure Server** (`/etc/wireguard/wg0.conf`):
```ini
[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = <SERVER_PRIVATE_KEY>

[Peer]
PublicKey = <CLIENT_PUBLIC_KEY>
AllowedIPs = 10.0.0.2/32
```

4. **Start VPN**:
```bash
sudo wg-quick up wg0
```

5. **Access OpenEye**:
   - Connect to VPN from phone/laptop
   - Access: `http://10.0.0.1:8000`

---

## 🎛️ User Roles & Permissions

OpenEye supports three user roles:

### Admin
**Full system control**:
- ✅ Add/remove cameras
- ✅ Manage all users
- ✅ Delete recordings
- ✅ Configure integrations
- ✅ View all analytics

### User
**Standard access**:
- ✅ View cameras
- ✅ Add faces
- ✅ View recordings
- ✅ View analytics
- ❌ Cannot manage other users

### Viewer
**Read-only access**:
- ✅ View cameras
- ✅ View recordings
- ✅ View analytics
- ❌ Cannot modify anything

### Creating Users with Roles

```bash
curl -X POST "http://localhost:8000/api/users/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john",
    "email": "john@example.com",
    "password": "secure_password",
    "role": "user"
  }'
```

---

## 📊 Using Analytics

### View Activity Dashboard

```bash
# Hourly activity breakdown
curl "http://localhost:8000/api/analytics/activity/hourly?days=7"

# Summary statistics
curl "http://localhost:8000/api/analytics/summary"
```

### Manage Recordings

```bash
# List all recordings
curl "http://localhost:8000/api/recordings/"

# List recordings with faces
curl "http://localhost:8000/api/recordings/?has_faces=true"

# Get storage statistics
curl "http://localhost:8000/api/recordings/storage/stats"

# Clean up old recordings (keep last 30 days)
curl -X POST "http://localhost:8000/api/recordings/cleanup?days_to_keep=30"
```

---

## 🔒 Security Best Practices

### 1. Use Strong Passwords
```bash
# Generate secure password
openssl rand -base64 32
```

### 2. Enable HTTPS (FREE with Let's Encrypt)
```bash
# Install certbot
sudo apt-get install certbot

# Get free SSL certificate
sudo certbot certonly --standalone -d your-domain.com

# Certificates saved to:
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem
```

### 3. Change Default Settings

Edit `.env`:
```bash
# Generate new JWT secret
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Set secure database password
DB_PASSWORD=$(openssl rand -base64 32)
```

### 4. Enable IP Whitelist (Optional)

In `backend/main.py`, uncomment:
```python
app.add_middleware(IPWhitelistMiddleware, allowed_ips=["127.0.0.1", "192.168.1.100"])
```

### 5. Regular Backups

```bash
# Backup database (PostgreSQL)
pg_dump -U openeye openeye_db > backup_$(date +%Y%m%d).sql

# Backup recordings
tar -czf recordings_backup.tar.gz recordings/

# Or use free cloud backup with MinIO
```

---

## 🐳 Docker Deployment (Easiest Option)

### Quick Start with Docker

```bash
# Build and start all services (PostgreSQL, Redis, OpenEye)
docker-compose -f docker-compose.yml up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### What's Included:
- ✅ PostgreSQL database (free)
- ✅ Redis cache (free)
- ✅ OpenEye backend (free)
- ✅ Nginx reverse proxy (free)
- ✅ Auto-restart on failure
- ✅ Persistent storage

---

## 🆘 Troubleshooting

### Cannot Connect to Camera

**Problem**: `Failed to open camera stream`

**Solutions**:
1. Check camera is on same network
2. Verify RTSP URL: `ffplay rtsp://camera-ip:554/stream`
3. Check firewall allows port 554
4. Try different stream URL (check camera manual)

### High CPU Usage

**Problem**: Server slowing down

**Solutions**:
1. Use `hog` face detection instead of `cnn`:
```python
# In camera config
face_detection_model = "hog"  # Faster, less accurate
# or
face_detection_model = "cnn"  # Slower, more accurate
```

2. Reduce frame rate:
```python
fps = 10  # Process 10 frames per second instead of 30
```

3. Add more cameras gradually

### Storage Full

**Problem**: Running out of disk space

**Solutions**:
1. Clean old recordings:
```bash
curl -X POST "http://localhost:8000/api/recordings/cleanup?days_to_keep=7"
```

2. Move to external drive:
```bash
# Create symlink
sudo ln -s /mnt/external/recordings ./recordings
```

3. Use cloud storage (MinIO)

### Cannot Access Remotely

**Problem**: Can't access from phone/outside network

**Solutions**:
1. **Use WireGuard VPN** (recommended, free)
2. Forward port 8000 on router (less secure)
3. Use Tailscale/ZeroTier (easy, free tier)
4. Use Cloudflare Tunnel (free, requires domain)

---

## 📱 Mobile App Usage

### Android/iOS App

1. **Install App**: See `mobile/README.md`

2. **Configure Server**:
   - Open app settings
   - Enter server URL: `http://your-server-ip:8000`
   - Or if using VPN: `http://10.0.0.1:8000`

3. **Login**: Use your OpenEye credentials

4. **View Cameras**: Tap camera to view live stream

5. **Receive Notifications**:
   - Enable notifications in app
   - Server will send alerts for motion/faces

---

## 💡 Cost Comparison

### Minimal Setup (FREE)
**Monthly Cost: $0**
- SQLite database
- Local storage
- Email notifications
- Run on your own hardware

### Cloud Backup Setup (LOW COST)
**Monthly Cost: ~$5**
- PostgreSQL (free)
- MinIO self-hosted (free)
- Or AWS S3 5GB (~$0.12/month)
- Telegram notifications (free)
- VPS for remote access (~$5/month)

### Premium Setup (OPTIONAL)
**Monthly Cost: ~$15-20**
- PostgreSQL (free)
- AWS S3 100GB (~$2/month)
- Twilio SMS (~$5/month)
- Firebase (free)
- VPS with more resources (~$10-15/month)

**Recommendation**: Start with the free setup!

---

## 🎓 Advanced Topics

### Running 24/7 on Raspberry Pi

```bash
# Optimize for Pi
pip install opencv-python-headless  # Lighter version

# Use less CPU
face_detection_model = "hog"
recording_fps = 10
```

### Adding Custom Alerts

Edit `backend/services/notification_service.py`:
```python
async def send_custom_alert(camera_id: str, message: str):
    # Your custom notification logic
    # Examples: Discord webhook, Slack, custom API
    pass
```

### Integrating with Home Assistant

See `backend/integrations/homeassistant_integration.py` for full MQTT integration.

---

## 🤝 Getting Help

- **Documentation**: `/docs/` folder
- **API Reference**: `http://localhost:8000/api/docs`
- **GitHub Issues**: Report bugs
- **Community**: Join discussions

---

## 📝 Quick Reference

### Common Commands

```bash
# Start server
python -m backend.main

# Check API status
curl http://localhost:8000/api/health

# List cameras
curl http://localhost:8000/api/cameras/

# View recordings
curl http://localhost:8000/api/recordings/

# Get analytics
curl http://localhost:8000/api/analytics/summary

# Clean old recordings
curl -X POST "http://localhost:8000/api/recordings/cleanup?days_to_keep=30"
```

### Important Files

- **Configuration**: `.env`
- **Database**: `surveillance.db`
- **Recordings**: `recordings/`
- **Logs**: `backend.log`
- **Face Images**: `faces/`

---

## ✅ Checklist for New Users

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Copy `.env.example` to `.env`
- [ ] Generate JWT secret: `openssl rand -hex 32`
- [ ] Configure email or Telegram (free!)
- [ ] Create admin user
- [ ] Add first camera
- [ ] Test notifications
- [ ] Setup remote access (WireGuard recommended)
- [ ] Configure automatic backups
- [ ] Enable HTTPS with Let's Encrypt (free)

---

**Congratulations! You're now running a professional surveillance system with $0/month in service costs!** 🎉
