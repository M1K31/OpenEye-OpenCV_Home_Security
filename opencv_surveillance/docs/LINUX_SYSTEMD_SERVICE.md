# Linux Systemd Service Setup Guide

**Version:** 3.3.8  
**Date:** October 9, 2025  
**Purpose:** Run OpenEye as a system service on Linux with auto-start and auto-restart capabilities

---

## Overview

This guide shows how to set up OpenEye to run as a **systemd service** on Linux, providing:

- ✅ **Auto-start on boot** - OpenEye starts automatically when system boots
- ✅ **Auto-restart on failure** - Service restarts automatically if it crashes
- ✅ **Easy management** - Simple commands to start/stop/restart
- ✅ **Centralized logging** - Logs accessible via `journalctl`
- ✅ **Resource limits** - Optional CPU/memory limits
- ✅ **Production-ready** - Suitable for 24/7 operation

---

## Prerequisites

- Linux system with systemd (Ubuntu 16.04+, Debian 8+, CentOS 7+, etc.)
- OpenEye already installed (see [README.md](../../README.md))
- Root/sudo access

---

## Quick Setup

### 1. Create System User (Recommended for Security)

```bash
# Create dedicated user for OpenEye
sudo useradd -r -s /bin/false -m -d /opt/openeye openeye

# Set ownership of OpenEye files
sudo chown -R openeye:openeye /opt/openeye
```

### 2. Move Installation to /opt/openeye (Recommended)

```bash
# If you installed in your home directory, move it:
sudo mv ~/OpenEye-OpenCV_Home_Security /opt/openeye/
sudo chown -R openeye:openeye /opt/openeye
```

### 3. Create Systemd Service File

```bash
sudo nano /etc/systemd/system/openeye.service
```

**Copy and paste this configuration:**

```ini
[Unit]
Description=OpenEye Surveillance System
Documentation=https://github.com/M1K31/OpenEye-OpenCV_Home_Security
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=openeye
Group=openeye
WorkingDirectory=/opt/openeye/opencv-surveillance

# Python virtual environment
Environment="PATH=/opt/openeye/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"

# Load environment variables from .env file
EnvironmentFile=/opt/openeye/opencv-surveillance/.env

# Start command
ExecStart=/opt/openeye/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Restart policy
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/openeye/opencv-surveillance/data
ReadWritePaths=/opt/openeye/opencv-surveillance/recordings
ReadWritePaths=/opt/openeye/opencv-surveillance/models

# Resource limits (optional)
# LimitNOFILE=65535
# MemoryLimit=2G
# CPUQuota=200%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=openeye

[Install]
WantedBy=multi-user.target
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

### 4. Create Required Directories

```bash
sudo -u openeye mkdir -p /opt/openeye/opencv-surveillance/{data,recordings,models}
sudo -u openeye mkdir -p /opt/openeye/opencv-surveillance/data/{faces,thumbnails}
```

### 5. Set Up Python Virtual Environment

```bash
# If you haven't already:
cd /opt/openeye/opencv-surveillance
sudo -u openeye python3 -m venv /opt/openeye/venv
sudo -u openeye /opt/openeye/venv/bin/pip install --upgrade pip
sudo -u openeye /opt/openeye/venv/bin/pip install -r requirements.txt
```

### 6. Configure Environment Variables

```bash
sudo -u openeye nano /opt/openeye/opencv-surveillance/.env
```

**Minimum required:**
```bash
# Security (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here

# Database
DATABASE_URL=sqlite:///./data/openeye.db

# Server
HOST=0.0.0.0
PORT=8000

# Optional: Notification settings
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your_email@gmail.com
# SMTP_PASSWORD=your_app_password
# NOTIFICATION_EMAIL=alerts@yourdomain.com
```

### 7. Reload Systemd and Enable Service

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable openeye

# Start service now
sudo systemctl start openeye

# Check status
sudo systemctl status openeye
```

---

## Service Management Commands

### Basic Commands

```bash
# Start OpenEye
sudo systemctl start openeye

# Stop OpenEye
sudo systemctl stop openeye

# Restart OpenEye
sudo systemctl restart openeye

# Check status
sudo systemctl status openeye

# Enable auto-start on boot
sudo systemctl enable openeye

# Disable auto-start on boot
sudo systemctl disable openeye
```

### Viewing Logs

```bash
# View all logs
sudo journalctl -u openeye

# Follow logs in real-time (like tail -f)
sudo journalctl -u openeye -f

# View logs since boot
sudo journalctl -u openeye -b

# View last 100 lines
sudo journalctl -u openeye -n 100

# View logs from specific time
sudo journalctl -u openeye --since "2025-10-09 10:00:00"
sudo journalctl -u openeye --since "1 hour ago"
sudo journalctl -u openeye --since today
```

