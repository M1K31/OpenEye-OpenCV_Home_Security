# Docker Deployment Guide for OpenEye v3.1.0

This guide covers deploying OpenEye using Docker with the new first-run setup wizard.

## Table of Contents
- [Quick Start](#quick-start)
  - [Using Docker Run](#using-docker-run)
  - [Using Docker Compose](#using-docker-compose)
  - [Using Docker Desktop (GUI)](#using-docker-desktop-gui)
- [First-Run Setup](#first-run-setup)
- [Configuration](#configuration)
  - [Understanding SECRET_KEY and JWT_SECRET_KEY](#understanding-secret_key-and-jwt_secret_key)
  - [Optional Environment Variables](#optional-environment-variables)
- [Docker Compose](#docker-compose)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

> **⚠️ IMPORTANT**: Before starting, you MUST set `SECRET_KEY` and `JWT_SECRET_KEY` environment variables for security. See the [Configuration](#understanding-secret_key-and-jwt_secret_key) section for details.

### Using Docker Run

```bash
# STEP 1: Generate secure random keys (REQUIRED)
export SECRET_KEY=$(openssl rand -hex 32)
export JWT_SECRET_KEY=$(openssl rand -hex 32)

# STEP 2: Pull the latest image
docker pull im1k31s/openeye-opencv_home_security:latest

# STEP 3: Run with your generated keys
docker run -d \
  --name openeye \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/models:/app/models \
  -e SECRET_KEY=$SECRET_KEY \
  -e JWT_SECRET_KEY=$JWT_SECRET_KEY \
  im1k31s/openeye-opencv_home_security:latest
```

### Using Docker Compose

```bash
# Clone repository or download docker-compose.yml
git clone https://github.com/M1K31/OpenEye.git
cd OpenEye/opencv-surveillance

# Copy environment file
cp .env.example .env

# IMPORTANT: Generate and add secret keys to .env file
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)" >> .env

# Edit .env with any additional settings (see Configuration section)
nano .env

# Start services
docker-compose up -d

# View logs
docker-compose logs -f openeye
```

### Using Docker Desktop (GUI)

Perfect for users who prefer a graphical interface! Follow these step-by-step instructions:

#### Step 1: Generate Secret Keys

First, generate your required secret keys. Open Terminal (Mac/Linux) or PowerShell (Windows):

**Mac/Linux:**
```bash
openssl rand -hex 32
# Copy the output - this is your SECRET_KEY

openssl rand -hex 32
# Copy the output - this is your JWT_SECRET_KEY
```

**Windows (PowerShell):**
```powershell
# Generate SECRET_KEY
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))

# Generate JWT_SECRET_KEY
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

**Alternative: Use Python (All platforms):**
```bash
python -c "import secrets; print('SECRET_KEY:', secrets.token_hex(32))"
python -c "import secrets; print('JWT_SECRET_KEY:', secrets.token_hex(32))"
```

Keep these keys somewhere safe - you'll need them in the next steps!

#### Step 2: Pull the Image

1. Open **Docker Desktop**
2. Click on the **Images** tab in the left sidebar
3. Click **Pull** (or the search icon)
4. Enter: `im1k31s/openeye-opencv_home_security:latest`
5. Click **Pull**
6. Wait for the download to complete (~1.75GB)

![Docker Desktop Pull Image](https://via.placeholder.com/800x400?text=Docker+Desktop+-+Pull+Image)

#### Step 3: Run the Container

1. In Docker Desktop, go to **Images** tab
2. Find `im1k31s/openeye-opencv_home_security:latest`
3. Click the **▶ Run** button (play icon) on the right
4. Click **Optional settings** to expand the configuration panel

#### Step 4: Configure Container Settings

**Container Name:**
```
openeye
```

**Ports:**
- Click **+** to add a port mapping
- Host Port: `8000`
- Container Port: `8000`

**Volumes (Data Persistence):**
Click **+** three times to add these volume mappings:

1. **For recordings and data:**
   - Host Path: `/path/to/your/data` (e.g., `/Users/yourname/openeye/data`)
   - Container Path: `/app/data`

2. **For configuration files:**
   - Host Path: `/path/to/your/config` (e.g., `/Users/yourname/openeye/config`)
   - Container Path: `/app/config`

3. **For face recognition models:**
   - Host Path: `/path/to/your/models` (e.g., `/Users/yourname/openeye/models`)
   - Container Path: `/app/models`

> 💡 **Tip**: Create these folders on your computer first. Docker Desktop will create them automatically if they don't exist, but it's better to know where they are!

**Windows Example Paths:**
```
C:\Users\YourName\openeye\data
C:\Users\YourName\openeye\config
C:\Users\YourName\openeye\models
```

**Mac/Linux Example Paths:**
```
/Users/yourname/openeye/data
/Users/yourname/openeye/config
/Users/yourname/openeye/models
```

#### Step 5: Add Environment Variables

This is the **MOST IMPORTANT** step! Click on the **Environment** tab and add these variables:

**Required (Security Keys):**
```
SECRET_KEY=<paste-your-generated-key-from-step-1>
JWT_SECRET_KEY=<paste-your-other-generated-key-from-step-1>
```

**Example:**
```
SECRET_KEY=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
JWT_SECRET_KEY=9876543210fedcba0987654321fedcba0987654321fedcba0987654321fedcba
```

**Optional (Add if you want email/Telegram notifications):**

For Gmail notifications:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM_ADDRESS=your-email@gmail.com
```

For Telegram notifications:
```
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

For ntfy.sh push notifications:
```
NTFY_TOPIC=openeye-alerts-unique-name
NTFY_SERVER=https://ntfy.sh
```

#### Step 6: Start the Container

1. Review all your settings
2. Click **Run** at the bottom
3. Docker Desktop will create and start your container

#### Step 7: Verify It's Running

1. Go to the **Containers** tab in Docker Desktop
2. You should see `openeye` with a green "Running" status
3. Click on the container name to see logs
4. Look for: `Application startup complete` or `Uvicorn running on http://0.0.0.0:8000`

#### Step 8: Access OpenEye

1. Open your web browser
2. Navigate to: `http://localhost:8000`
3. You'll see the **First-Run Setup Wizard** 🎉
4. Follow the 3-step wizard to create your admin account
5. Start using OpenEye!

#### Troubleshooting Docker Desktop

**Container won't start?**
- Check the logs by clicking on the container name
- Verify you added both `SECRET_KEY` and `JWT_SECRET_KEY`
- Make sure port 8000 isn't already in use

**Can't access http://localhost:8000?**
- Wait 30 seconds for the application to fully start
- Check the container is running (green status)
- Try `http://127.0.0.1:8000` instead
- Check your firewall settings

**Need to change environment variables?**
1. Stop the container (click ■ stop button)
2. Delete the container (click 🗑️ delete button)
3. Start over from Step 3 with new settings

**Want to see what's happening?**
- Click on the container name in the Containers tab
- Click the **Logs** tab to see real-time output
- Click the **Inspect** tab to see configuration
- Click the **Stats** tab to see resource usage

#### Video Tutorial

**Visual Learner?** Check out this quick video guide:
1. Pull Image → 2. Configure Settings → 3. Add Environment Variables → 4. Run Container → 5. Complete Setup Wizard

> 📹 *Video tutorial coming soon! Check the GitHub repository for updates.*

---

## First-Run Setup

### New in v3.1.0: Interactive Setup Wizard! 🎉

OpenEye v3.1.0 introduces a user-friendly setup wizard that runs on first launch:

1. **Start the container:**
   ```bash
   docker-compose up -d
   ```

2. **Open your browser:**
   Navigate to `http://localhost:8000/`

3. **Complete the 3-step wizard:**
   
   **Step 1: Welcome**
   - Introduction to OpenEye
   - Overview of security features
   
   **Step 2: Create Admin Account**
   - Choose username (default: 'admin')
   - Enter email address
   - Create strong password:
     * Minimum 12 characters
     * At least one uppercase letter
     * At least one lowercase letter
     * At least one number
     * At least one special character
   - Real-time password strength indicator
   
   **Step 3: Complete**
   - Setup confirmation
   - Automatic redirect to login

4. **Login and start using OpenEye!**
   You'll be redirected to the login page. Use the credentials you just created.

### What Changed?

**Old Way (v3.0.0 and earlier):**
- Auto-generated admin password
- Had to find password in logs
- Forced password reset on first login
- Confusing for new users

**New Way (v3.1.0):**
- ✅ Interactive setup wizard
- ✅ Choose your own password
- ✅ Real-time validation
- ✅ Password strength indicator
- ✅ No password reset needed
- ✅ Better user experience

---

## Configuration

### Required Environment Variables

#### Understanding SECRET_KEY and JWT_SECRET_KEY

**Both keys are REQUIRED for security and proper operation.**

##### SECRET_KEY
- **Purpose**: Used for general application security, including:
  - Session management
  - Cookie signing
  - CSRF protection
  - Database encryption
  - Secure token generation
  
- **Required**: YES - The application will not function properly without it
- **Default**: If not set, a random key is generated on startup (NOT recommended for production as it changes on restart)
- **Security Impact**: If compromised, attackers could:
  - Forge session cookies
  - Bypass CSRF protection
  - Access encrypted data

##### JWT_SECRET_KEY
- **Purpose**: Used specifically for JSON Web Token (JWT) authentication:
  - API authentication tokens
  - User login sessions
  - Token validation and signing
  - Prevents token tampering
  
- **Required**: YES - User authentication will fail without it
- **Default**: If not set, uses SECRET_KEY as fallback (NOT recommended)
- **Security Impact**: If compromised, attackers could:
  - Forge authentication tokens
  - Impersonate any user
  - Bypass authentication entirely

##### Important Security Notes

**⚠️ CRITICAL:**
- Never use the same value for both keys
- Never commit these keys to version control
- Never share these keys publicly
- Change these keys if you suspect they've been compromised

**🔒 Best Practices:**
- Use different random values for each key
- Use at least 64 characters (32 bytes hex)
- Store keys in environment variables, not in code
- Rotate keys periodically (requires re-authentication)
- Use a secrets manager in production (AWS Secrets Manager, HashiCorp Vault, etc.)

##### Generate Secure Random Keys

**Method 1: OpenSSL (Recommended)**
```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate JWT_SECRET_KEY
openssl rand -hex 32
```

**Method 2: Python**
```bash
# Generate both keys
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32)); print('JWT_SECRET_KEY=' + secrets.token_hex(32))"
```

**Method 3: Online (Use with caution)**
```bash
# Visit https://www.random.org/strings/ and generate two random strings
# Length: 64, Unique: Yes, Format: hex
```

##### Example Configuration

**Development (for testing only):**
```bash
SECRET_KEY=dev-secret-key-not-for-production-use-123456
JWT_SECRET_KEY=dev-jwt-secret-key-not-for-production-use-123456
```

**Production (always generate new random keys):**
```bash
SECRET_KEY=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
JWT_SECRET_KEY=9876543210fedcba0987654321fedcba0987654321fedcba0987654321fedcba
```

---

### Optional Environment Variables

#### Email Notifications (FREE with Gmail)

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM_ADDRESS=your-email@gmail.com
```

**Gmail App Password Setup:**
1. Enable 2FA on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate an app password for "OpenEye"
4. Use that password in `SMTP_PASSWORD`

#### Telegram Bot (FREE - Recommended!)

```bash
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

**Setup Guide:**
1. Talk to [@BotFather](https://t.me/botfather) on Telegram
2. Create new bot: `/newbot`
3. Copy the token to `TELEGRAM_BOT_TOKEN`
4. Talk to [@userinfobot](https://t.me/userinfobot) to get your chat ID
5. Copy your ID to `TELEGRAM_CHAT_ID`

#### ntfy.sh Push Notifications (FREE!)

```bash
NTFY_TOPIC=openeye-alerts-unique-name
NTFY_SERVER=https://ntfy.sh
```

**Setup Guide:**
1. Choose a unique topic name
2. Subscribe on phone: https://ntfy.sh/docs/subscribe/phone/
3. Subscribe to your topic: `openeye-alerts-unique-name`

#### Twilio SMS (Paid)

```bash
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1234567890
```

#### Firebase Push Notifications

```bash
FIREBASE_CREDENTIALS_PATH=/app/config/firebase-credentials.json
```

Mount your credentials file:
```bash
-v $(pwd)/firebase-credentials.json:/app/config/firebase-credentials.json
```

#### Database Options

**SQLite (Default - no configuration needed):**
```bash
DATABASE_URL=sqlite:///./data/openeye.db
```

**PostgreSQL (Recommended for production):**
```bash
DATABASE_URL=postgresql://user:password@postgres:5432/openeye
```

#### Cloud Storage

**MinIO (FREE self-hosted):**
```bash
MINIO_ENDPOINT=minio.local:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=openeye-recordings
```

**AWS S3:**
```bash
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
```

**Google Cloud Storage:**
```bash
GCS_BUCKET=your-bucket-name
GCS_CREDENTIALS_PATH=/app/config/gcs-credentials.json
```

#### Application Settings

```bash
LOG_LEVEL=INFO                      # DEBUG, INFO, WARNING, ERROR
ENABLE_FACE_RECOGNITION=true        # Enable/disable face recognition
MAX_RECORDING_DURATION=300          # Max recording length in seconds
```

---

## Docker Compose

### Basic Configuration

Create `.env` file:
```bash
# Security (REQUIRED)
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Email (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_ADDRESS=your-email@gmail.com

# Telegram (Optional - FREE!)
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### Production Configuration with PostgreSQL

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: openeye-postgres
    environment:
      POSTGRES_DB: openeye
      POSTGRES_USER: openeye
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - openeye-network
    restart: unless-stopped

  openeye:
    image: im1k31s/openeye-opencv_home_security:latest
    container_name: openeye-surveillance
    depends_on:
      - postgres
    ports:
      - "8000:8000"
    environment:
      # Database
      - DATABASE_URL=postgresql://openeye:${POSTGRES_PASSWORD}@postgres:5432/openeye
      
      # Security (REQUIRED)
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      
      # Email (Optional)
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_PORT=${SMTP_PORT}
      - SMTP_USERNAME=${SMTP_USERNAME}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
      - SMTP_FROM_ADDRESS=${SMTP_FROM_ADDRESS}
      
      # Telegram (Optional)
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
      
      # Application
      - LOG_LEVEL=INFO
      - ENABLE_FACE_RECOGNITION=true
    
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./models:/app/models
    
    networks:
      - openeye-network
    
    restart: unless-stopped
    
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

volumes:
  postgres_data:

networks:
  openeye-network:
    driver: bridge
```

Start production stack:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Production Deployment

### Security Checklist

- [ ] Change default SECRET_KEY and JWT_SECRET_KEY
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable HTTPS with reverse proxy (Nginx/Traefik)
- [ ] Set up firewall rules
- [ ] Use strong passwords (enforced by setup wizard)
- [ ] Enable backups for data directory
- [ ] Monitor logs regularly
- [ ] Keep Docker images updated

### Reverse Proxy with Nginx

Create `nginx.conf`:

```nginx
server {
    listen 80;
    server_name openeye.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name openeye.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/openeye.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/openeye.yourdomain.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket support for live streams
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Automated Backups

Create `backup.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/backups/openeye"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup data directory
tar -czf $BACKUP_DIR/openeye-data-$DATE.tar.gz ./data

# Backup database (if PostgreSQL)
docker exec openeye-postgres pg_dump -U openeye openeye > $BACKUP_DIR/openeye-db-$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "openeye-*" -mtime +7 -delete

echo "Backup completed: $DATE"
```

Add to crontab:
```bash
0 2 * * * /path/to/backup.sh
```

### Monitoring

Check container health:
```bash
docker ps
docker logs openeye
docker stats openeye
```

View application logs:
```bash
docker exec openeye tail -f /app/data/logs/openeye.log
```

---

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker logs openeye
```

**Common issues:**
- SECRET_KEY not set → Set in .env file
- Port 8000 in use → Change port: `-p 8080:8000`
- Permission denied → Check volume permissions: `chmod -R 755 ./data`

### Setup Wizard Not Loading

**Check if container is running:**
```bash
docker ps | grep openeye
```

**Access directly:**
```bash
curl http://localhost:8000/api/setup/status
```

**Expected response:**
```json
{"setup_complete": false}
```

### Can't Complete Setup

**Check backend logs:**
```bash
docker logs openeye | grep setup
```

**Verify database connection:**
```bash
docker exec openeye ls -la /app/data/
```

### Face Recognition Not Working

**Check if enabled:**
```bash
docker exec openeye env | grep ENABLE_FACE_RECOGNITION
```

**Check models:**
```bash
docker exec openeye ls -la /app/models/
```

### High CPU/Memory Usage

**Limit resources in docker-compose.yml:**
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```

**Check running processes:**
```bash
docker exec openeye ps aux
```

### Database Issues

**SQLite locked:**
```bash
# Check for multiple processes
docker exec openeye fuser /app/data/openeye.db
```

**PostgreSQL connection failed:**
```bash
# Check PostgreSQL container
docker logs openeye-postgres

# Test connection
docker exec openeye pg_isready -h postgres -U openeye
```

### Network Issues

**Can't access from other devices:**
```bash
# Check firewall
sudo ufw status
sudo ufw allow 8000

# Check binding
docker exec openeye netstat -tuln | grep 8000
```

**Camera streams not loading:**
```bash
# Check network connectivity
docker exec openeye ping -c 3 camera-ip

# Check camera accessibility
docker exec openeye curl -I rtsp://camera-ip:554/stream
```

---

## Useful Commands

### Container Management

```bash
# Start container
docker-compose up -d

# Stop container
docker-compose down

# Restart container
docker-compose restart

# View logs
docker-compose logs -f

# Shell access
docker exec -it openeye bash

# Update to latest version
docker-compose pull
docker-compose up -d
```

### Database Operations

```bash
# SQLite backup
docker exec openeye sqlite3 /app/data/openeye.db ".backup /app/data/backup.db"

# PostgreSQL backup
docker exec openeye-postgres pg_dump -U openeye openeye > backup.sql

# PostgreSQL restore
cat backup.sql | docker exec -i openeye-postgres psql -U openeye openeye
```

### Maintenance

```bash
# Clean up old recordings
docker exec openeye find /app/data/recordings -mtime +30 -delete

# Check disk usage
docker exec openeye du -sh /app/data/*

# View active cameras
curl http://localhost:8000/api/cameras/ | jq

# Check system health
curl http://localhost:8000/api/health
```

---

## Next Steps

After successful deployment:

1. **Complete first-run setup** at http://localhost:8000/
2. **Add cameras** using the Camera Discovery feature
3. **Configure notifications** (Email, Telegram, ntfy.sh)
4. **Upload faces** for recognition
5. **Set up remote access** (WireGuard VPN)
6. **Configure backups** (see Production Deployment)
7. **Enable HTTPS** for security

For detailed guides, see:
- [User Guide](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/blob/main/opencv-surveillance/docs/USER_GUIDE.md)
- [API Documentation](http://localhost:8000/api/docs)
- [GitHub Repository](https://github.com/M1K31/OpenEye-OpenCV_Home_Security)

---

**OpenEye v3.1.0** - Built with ❤️ by the open-source community
