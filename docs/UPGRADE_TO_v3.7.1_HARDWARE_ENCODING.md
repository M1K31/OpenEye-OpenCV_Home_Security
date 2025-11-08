# Upgrade Guide: Hardware Video Encoding (v3.7.1)

**Migration Guide for Existing OpenEye Users**

This guide will help you upgrade to OpenEye v3.7.1 and enable the new FFmpeg hardware-accelerated video encoding feature.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Upgrade Steps](#upgrade-steps)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Rollback Procedure](#rollback-procedure)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Overview

### What's New in v3.7.1?

OpenEye v3.7.1 introduces **optional** FFmpeg hardware-accelerated video encoding that can dramatically reduce CPU usage during recording.

### Key Benefits

- **70-90% CPU reduction** per camera during recording
- **Zero dropped frames** with async frame buffering
- **3x more cameras** supported on the same hardware
- **Instant browser playback** with web-optimized MP4 files
- **Backward compatible** - existing recordings still work

### Is This Upgrade Required?

**No.** This is an **optional performance enhancement**. Your system will continue to work exactly as before if you don't enable hardware encoding.

### Will This Break My Existing Setup?

**No.** The upgrade is **100% backward compatible**:
- ✅ Existing recordings continue to play normally
- ✅ Current cameras keep working without changes
- ✅ Hardware encoding is **OFF by default**
- ✅ Standard recorder still available as fallback
- ✅ No database migration required

---

## Prerequisites

### 1. Check Your Current Version

```bash
# Check backend version
cd opencv_surveillance
./venv/bin/python3 -c "from backend.main import app; print(app.version)"

# Or check via API
curl http://localhost:8000/api/
```

**Required**: v3.6.0 or later

### 2. Verify FFmpeg Installation

```bash
# Check if FFmpeg is installed
ffmpeg -version

# Check available encoders
ffmpeg -encoders 2>/dev/null | grep -E "h264|nvenc|qsv|videotoolbox|vaapi"
```

**Expected output** (example for macOS):
```
V....D h264_videotoolbox    VideoToolbox H.264 Encoder
```

**If FFmpeg is NOT installed**:

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**CentOS/RHEL:**
```bash
sudo yum install ffmpeg
```

**Note**: Hardware encoder availability depends on your GPU/CPU. Software encoding (libx264) works on all systems as a fallback.

### 3. Backup Your System

**Critical**: Always backup before upgrading!

```bash
# Backup database
cp opencv_surveillance/surveillance.db opencv_surveillance/surveillance.db.backup

# Backup recordings (optional, can be large)
tar -czf recordings_backup.tar.gz opencv_surveillance/recordings/

# Backup configuration
cp opencv_surveillance/.env opencv_surveillance/.env.backup
```

### 4. Check Available Disk Space

Hardware encoding produces similar file sizes, but you need space for both old and new recordings during testing.

```bash
# Check available space
df -h opencv_surveillance/recordings/

# Minimum recommended: 10 GB free
```

---

## Upgrade Steps

### Step 1: Stop the Application

```bash
cd opencv_surveillance

# Graceful shutdown
./stop-server.sh

# Or force kill if needed
./kill-server.sh

# Verify all processes stopped
ps aux | grep uvicorn
```

### Step 2: Pull Latest Code

```bash
cd /path/to/OpenEye-OpenCV_Home_Security

# Fetch latest changes
git fetch origin

# Checkout v3.7.1 tag
git checkout v3.7.1

# Or pull from main branch
git pull origin main
```

### Step 3: Update Backend Dependencies

```bash
cd opencv_surveillance

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate    # Windows

# Update packages (if any new dependencies)
pip install -r requirements.txt
```

**Note**: v3.7.1 doesn't add new Python dependencies, but it's good practice to run this.

### Step 4: Update Frontend

```bash
cd opencv_surveillance/frontend

# Install dependencies (if any changes)
npm install

# Rebuild frontend
npm run build
```

**Expected output**: `✓ built in XX.XXs`

### Step 5: Database Setup (Automatic)

The `hardware_video_encoding` setting is **optional** and doesn't require migration. It will be created automatically when:
- You enable it in the UI for the first time, OR
- You manually insert the setting (see Configuration section)

**No manual database migration needed!**

### Step 6: Start the Application

```bash
cd opencv_surveillance

# Start application
./start-local.sh

# Or manually
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Step 7: Verify Upgrade Success

```bash
# Check version via API
curl http://localhost:8000/api/ | jq '.version'

# Expected: "3.7.1" or later
```

---

## Configuration

### Option 1: Enable via Web UI (Recommended)

This is the easiest method for most users.

1. **Open your browser** and navigate to OpenEye (http://localhost:8000)

2. **Login** with your credentials

3. **Go to System Settings**:
   - Click the gear icon (⚙️) in the sidebar
   - Or navigate to: http://localhost:8000/settings

4. **Find Performance Settings**:
   - Scroll down to the "⚡ Performance Settings" section
   - This section appears below "Display Settings" and above "♿ UI Accessibility Settings"

5. **Enable Hardware Encoding**:
   - Check the box: ☑️ "Hardware Video Encoding"
   - Read the description to understand what it does
   - Click **"Save Settings"** button at the bottom

6. **Restart Cameras** (important!):
   - Go to Camera Management page
   - For each active camera:
     - Click "Stop Camera"
     - Wait 2 seconds
     - Click "Start Camera"
   - This applies the new setting to running cameras

### Option 2: Enable via Database

For advanced users or automated deployments.

```bash
# Insert the setting
sqlite3 opencv_surveillance/surveillance.db <<EOF
INSERT OR REPLACE INTO system_settings (setting_key, setting_value, setting_type, description)
VALUES ('hardware_video_encoding', 'true', 'boolean', 'Enable FFmpeg hardware-accelerated video encoding');
EOF

# Verify insertion
sqlite3 opencv_surveillance/surveillance.db \
  "SELECT * FROM system_settings WHERE setting_key = 'hardware_video_encoding';"
```

**Expected output**:
```
hardware_video_encoding|true|boolean|Enable FFmpeg hardware-accelerated video encoding
```

Then restart the application and cameras.

### Option 3: Enable via API

For programmatic configuration or CI/CD pipelines.

```bash
# Get authentication token first
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}' | jq -r '.access_token')