### Checking Service Health

```bash
# Check if service is running
sudo systemctl is-active openeye

# Check if service is enabled
sudo systemctl is-enabled openeye

# Check service status
sudo systemctl status openeye

# Test HTTP endpoint
curl http://localhost:8000/api/health
```

---

## Advanced Configuration

### 1. Resource Limits

Uncomment and adjust these lines in the service file:

```ini
[Service]
# Limit open files
LimitNOFILE=65535

# Limit memory usage to 2GB
MemoryLimit=2G

# Limit CPU usage to 200% (2 cores)
CPUQuota=200%

# Limit number of processes
TasksMax=100
```

### 2. Security Hardening

Additional security options:

```ini
[Service]
# Prevent privilege escalation
NoNewPrivileges=true

# Private /tmp directory
PrivateTmp=true

# Make filesystem read-only except specified paths
ProtectSystem=strict
ReadWritePaths=/opt/openeye/opencv-surveillance/data
ReadWritePaths=/opt/openeye/opencv-surveillance/recordings

# Restrict access to /home
ProtectHome=true

# Restrict network access
# RestrictAddressFamilies=AF_INET AF_INET6

# Prevent access to kernel logs
ProtectKernelLogs=true

# Prevent kernel module loading
ProtectKernelModules=true
```

### 3. Network Configuration

Run on different port or bind to specific IP:

```ini
[Service]
# Run on port 8080 instead of 8000
ExecStart=/opt/openeye/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080

# Bind only to localhost (require reverse proxy)
ExecStart=/opt/openeye/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### 4. Multiple Workers (Production)

For better performance with multiple CPU cores:

```ini
[Service]
# Run with 4 worker processes
ExecStart=/opt/openeye/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Note:** Adjust `--workers` based on CPU cores. Recommended: `2 × CPU cores + 1`

---

## Nginx Reverse Proxy (Recommended for Production)

### 1. Install Nginx

```bash
sudo apt-get update
sudo apt-get install nginx
```

### 2. Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/openeye
```

**Configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP

    # Redirect HTTP to HTTPS (after SSL is set up)
    # return 301 https://$server_name$request_uri;

    # Client body size limit for file uploads
    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (for future WebSocket implementation)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (if serving directly)
    location /static {
        alias /opt/openeye/opencv-surveillance/frontend/dist;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 3. Enable Site and Restart Nginx

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/openeye /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### 4. Set Up SSL with Let's Encrypt (Optional but Recommended)

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is set up automatically
```

---

## Updating OpenEye

### Manual Update Process

```bash
# Stop service
sudo systemctl stop openeye

# Switch to openeye user
sudo -u openeye -s

# Navigate to installation
cd /opt/openeye/opencv-surveillance

# Backup database
cp data/openeye.db data/openeye.db.backup

# Pull latest changes
git pull origin main

# Update Python dependencies
/opt/openeye/venv/bin/pip install -r requirements.txt

# Update frontend
cd frontend
npm install
npm run build
cd ..

# Exit openeye user shell
exit

# Restart service
sudo systemctl restart openeye

# Check status
sudo systemctl status openeye
```

### Automated Update Script

Create `/opt/openeye/scripts/update.sh`:

```bash
#!/bin/bash
set -e

echo "🔄 Stopping OpenEye service..."
sudo systemctl stop openeye

echo "💾 Backing up database..."
sudo -u openeye cp /opt/openeye/opencv-surveillance/data/openeye.db \
                    /opt/openeye/opencv-surveillance/data/openeye.db.backup-$(date +%Y%m%d-%H%M%S)

echo "📥 Pulling latest changes..."
cd /opt/openeye/opencv-surveillance
sudo -u openeye git pull origin main

echo "🐍 Updating Python dependencies..."
sudo -u openeye /opt/openeye/venv/bin/pip install -r requirements.txt

echo "📦 Building frontend..."
cd frontend
sudo -u openeye npm install
sudo -u openeye npm run build
cd ..

echo "🚀 Starting OpenEye service..."
sudo systemctl start openeye

echo "✅ Update complete!"
sudo systemctl status openeye
```

Make it executable:
```bash
sudo chmod +x /opt/openeye/scripts/update.sh
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check status and logs
sudo systemctl status openeye -l
sudo journalctl -u openeye -n 50 --no-pager

# Common issues:
# 1. Python path wrong - check Environment= line
# 2. Missing dependencies - reinstall requirements.txt
# 3. Port already in use - check: sudo netstat -tulpn | grep 8000
# 4. Permission issues - check: sudo ls -la /opt/openeye
```

### Permission Errors

