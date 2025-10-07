# OpenEye - Free AI Surveillance System

![Version](https://img.shields.io/badge/version-3.1.0-blue.svg) ![License](https://img.shields.io/badge/license-MIT-yellow.svg) ![Cost](https://img.shields.io/badge/cost-$0/month-success.svg)

**100% free and open-source** AI-powered surveillance with face recognition, motion detection, and smart home integration. Your data stays on your hardware - no subscriptions, no cloud dependencies.

🔗 **GitHub**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security  
📚 **Full Documentation**: See DOCKER_DEPLOYMENT_GUIDE.md in the repository

---

## ✨ Key Features

- 🎥 **Multi-Camera Support** - RTSP, USB, network cameras
- 👤 **Face Recognition** - AI-powered with dlib
- 🔍 **Motion Detection** - OpenCV MOG2
- 📹 **Auto Recording** - Motion-triggered capture
- 🔎 **Camera Discovery** - Automatic USB/network detection (v3.1.0)
- 🎨 **8 Themes** - Customizable superhero-inspired UI
- ❓ **Help System** - 36+ inline help entries
- 🔐 **First-Run Wizard** - Easy admin setup
- 📧 **Free Alerts** - Email, Telegram, ntfy.sh
- 🏠 **Smart Home** - HomeKit, Home Assistant integration
- 👥 **Multi-User** - Admin, User, Viewer roles

**Cost**: $0/month forever • **Privacy**: All data stays local • **Control**: You own everything

---

## 🚀 Quick Start Guide

### ⚠️ IMPORTANT: Generate Secret Keys First

Before running, you MUST generate secure random keys:

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

Keep these keys safe - you'll need them in the next steps!

---

## 📦 Method 1: Docker Run (Command Line)

**Step 1: Generate keys** (see above)

**Step 2: Run the container**
```bash
docker run -d \
  --name openeye \
  -p 8000:8000 \
  -v ./data:/app/data \
  -v ./config:/app/config \
  -v ./models:/app/models \
  -e SECRET_KEY=your-generated-secret-key-here \
  -e JWT_SECRET_KEY=your-generated-jwt-secret-key-here \
  im1k31s/openeye-opencv_home_security:latest
```

**Step 3: Access OpenEye**
- Open browser: `http://localhost:8000`
- Complete the first-run setup wizard
- Create your admin account with a strong password

---

## 🐳 Method 2: Docker Compose (Recommended)

**Step 1: Create docker-compose.yml**
```yaml
version: '3.8'

services:
  openeye:
    image: im1k31s/openeye-opencv_home_security:latest
    container_name: openeye
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=your-generated-secret-key-here
      - JWT_SECRET_KEY=your-generated-jwt-secret-key-here
      # Optional: Add email/Telegram/ntfy.sh settings
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USERNAME=your-email@gmail.com
      - SMTP_PASSWORD=your-gmail-app-password
      - TELEGRAM_BOT_TOKEN=your-bot-token
      - TELEGRAM_CHAT_ID=your-chat-id
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./models:/app/models
    restart: unless-stopped
```

**Step 2: Start the service**
```bash
docker-compose up -d
```

**Step 3: View logs**
```bash
docker-compose logs -f openeye
```

---

## 🖥️ Method 3: Docker Desktop (GUI)

Perfect for users who prefer a graphical interface!

### Step 1: Generate Secret Keys
Use Terminal/PowerShell/Command Prompt to generate keys (see "Generate Secret Keys" section above). **Save these keys** - you'll paste them in Step 5!

### Step 2: Pull the Image
1. Open **Docker Desktop**
2. Go to **Images** tab
3. Click **Pull** or search icon
4. Enter: `im1k31s/openeye-opencv_home_security:latest`
5. Click **Pull** and wait (~1.75GB download)

### Step 3: Run the Container
1. Find the image in the **Images** list
2. Click the **▶ Run** button (play icon)
3. Click **Optional settings** to expand

### Step 4: Configure Container
**Container name:** `openeye`

**Ports:**
- Click **+** to add port mapping
- Host Port: `8000`
- Container Port: `8000`

**Volumes** (click **+** three times):
1. Data: Host `C:\openeye\data` (Windows) or `/Users/yourname/openeye/data` (Mac) → Container `/app/data`
2. Config: Host `C:\openeye\config` or `/Users/yourname/openeye/config` → Container `/app/config`
3. Models: Host `C:\openeye\models` or `/Users/yourname/openeye/models` → Container `/app/models`

### Step 5: Environment Variables (CRITICAL!)
Click the **Environment** tab and add:

**Required:**
```
SECRET_KEY=paste-your-generated-key-from-step-1
JWT_SECRET_KEY=paste-your-other-generated-key-from-step-1
```

**Optional (for notifications):**
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### Step 6: Start Container
1. Review all settings
2. Click **Run** at the bottom
3. Go to **Containers** tab
4. Wait for green "Running" status

### Step 7: Access OpenEye
1. Open browser: `http://localhost:8000`
2. Complete the first-run setup wizard
3. Start using OpenEye!

---

## 🔐 Environment Variables Explained

### Required (Security)

| Variable | Purpose | Example |
|----------|---------|---------|
| `SECRET_KEY` | Session management, CSRF protection, database encryption | `a1b2c3d4e5f6...` (64 chars) |
| `JWT_SECRET_KEY` | API authentication tokens, user sessions | `9876543210fe...` (64 chars) |

**⚠️ CRITICAL**: Without these, authentication will fail! Generate with `openssl rand -hex 32`.

### Optional (Notifications - All FREE!)

**Gmail Alerts:**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password  # Get from myaccount.google.com/apppasswords
SMTP_FROM_ADDRESS=your-email@gmail.com
```

**Telegram Alerts (Recommended - FREE!):**
```bash
TELEGRAM_BOT_TOKEN=your-bot-token  # Get from @BotFather
TELEGRAM_CHAT_ID=your-chat-id      # Get from @userinfobot
```

**ntfy.sh Push Notifications (FREE!):**
```bash
NTFY_TOPIC=openeye-alerts-unique-name
NTFY_SERVER=https://ntfy.sh
```

---

## 📖 First-Run Setup (v3.1.0)

When you first access OpenEye at `http://localhost:8000`, you'll see the **First-Run Setup Wizard**:

**Step 1: Welcome** - Introduction and security overview

**Step 2: Create Admin Account**
- Choose username (default: `admin`)
- Enter email address
- Create **strong password** (12+ chars, complexity required):
  - At least one uppercase letter
  - At least one lowercase letter
  - At least one number
  - At least one special character
- Real-time password strength indicator

**Step 3: Complete** - Setup confirmation, auto-redirect to login

**No more auto-generated passwords!** You control your admin credentials from day one.

---

## 🎯 What's New in v3.1.0

### Camera Discovery
- **USB Camera Scanning**: Automatically detect connected webcams
- **Network Camera Discovery**: ONVIF protocol support for IP cameras
- **One-Click Setup**: No manual RTSP URL configuration needed

### Theme System
Choose from 8 superhero-inspired themes:
- Sman (Classic red/blue)
- Bman (Dark knight)
- W Woman (Warrior gold)
- Flah (Speed red)
- Aman (Ocean teal)
- Cy (Tech silver)
- G Lantern (Willpower green)
- Default (Professional blue)

### Help System
- 36+ inline help entries
- Context-sensitive help buttons (?)
- Theme-aware tooltips
- Covers all features and settings

### First-Run Setup
- Interactive 3-step wizard
- Strong password enforcement
- Real-time validation
- No auto-generated passwords

---

## 🛠️ Common Commands

```bash
# View logs
docker logs openeye -f

# Restart container
docker restart openeye

# Stop container
docker stop openeye

# Update to latest version
docker pull im1k31s/openeye-opencv_home_security:latest
docker stop openeye && docker rm openeye
# Then run the docker run command again with your keys

# Shell access (troubleshooting)
docker exec -it openeye bash
```

---

## 🆘 Troubleshooting

**Container won't start?**
- Check logs: `docker logs openeye`
- Verify SECRET_KEY and JWT_SECRET_KEY are set
- Ensure port 8000 isn't in use

**Can't access http://localhost:8000?**
- Wait 30 seconds for startup
- Check container status: `docker ps | grep openeye`
- Try `http://127.0.0.1:8000` instead
- Check firewall settings

**First-run setup not loading?**
- Check logs: `docker logs openeye | grep setup`
- Verify database connection
- Ensure volumes are mounted correctly

**Face recognition not working?**
- Enable in environment: `ENABLE_FACE_RECOGNITION=true`
- Upload 3-5 clear face photos per person
- Train the model after adding photos

---

## 📚 Full Documentation

For complete deployment guides, configuration options, and advanced features:

- **Complete Docker Guide**: See `DOCKER_DEPLOYMENT_GUIDE.md` in repository
- **User Guide**: `opencv-surveillance/docs/USER_GUIDE.md`
- **API Documentation**: `http://localhost:8000/api/docs` (when running)
- **GitHub Repository**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security

---

## 🔒 Security Best Practices

✅ Always generate unique SECRET_KEY and JWT_SECRET_KEY  
✅ Use different values for each key  
✅ Never commit keys to version control  
✅ Rotate keys periodically  
✅ Use strong passwords (enforced by setup wizard)  
✅ Enable HTTPS with reverse proxy for production  
✅ Keep Docker images updated  
✅ Regular backups of `/app/data` directory  

---

## 💡 Why OpenEye?

| Feature | OpenEye | Nest/Ring/Arlo |
|---------|---------|----------------|
| **Monthly Cost** | $0 | $10-30/month |
| **Cloud Dependency** | None | Required |
| **Privacy** | 100% local | Cloud-based |
| **Customization** | Full control | Limited |
| **Smart Home** | Free integrations | Paid/limited |
| **Storage** | Unlimited (your hardware) | Limited cloud |
| **API Access** | Full REST API | Limited/paid |

**Total 5-year cost**: OpenEye = $0 | Cloud services = $600-$1,800+

---

## 🤝 Support & Community

- 📖 **Documentation**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security
- 🐛 **Bug Reports**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues
- 💬 **Discussions**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/discussions

---

## 📄 License

MIT License - Free for personal and commercial use

---

**OpenEye v3.1.0** - Built with ❤️ by the open-source community

*Your security, your data, your control - at $0/month forever*