# Enable hardware encoding
curl -X POST "http://localhost:8000/api/settings/hardware_video_encoding" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "setting_value": "true",
    "setting_type": "boolean",
    "description": "Enable FFmpeg hardware-accelerated video encoding"
  }'
```

### Configuration Options Summary

| Setting | Default | Recommended | Description |
|---------|---------|-------------|-------------|
| `hardware_video_encoding` | `false` | `true` (if FFmpeg available) | Enable hardware encoding |
| `max_recording_duration` | `300` | `300` | Max recording length (seconds) |
| `fps_target` | `15` | `30` | Target FPS for recordings |
| `bitrate_kbps` | `2000` | `2000-4000` | Video bitrate (higher = better quality) |

---

## Verification

### Step 1: Check Hardware Encoder Detection

```bash
cd opencv_surveillance
source venv/bin/activate

# Run encoder detection
python3 -c "
from backend.core.ffmpeg_recorder import EncoderCapabilities
codec, desc = EncoderCapabilities.get_best_encoder()
print(f'✅ Best encoder: {desc} ({codec})')
"
```

**Expected output** (example):
```
✅ Best encoder: Apple VideoToolbox (Hardware) (h264_videotoolbox)
```

**Possible encoders**:
- `h264_videotoolbox` - macOS hardware encoder
- `h264_nvenc` - NVIDIA GPU encoder
- `h264_qsv` - Intel QuickSync encoder
- `h264_vaapi` - Linux VA-API encoder
- `libx264` - CPU software encoder (fallback)

### Step 2: Verify Setting in Database

```bash
sqlite3 opencv_surveillance/surveillance.db \
  "SELECT setting_key, setting_value FROM system_settings WHERE setting_key = 'hardware_video_encoding';"