```bash
# Fix ownership
sudo chown -R openeye:openeye /opt/openeye

# Fix permissions
sudo chmod -R 755 /opt/openeye
sudo chmod -R 755 /opt/openeye/opencv-surveillance/data
```

### Service Crashes Immediately

```bash
# Check for Python errors
sudo journalctl -u openeye -n 100 --no-pager | grep -i error

# Test manually as openeye user
sudo -u openeye -s
cd /opt/openeye/opencv-surveillance
/opt/openeye/venv/bin/python -m backend.main
```

### Port Already in Use

```bash
# Find what's using port 8000
sudo netstat -tulpn | grep 8000

# Kill the process (replace PID)
sudo kill -9 <PID>

# Or change OpenEye port in service file
```

### Database Locked

```bash
# Check for stale lock
sudo -u openeye fuser /opt/openeye/opencv-surveillance/data/openeye.db

# Remove if necessary (ensure service is stopped!)
sudo systemctl stop openeye
sudo rm -f /opt/openeye/opencv-surveillance/data/openeye.db-shm
sudo rm -f /opt/openeye/opencv-surveillance/data/openeye.db-wal
```

---

## Monitoring

### Health Check Script

Create `/opt/openeye/scripts/healthcheck.sh`:

```bash
#!/bin/bash

# Check if service is running
if ! systemctl is-active --quiet openeye; then
    echo "❌ OpenEye service is not running!"
    exit 1
fi

# Check HTTP endpoint
if ! curl -f -s http://localhost:8000/api/health > /dev/null; then
    echo "❌ OpenEye HTTP endpoint not responding!"
    exit 1
fi

echo "✅ OpenEye is healthy"
exit 0
```

### Cron Job for Monitoring

```bash
# Add to crontab
sudo crontab -e

# Check every 5 minutes
*/5 * * * * /opt/openeye/scripts/healthcheck.sh || systemctl restart openeye
```

---

## Backup & Restore

### Backup Script

Create `/opt/openeye/scripts/backup.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/opt/openeye/backups"
DATE=$(date +%Y%m%d-%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
cp /opt/openeye/opencv-surveillance/data/openeye.db \
   $BACKUP_DIR/openeye-db-$DATE.db

# Backup .env file
cp /opt/openeye/opencv-surveillance/.env \
   $BACKUP_DIR/env-$DATE.backup

# Backup face recognition data
tar -czf $BACKUP_DIR/faces-$DATE.tar.gz \
   /opt/openeye/opencv-surveillance/data/faces/

echo "✅ Backup complete: $BACKUP_DIR"

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### Automated Daily Backup

```bash
# Add to crontab
sudo crontab -e

# Run backup daily at 2 AM
0 2 * * * /opt/openeye/scripts/backup.sh
```

---

## Uninstallation

To completely remove OpenEye:

```bash
# Stop and disable service
sudo systemctl stop openeye
sudo systemctl disable openeye

# Remove service file
sudo rm /etc/systemd/system/openeye.service
sudo systemctl daemon-reload

# Remove installation
sudo rm -rf /opt/openeye

# Remove user (optional)
sudo userdel -r openeye

# Remove Nginx configuration (if used)
sudo rm /etc/nginx/sites-enabled/openeye
sudo rm /etc/nginx/sites-available/openeye
sudo systemctl restart nginx
```

---

## Comparison: Systemd vs Docker

| Feature | Systemd | Docker |
|---------|---------|--------|
| **Auto-start on boot** | ✅ `systemctl enable` | ✅ `restart: always` |
| **Auto-restart on crash** | ✅ `Restart=always` | ✅ `restart: always` |
| **Resource limits** | ✅ systemd directives | ✅ Docker limits |
| **Log management** | ✅ journalctl | ✅ docker logs |
| **Easy updates** | ⚠️ Manual/script | ✅ `docker pull` |
| **Portability** | ❌ Linux-specific | ✅ Cross-platform |
| **Performance** | ✅ Native | ⚠️ Small overhead |
| **Learning curve** | ⚠️ systemd knowledge | ⚠️ Docker knowledge |

**Choose systemd if:**
- Running on Linux server
- Want native performance
- Familiar with Linux system administration

**Choose Docker if:**
- Want maximum portability
- Prefer containerized deployments
- Running on non-Linux systems

---

## Additional Resources

- [systemd Documentation](https://www.freedesktop.org/software/systemd/man/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)
- [OpenEye GitHub](https://github.com/M1K31/OpenEye-OpenCV_Home_Security)

---

**Questions or Issues?**
- GitHub Issues: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues
- Documentation: See [README.md](../../README.md)

---

*Last Updated: October 9, 2025*  
*OpenEye v3.3.8*
