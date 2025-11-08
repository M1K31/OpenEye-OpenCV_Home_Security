# OpenEye Uninstall Guide

This guide will help you completely remove OpenEye from your system.

---

## 🗑️ Complete Uninstallation

### Step 1: Stop Running Services

#### If Running Directly
```bash
# Stop the Python server (Ctrl+C if running in terminal)
# Or find and kill the process
ps aux | grep "backend.main"
kill <process_id>
```

#### If Running with Docker
```bash
cd /path/to/OpenEye/opencv-surveillance

# Stop and remove containers
docker-compose down

# Remove volumes (deletes all data!)
docker-compose down -v

# Remove images
docker rmi openeye-backend openeye-nginx
```

### Step 2: Remove Python Virtual Environment

```bash
cd /path/to/OpenEye/opencv-surveillance

# If you used venv
rm -rf .venv

# If you used conda
conda env remove -n openeye
```

### Step 3: Remove Database

#### SQLite (Default)
```bash
cd /path/to/OpenEye/opencv-surveillance

# Remove database file
rm surveillance.db
```

#### PostgreSQL
```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Drop database
DROP DATABASE openeye_db;
DROP USER openeye;
\q
```

### Step 4: Remove Recordings and Data

```bash
cd /path/to/OpenEye/opencv-surveillance

# Remove recordings
rm -rf recordings/

# Remove face images
rm -rf faces/

# Remove logs
rm -rf logs/
rm backend.log

# Remove temporary files
rm -rf __pycache__
rm -rf backend/__pycache__
rm -rf backend/**/__pycache__
```

### Step 5: Remove Project Files

```bash
# Navigate to parent directory
cd /path/to/OpenEye

# Remove entire project
rm -rf opencv-surveillance/

# Or if you want to keep the code but remove all data:
cd opencv-surveillance
rm -rf recordings/ faces/ logs/ surveillance.db backend.log __pycache__
```

---

## 🔧 Selective Uninstallation

### Remove Only User Data (Keep Software)

```bash
cd /path/to/OpenEye/opencv-surveillance

# Remove databases
rm surveillance.db

# Remove recordings
rm -rf recordings/*

# Remove face data
rm -rf faces/*

# Keep the software for reinstall
```

### Remove Only Python Dependencies

```bash
# If using pip
pip uninstall -r requirements.txt -y

# If using conda
conda env remove -n openeye
```

### Remove Only Docker Components

```bash
# Stop containers
docker-compose down

# Remove volumes only
docker volume rm opencv-surveillance_postgres-data
docker volume rm opencv-surveillance_redis-data
docker volume rm opencv-surveillance_minio-data

# Keep images for later use
```

---

## 🧹 Clean System Services

### Remove Systemd Service (if configured)

```bash
# Stop service
sudo systemctl stop openeye

# Disable service
sudo systemctl disable openeye

# Remove service file
sudo rm /etc/systemd/system/openeye.service

# Reload systemd
sudo systemctl daemon-reload
```

### Remove from Startup (macOS)

```bash
# Remove LaunchAgent
rm ~/Library/LaunchAgents/com.openeye.surveillance.plist

# Unload service
launchctl unload ~/Library/LaunchAgents/com.openeye.surveillance.plist
```

---

## 🌐 Clean Network Configuration

### Remove Port Forwarding

1. Log into your router (usually `192.168.1.1`)
2. Find Port Forwarding settings
3. Remove any rules for port 8000 or OpenEye

### Remove WireGuard VPN

```bash
# Stop WireGuard
sudo wg-quick down wg0

# Remove configuration
sudo rm /etc/wireguard/wg0.conf

# Remove keys
rm privatekey publickey
```

### Remove Cloudflare Tunnel (if configured)

```bash
# Stop tunnel
cloudflared tunnel delete openeye

# Remove configuration
rm ~/.cloudflared/config.yml
```

---

## 📦 Remove Optional Components

### PostgreSQL (if you want to remove it completely)

```bash
# Ubuntu/Debian
sudo apt-get remove --purge postgresql postgresql-contrib
sudo apt-get autoremove

# macOS
brew uninstall postgresql
```

### Redis (if installed)

```bash
# Ubuntu/Debian
sudo apt-get remove --purge redis-server
sudo apt-get autoremove

# macOS
brew uninstall redis
```

### Nginx (if installed separately)

```bash
# Ubuntu/Debian
sudo apt-get remove --purge nginx
sudo apt-get autoremove

# macOS
brew uninstall nginx
```

---

## 🔐 Remove SSL Certificates

### Let's Encrypt Certificates

```bash
# List certificates
sudo certbot certificates

# Delete specific certificate
sudo certbot delete --cert-name your-domain.com

# Or remove all certbot data
sudo apt-get remove --purge certbot
sudo rm -rf /etc/letsencrypt/
```

### Self-Signed Certificates

```bash
cd /path/to/OpenEye/opencv-surveillance

# Remove SSL files
rm docker/ssl/cert.pem
rm docker/ssl/key.pem
```