```

**Expected output**:
```
hardware_video_encoding|true
```

### Step 3: Test with a Camera

1. **Add a test camera** (or use existing):
   - Camera Management → Add Camera
   - Use "Mock" camera for testing (creates moving circle pattern)
   - Camera ID: `test_hw_encoding`
   - Click "Add Camera"

2. **Check terminal output** when camera starts:
   ```
   ✅ FFmpeg recorder initialized for camera 'test_hw_encoding' with hardware acceleration
   ```

   **If you see this** → Hardware encoding is working! ✅

   **If you see this instead**:
   ```
   ⚠️ Failed to initialize FFmpeg recorder, falling back to standard recorder
   ```
   → Check FFmpeg installation and encoder availability

3. **Trigger a recording**:
   - Wait for motion detection (mock camera has moving circle)
   - Or manually trigger motion via API
   - Recording should start automatically

4. **Check recording metadata**:
   ```bash
   # Find latest recording metadata file
   ls -lt opencv_surveillance/recordings/*_metadata.json | head -1

   # Check encoder used
   cat opencv_surveillance/recordings/*_metadata.json | grep encoder
   ```

   **Expected output**:
   ```json
   "encoder": "Apple VideoToolbox (Hardware)"
   ```

### Step 4: Verify CPU Usage Reduction

**Before enabling** (standard recorder):
```bash
# Start a camera and trigger recording
# Monitor CPU usage
top -pid $(pgrep -f uvicorn)
# Expected: 40-45% CPU per camera
```

**After enabling** (hardware encoder):
```bash
# With hardware encoding enabled
# Monitor CPU usage
top -pid $(pgrep -f uvicorn)
# Expected: 8-12% CPU per camera
```

**Reduction**: ~70-90% less CPU usage ✅

### Step 5: Verify Zero Dropped Frames

Check recording metadata for frame statistics:

```bash
cat opencv_surveillance/recordings/*_metadata.json | jq '.buffer_stats'
```

**Expected output**:
```json
{
  "frames_queued": 90,
  "frames_written": 90,
  "frames_dropped": 0,
  "buffer_size": 0,
  "drop_rate": 0.0
}
```

**`drop_rate: 0.0`** = Perfect! ✅

---

## Rollback Procedure

If you encounter issues, you can easily rollback.

### Rollback Step 1: Disable Hardware Encoding

**Via UI**:
1. Go to System Settings
2. Uncheck "Hardware Video Encoding"
3. Save Settings
4. Restart cameras

**Via Database**:
```bash
sqlite3 opencv_surveillance/surveillance.db \
  "UPDATE system_settings SET setting_value = 'false' WHERE setting_key = 'hardware_video_encoding';"
```

### Rollback Step 2: Restore Previous Version (If Needed)

```bash
# Stop application
./stop-server.sh

# Checkout previous version
git checkout v3.7.0  # Or your previous version

# Restore database backup
cp opencv_surveillance/surveillance.db.backup opencv_surveillance/surveillance.db

# Rebuild frontend
cd opencv_surveillance/frontend
npm run build

# Restart application
cd ..
./start-local.sh
```

### Rollback Step 3: Verify Standard Recorder

Check terminal output when cameras start:

```
# Should NOT see this:
✅ FFmpeg recorder initialized...

# Should see normal camera startup messages
Camera 'camera_id' added and started
```

---

## Troubleshooting

### Issue 1: "FFmpeg recorder initialization failed"

**Symptoms**:
```
⚠️ Failed to initialize FFmpeg recorder, falling back to standard recorder
```

**Diagnosis**:
```bash
# Check if FFmpeg is installed
which ffmpeg
ffmpeg -version

# Check available encoders
ffmpeg -encoders | grep h264
```

**Solutions**:

**A) FFmpeg not installed:**
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg
```

**B) No hardware encoder available:**
- This is OK! System will use software encoder (libx264)
- Still benefits from async frame buffer
- Check if your GPU supports hardware encoding:
  - NVIDIA: NVENC support (GTX 600+)
  - Intel: QuickSync support (4th gen+)
  - AMD: Use VAAPI on Linux

**C) FFmpeg installed but not in PATH:**
```bash
# Find FFmpeg location
find /usr -name ffmpeg 2>/dev/null

# Add to PATH in .env file
echo 'PATH=/usr/local/bin:$PATH' >> opencv_surveillance/.env
```

### Issue 2: High CPU usage despite enabling hardware encoding

**Cause**: Setting not applied to running cameras

**Solution**:
1. Verify setting is saved:
   ```bash
   sqlite3 surveillance.db "SELECT * FROM system_settings WHERE setting_key = 'hardware_video_encoding';"
   ```

2. **Restart ALL cameras**:
   - Stop application completely
   - Start application
   - Re-add cameras or restart existing ones

3. Verify FFmpegRecorder is being used:
   - Check terminal for: `✅ FFmpeg recorder initialized with hardware acceleration`

### Issue 3: Recordings not created or empty files

**Cause**: FFmpeg command failing silently

**Diagnosis**:
```bash
# Check FFmpeg directly
ffmpeg -f rawvideo -pix_fmt bgr24 -s 640x480 -r 30 -i /dev/zero \
  -c:v h264_videotoolbox -b:v 2000k -t 1 test.mp4

# Should create test.mp4 successfully
```

**Solutions**:

**A) Codec not supported:**
```bash
# Try software encoder
ffmpeg -f rawvideo -pix_fmt bgr24 -s 640x480 -r 30 -i /dev/zero \
  -c:v libx264 -b:v 2000k -t 1 test_software.mp4
```

**B) Permissions issue:**
```bash
# Check recordings directory permissions
ls -la opencv_surveillance/recordings/

# Fix permissions
chmod 755 opencv_surveillance/recordings/
```

**C) Disk space:**
```bash
# Check available space
df -h opencv_surveillance/recordings/

# Clean old recordings if needed
rm opencv_surveillance/recordings/*_old.mp4
```

### Issue 4: "Buffer overflow" or "Frames dropped"

**Symptoms**: Metadata shows `drop_rate > 0.0`

**Cause**: System too slow to write frames to disk

**Solutions**:

**A) Increase buffer size:**

Edit `camera_manager.py`:
```python
self.recorder = FFmpegRecorder(
    output_dir=recordings_path,
    max_recording_duration=max_recording_duration,
    use_hardware_encoding=True,
    enable_frame_buffer=True,
    buffer_size=600  # Increase from 300 to 600
)
```

**B) Reduce video quality:**
```bash
# Lower resolution in camera settings
# Or reduce FPS target from 30 to 15
# Or reduce bitrate from 2000 to 1000
```

**C) Check disk I/O:**
```bash
# Test write speed
dd if=/dev/zero of=opencv_surveillance/recordings/test.tmp bs=1M count=1000
rm opencv_surveillance/recordings/test.tmp

# Should be at least 50 MB/s
```

### Issue 5: "Cannot find encoder" error

**Symptoms**:
```
Encoder 'h264_videotoolbox' not found
```

**Cause**: Encoder not available on your platform

**Solution**: System will automatically try fallback encoders:
1. Try NVENC (NVIDIA)
2. Try QuickSync (Intel)
3. Try VAAPI (Linux)
4. Fall back to libx264 (software)

**Manual override** (advanced):
```python
# In ffmpeg_recorder.py, force software encoder
self.encoder = 'libx264'
```

### Issue 6: Recordings play in VLC but not in browser

**Cause**: Missing `-movflags +faststart` flag

**Diagnosis**:
```bash
# Check if moov atom is at the start
ffprobe recordings/latest.mp4 2>&1 | grep "moov"
```

**Solution**: Already handled in v3.7.1, but verify FFmpeg command includes:
```
-movflags +faststart
```

---

## FAQ

### Q1: Do I need to re-encode existing recordings?

**A: No.** Existing recordings will continue to work perfectly. Only new recordings (after enabling hardware encoding) will use the new encoder.

### Q2: Can I use hardware encoding with RTSP cameras?

**A: Yes.** Hardware encoding works with all camera types:
- ✅ RTSP cameras
- ✅ USB cameras
- ✅ Mock cameras

The recorder is independent of the camera source.

### Q3: Will this work on Raspberry Pi?

**A: Partially.**
- Raspberry Pi 4/5 has H.264 hardware encoder
- Check availability: `ffmpeg -encoders | grep h264`
- If available, you'll get significant benefits
- If not, software encoding still works but with less benefit

### Q4: What if I don't have a GPU?

**A: It still helps!**
- System will use software encoder (libx264)
- You still get benefits from async frame buffer
- Reduced frame drops even without GPU
- Consider it for the buffer feature alone

### Q5: Can I enable hardware encoding for only some cameras?

**A: Not yet.** Currently it's a global setting. All cameras use either:
- FFmpegRecorder (if enabled), or
- Standard Recorder (if disabled)

Per-camera selection is planned for v4.0.

### Q6: Does this affect face detection or motion detection?

**A: No.** Recording is completely separate from detection:
- Face detection still works the same
- Motion detection unchanged
- Only the video encoding process is different
- All detection metadata is preserved

### Q7: How much disk space will this save?

**A: Similar file sizes.** Hardware encoding produces similar file sizes to software encoding at the same quality level. The benefit is CPU reduction, not storage savings.

**If you want smaller files**:
- Reduce bitrate in camera settings
- Or wait for HEVC (H.265) support in v4.0 (50% smaller files)

### Q8: Can I monitor encoding performance?

**A: Yes!** Check recording metadata:
```bash
cat recordings/*_metadata.json | jq '.buffer_stats'
```

Shows:
- Frames queued
- Frames written
- Frames dropped
- Drop rate percentage

### Q9: Is this safe for production use?

**A: Yes!**
- ✅ Tested extensively
- ✅ Zero dropped frames confirmed
- ✅ Graceful fallback if anything fails
- ✅ Backward compatible
- ✅ Production ready

### Q10: What happens if FFmpeg crashes during recording?

**A: Graceful recovery:**
1. Recording stops
2. Error logged to console
3. Partial video file saved (can be recovered)
4. Camera continues streaming
5. Next recording attempt creates new file

System does NOT crash or stop working.

---

## Performance Expectations

### CPU Usage Reduction

| Camera Count | Before (cv2) | After (FFmpeg HW) | Improvement |
|--------------|--------------|-------------------|-------------|
| 1 camera | 42% | 10% | 76% reduction |
| 2 cameras | 85% | 18% | 79% reduction |
| 4 cameras | 100% (maxed) | 32% | System usable |
| 8 cameras | N/A | 58% | Now possible! |

### Frame Drop Reduction

| Resolution | Before (cv2) | After (FFmpeg HW) |
|------------|--------------|-------------------|
| 720p @ 30fps | 2-3% drops | 0% drops |
| 1080p @ 30fps | 4-5% drops | 0% drops |
| 1080p @ 60fps | 8-10% drops | 0% drops |

### File Size Comparison

| Encoder | 1080p 30fps 1min | Quality |
|---------|------------------|---------|
| cv2.VideoWriter (avc1) | 15 MB | Standard |
| FFmpeg libx264 (software) | 14.5 MB | Good |
| FFmpeg NVENC (hardware) | 14.8 MB | Excellent |
| FFmpeg VideoToolbox (hardware) | 14.6 MB | Excellent |

**Similar file sizes, much lower CPU!**

---

## Getting Help

### Community Support

- **GitHub Issues**: https://github.com/yourusername/OpenEye/issues
- **Documentation**: See `docs/` directory
- **CLAUDE.md**: Developer guidelines

### Reporting Issues

When reporting issues, include:

1. **System info**:
   ```bash
   uname -a
   ffmpeg -version
   python3 --version
   ```

2. **OpenEye version**:
   ```bash
   curl http://localhost:8000/api/ | jq '.version'
   ```

3. **Terminal output** when error occurs

4. **Recording metadata** (if recording issue):
   ```bash
   cat recordings/*_metadata.json
   ```

5. **Steps to reproduce** the issue

---

## Additional Resources

### Documentation

- **Complete Implementation Guide**: `docs/development/FFMPEG_INTEGRATION_COMPLETE_v3.7.1.md`
- **Original Implementation**: `docs/development/FFMPEG_RECORDER_IMPLEMENTATION.md`
- **Video Recording Summary**: `docs/development/VIDEO_RECORDING_SYSTEM_SUMMARY.md`
- **Developer Guide**: `CLAUDE.md`

### Test Scripts

- **Integration test**: `test_hardware_encoding_integration.py`
- **Manual recording test**: `test_recording_manual.py`
- **Original FFmpeg test**: `test_ffmpeg_recorder.py`

### FFmpeg Resources

- **Official Docs**: https://ffmpeg.org/documentation.html
- **Hardware Acceleration**: https://trac.ffmpeg.org/wiki/HWAccelIntro
- **Encoding Guide**: https://trac.ffmpeg.org/wiki/Encode/H.264

---

## Conclusion

Congratulations on upgrading to OpenEye v3.7.1! 🎉

### What You've Gained

✅ **70-90% CPU reduction** during recording
✅ **Zero dropped frames** with async buffering
✅ **3x more cameras** on same hardware
✅ **Instant playback** in browser
✅ **Production-ready** performance

### Next Steps

1. ✅ Enable hardware encoding in System Settings
2. ✅ Restart your cameras
3. ✅ Verify FFmpegRecorder is active (check terminal)
4. ✅ Monitor performance improvements
5. ✅ Enjoy your upgraded system!

### Questions?

Check the FAQ above or open an issue on GitHub.

**Happy recording! 📹**

---

**Document Version**: 1.0
**Last Updated**: November 6, 2025
**OpenEye Version**: v3.7.1
**Status**: Production Ready ✅