---

## 📧 Clean Up Integrations

### Telegram Bot

1. Open Telegram
2. Find your OpenEye bot
3. Type `/deletebot` to @BotFather
4. Select your bot to delete

### Firebase (if configured)

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select your OpenEye project
3. Settings → General
4. Scroll to bottom: "Delete Project"

### Twilio (if configured)

1. Log into [Twilio Console](https://console.twilio.com)
2. Phone Numbers → Active Numbers
3. Release any numbers used for OpenEye
4. (Optional) Close account in Account Settings

---

## 🐳 Docker Complete Cleanup

### Remove All OpenEye Docker Resources

```bash
# Stop all OpenEye containers
docker stop $(docker ps -a -q --filter name=openeye)

# Remove all OpenEye containers
docker rm $(docker ps -a -q --filter name=openeye)

# Remove all OpenEye images
docker rmi $(docker images --filter reference="openeye*" -q)

# Remove all OpenEye volumes
docker volume rm $(docker volume ls -q --filter name=openeye)

# Remove all OpenEye networks
docker network rm $(docker network ls -q --filter name=openeye)

# Clean up unused Docker resources
docker system prune -a --volumes
```

---

## 🗄️ Backup Before Uninstall

**Important**: Create backups if you might want to restore later!

```bash
cd /path/to/OpenEye/opencv-surveillance

# Create backup directory
mkdir ~/openeye-backup

# Backup database
cp surveillance.db ~/openeye-backup/

# Or for PostgreSQL
pg_dump -U openeye openeye_db > ~/openeye-backup/database_backup.sql

# Backup recordings
tar -czf ~/openeye-backup/recordings_backup.tar.gz recordings/

# Backup face data
tar -czf ~/openeye-backup/faces_backup.tar.gz faces/

# Backup configuration
cp .env ~/openeye-backup/

echo "Backup saved to: ~/openeye-backup/"
```

---

## ↩️ Restore from Backup

If you change your mind:

```bash
cd /path/to/OpenEye/opencv-surveillance

# Restore database
cp ~/openeye-backup/surveillance.db ./

# Or for PostgreSQL
psql -U openeye openeye_db < ~/openeye-backup/database_backup.sql

# Restore recordings
tar -xzf ~/openeye-backup/recordings_backup.tar.gz

# Restore faces
tar -xzf ~/openeye-backup/faces_backup.tar.gz

# Restore configuration
cp ~/openeye-backup/.env ./

# Restart server
python -m backend.main
```

---

## ✅ Uninstall Verification Checklist

After uninstalling, verify everything is removed:

- [ ] No OpenEye processes running: `ps aux | grep openeye`
- [ ] No Docker containers: `docker ps -a | grep openeye`
- [ ] No systemd service: `systemctl list-units | grep openeye`
- [ ] Project directory removed: `ls /path/to/OpenEye`
- [ ] Database removed: `ls surveillance.db` or check PostgreSQL
- [ ] Recordings removed: `ls recordings/`
- [ ] Port 8000 not in use: `sudo netstat -tulpn | grep 8000`
- [ ] WireGuard configuration removed: `ls /etc/wireguard/wg0.conf`
- [ ] SSL certificates removed: `ls /etc/letsencrypt/`

---

## 🔄 Alternatives to Complete Uninstall

### Temporary Disable

Instead of uninstalling, just stop the service:

```bash
# Stop server
pkill -f "backend.main"

# Or stop Docker
docker-compose stop

# Data remains intact, can restart anytime
```

### Archive Installation

Keep everything but move it out of the way:

```bash
# Move to archive location
mv /path/to/OpenEye ~/Archives/openeye-$(date +%Y%m%d)

# Can restore later if needed
```

---

## ❓ Why Are You Uninstalling?

Before you go, consider:

### Performance Issues?
- Try reducing cameras or frame rate
- Use `hog` instead of `cnn` face detection
- Add more RAM or use external storage

### Too Complex?
- Use the simple Docker setup instead
- Check the USER_GUIDE.md for easier configuration
- Join our community for help

### Privacy Concerns?
- All data stays on your system
- No cloud services required
- You control everything

### Cost Concerns?
- OpenEye is 100% free!
- No subscriptions or hidden fees
- Run entirely on your own hardware

---

## 🆘 Need Help?

If you're uninstalling due to issues:

1. **Check Documentation**: `docs/` folder
2. **GitHub Issues**: Report problems
3. **Community**: Ask questions
4. **Reinstall**: It's easy to try again!

---

## 📝 Post-Uninstall Cleanup (Optional)

Clean up any remaining configuration or dependencies:

```bash
# Remove Python packages (if not used elsewhere)
pip uninstall opencv-python face_recognition dlib numpy -y

# Remove system packages (if not needed)
# Ubuntu/Debian
sudo apt-get autoremove
sudo apt-get autoclean

# macOS
brew cleanup
```

---

**Thank you for trying OpenEye! We hope it met your needs. Feel free to reinstall anytime!** 👋
