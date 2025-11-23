# Two-Way Audio Communication Guide (v3.10.0)

Real-time bidirectional audio communication with your surveillance cameras using WebRTC.

## 🎯 Overview

OpenEye's Two-Way Audio feature enables real-time voice communication with cameras, allowing you to:
- **Listen** to audio from camera microphones
- **Speak** to people near cameras through connected speakers
- **Record** audio conversations for security purposes
- **Monitor** audio quality and connection status

Built on **WebRTC** technology for low-latency, peer-to-peer audio streaming.

---

## ✨ Features

### Core Capabilities
- ✅ **Bidirectional Audio** - Simultaneous listen and speak
- ✅ **WebRTC-Based** - Industry-standard, low-latency streaming
- ✅ **Echo Cancellation** - Prevents audio feedback loops
- ✅ **Noise Suppression** - Reduces background noise
- ✅ **Audio Recording** - Save conversations as WAV files
- ✅ **Multi-Camera Support** - Connect to different cameras independently
- ✅ **Mute Controls** - Separate microphone and speaker mute
- ✅ **Connection Status** - Real-time connection monitoring

### User Experience
- 🎤 **One-Click Connect** - Simple button click to start audio
- 📱 **Responsive UI** - Works on desktop, tablet, and mobile
- 🔒 **Secure** - JWT-authenticated WebSocket connections
- 🎨 **Theme-Aware** - Integrates with all 9 OpenEye themes
- ♿ **Accessible** - Keyboard navigation and ARIA labels

---

## 📋 Requirements

### System Requirements

**Backend (Server)**:
- Python 3.9+
- PyAudio 0.2.13+
- aiortc 1.6.0+ (WebRTC implementation)
- av 11.0.0+ (Audio/video processing)
- Microphone connected to server (for camera-side audio)
- Speakers connected to server (for camera-side playback)

**Frontend (Client)**:
- Modern web browser with WebRTC support:
  - Chrome/Edge 80+
  - Firefox 75+
  - Safari 14+
- Microphone permission granted
- HTTPS connection (required for microphone access in production)

**Network**:
- Stable internet connection
- UDP ports open for WebRTC (dynamic range)
- STUN server access (default: Google's stun:stun.l.google.com:19302)

### Optional Requirements

- **TURN Server**: For NAT traversal in complex networks
- **Hardware Echo Cancellation**: Improves audio quality
- **External Microphone/Speakers**: Better audio quality than built-in devices

---

## 🚀 Quick Start

### 1. Install Dependencies

The two-way audio dependencies are included in `requirements.txt`:

```bash
cd opencv_surveillance
pip install pyaudio aiortc av
```

**Platform-Specific Notes**:

**macOS**:
```bash
# Install PortAudio (required by PyAudio)
brew install portaudio

# Then install Python packages
pip install pyaudio aiortc av
```

**Ubuntu/Debian**:
```bash
# Install system dependencies
sudo apt-get install portaudio19-dev python3-pyaudio

# Then install Python packages
pip install aiortc av
```

**Windows**:
```bash
# Download and install PortAudio
# Then install Python packages
pip install pyaudio aiortc av
```

### 2. Start the Server

```bash
# Make sure backend is running
cd opencv_surveillance
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 3. Access Two-Way Audio

**From Dashboard**:
1. Navigate to Dashboard (http://localhost:8000)
2. Find an active camera
3. Click the 🎤 microphone button on the camera card
4. Click "Connect Audio" in the modal
5. Allow microphone permission when prompted

**From Camera Settings**:
1. Navigate to Cameras → Camera Management
2. Click ⚙️ Settings on any camera
3. Scroll to "Two-Way Audio" section
4. Click "Connect Audio"

---

## 📖 User Guide

### Opening Audio Connection

1. **Locate Audio Button**
   - Dashboard: 🎤 button appears on active camera cards
   - Camera Settings: Two-Way Audio section

2. **Click Audio Button**
   - Modal opens with connection interface
   - Shows camera name and audio controls

3. **Grant Microphone Permission**
   - Browser will request microphone access
   - Click "Allow" to enable two-way communication
   - Permission is remembered for future sessions

4. **Connect**
   - Click "Connect Audio" button
   - Wait for WebRTC connection to establish
   - Status changes to "Live" when connected

### Audio Controls

When connected, you have three controls:

**🎤 Speaking** (Microphone):
- **Green** = Microphone is ON (you can speak)
- **Gray** = Microphone is MUTED (you cannot speak)
- Click to toggle

**🔊 Listening** (Speaker):
- **Green** = Speaker is ON (you can hear)
- **Gray** = Speaker is MUTED (you cannot hear)
- Click to toggle

**⏹ Disconnect**:
- Ends the audio session
- Releases microphone and closes connection
- Returns to initial state

### Connection States

**🟢 Live**:
- Audio connection is active
- You can speak and listen
- Green pulsing indicator

**🟡 Connecting...**:
- Establishing WebRTC connection
- Negotiating peer connection
- Spinner animation

**⚠️ Error States**:
- **Microphone Permission Denied**: Allow microphone access in browser settings
- **No Microphone Found**: Connect a microphone and refresh
- **Connection Failed**: Check network and try again
- **WebSocket Connection Failed**: Backend server may be unreachable

---

## 🔧 Configuration

### Audio Settings

Edit `backend/core/two_way_audio_system.py`:

```python
@dataclass
class AudioConfig:
    sample_rate: int = 16000  # Hz (8000, 16000, 44100, 48000)
    channels: int = 1  # Mono (1) or Stereo (2)
    chunk_size: int = 1024  # Frames per buffer
    format: int = pyaudio.paInt16  # 16-bit audio
    input_device: Optional[int] = None  # Auto-detect
    output_device: Optional[int] = None  # Auto-detect
    enable_echo_cancellation: bool = True
    enable_noise_suppression: bool = True
```

### List Available Audio Devices

```bash
# Via API
curl http://localhost:8000/api/audio/devices

# Returns:
{
  "input_devices": [
    {"index": 0, "name": "Built-in Microphone", "channels": 2, "sample_rate": 44100},
    {"index": 1, "name": "USB Microphone", "channels": 1, "sample_rate": 48000}
  ],
  "output_devices": [
    {"index": 0, "name": "Built-in Speakers", "channels": 2, "sample_rate": 44100},
    {"index": 1, "name": "USB Speakers", "channels": 2, "sample_rate": 48000}
  ]
}
```

### Select Specific Devices

Edit `backend/main.py`:

```python
from backend.core.two_way_audio_system import TwoWayAudioManager, AudioConfig

# Custom audio configuration
audio_config = AudioConfig(
    input_device=1,  # Use USB Microphone
    output_device=1,  # Use USB Speakers
    sample_rate=48000,  # Higher quality
    enable_echo_cancellation=True,
    enable_noise_suppression=True
)

audio_manager = TwoWayAudioManager(audio_config=audio_config)
```

### STUN/TURN Server Configuration

For complex network environments, configure TURN servers:

```python
# In two_way_audio_system.py
ice_servers = [
    "stun:stun.l.google.com:19302",  # Google STUN
    "stun:stun1.l.google.com:19302",
    "turn:your-turn-server.com:3478?transport=udp",  # Your TURN server
]

session = WebRTCAudioSession(camera_id, audio_config, ice_servers)
```

---

## 🔍 Troubleshooting

### Common Issues

#### "Microphone Permission Denied"

**Problem**: Browser blocked microphone access

**Solutions**:
1. Click the 🔒 lock icon in browser address bar
2. Set microphone permission to "Allow"
3. Refresh the page and try again

**Chrome**: `chrome://settings/content/microphone`
**Firefox**: `about:preferences#privacy`
**Safari**: Safari → Preferences → Websites → Microphone

#### "No Microphone Found"

**Problem**: No audio input device detected

**Solutions**:
1. Connect a microphone to your computer
2. Check system audio settings
3. Verify microphone is not in use by another application
4. Restart browser

#### "Connection Failed"

**Problem**: WebRTC connection couldn't be established

**Solutions**:
1. **Check Network**: Ensure stable internet connection
2. **Firewall**: Allow UDP traffic for WebRTC
3. **STUN/TURN**: Configure TURN server for strict NAT
4. **Browser Console**: Check for WebRTC errors

```javascript
// Enable WebRTC debugging in Chrome
chrome://webrtc-internals/
```

#### "Audio Choppy or Delayed"

**Problem**: Poor audio quality

**Solutions**:
1. **Reduce Sample Rate**: Lower from 48000 to 16000 Hz
2. **Increase Chunk Size**: From 1024 to 2048 frames
3. **Check CPU Usage**: High CPU load affects audio
4. **Network Bandwidth**: Ensure sufficient bandwidth
5. **Echo Cancellation**: Enable in AudioConfig

#### "Echo/Feedback Loop"

**Problem**: Audio feedback creating echo

**Solutions**:
1. **Use Headphones**: Prevents speaker output from reaching microphone
2. **Enable Echo Cancellation**: Set `enable_echo_cancellation=True`
3. **Reduce Speaker Volume**: Lower volume to prevent feedback
4. **Use Directional Microphone**: Better isolation

---

## 🛠️ Advanced Usage

### Recording Audio Conversations

```python
# Start recording
session.start_recording()

# ... audio conversation happens ...

# Stop and save recording
success = session.stop_recording("data/audio/conversation_2025-01-15.wav")
```

Recordings are saved as **WAV files** with:
- Format: 16-bit PCM
- Sample Rate: As configured (default 16000 Hz)
- Channels: Mono (1 channel)

### Programmatic Audio Management

```python
from backend.core.two_way_audio_system import TwoWayAudioManager

# Initialize manager
manager = TwoWayAudioManager()

# Create session for camera
session = await manager.create_session("front_door_camera")

# Create WebRTC offer
offer = await session.create_offer()

# ... exchange SDP with client ...

# Set remote description (answer from client)
await session.set_remote_description(answer)

# Close session when done
await manager.close_session("front_door_camera")
```

### Custom Audio Processing

Extend `AudioCapture` for custom processing:

```python
class CustomAudioCapture(AudioCapture):
    def _noise_suppression(self, audio_data: np.ndarray) -> np.ndarray:
        """Custom noise suppression algorithm"""
        # Your custom processing
        rms = np.sqrt(np.mean(audio_data**2))
        threshold = 1000  # Custom threshold

        if rms < threshold:
            return np.zeros_like(audio_data)

        # Apply filter
        return audio_data * 0.8  # Reduce gain
```

---

## 🔐 Security Considerations

### Authentication

- All WebSocket connections require JWT authentication
- Token is passed via query parameter: `?token=<jwt>`
- Expired tokens are rejected

### Encryption

- WebRTC uses **DTLS-SRTP** for end-to-end encryption
- Audio streams are encrypted between peers
- TURN servers should use TLS/DTLS

### Privacy

- Audio is not stored unless explicitly recorded
- Recordings require admin privileges
- Clear audio history regularly

### Best Practices

1. **Use HTTPS**: Required for microphone access in production
2. **Limit Access**: Restrict audio feature to trusted users
3. **Monitor Sessions**: Log all audio connections
4. **Audit Recordings**: Review stored audio periodically
5. **Secure TURN**: Use authenticated TURN servers

---

## 📊 Performance

### Resource Usage

**Per Active Audio Session**:
- **CPU**: 2-5% (with echo cancellation)
- **RAM**: ~50-100 MB
- **Bandwidth**:
  - Uplink: ~128 kbps (16kHz, mono)
  - Downlink: ~128 kbps

**Scalability**:
- **Single Server**: Up to 10 simultaneous audio sessions
- **Clustered**: Unlimited (sessions are per-server)

### Optimization Tips

1. **Lower Sample Rate**: 8kHz for voice-only (halves bandwidth)
2. **Increase Chunk Size**: Reduces processing overhead
3. **Disable Processing**: Turn off noise suppression/echo cancellation if not needed
4. **Use TURN Relay**: Only when NAT traversal fails (adds latency)

---

## 🧪 Testing

### Manual Testing

**Test Page**:
```
http://localhost:8000/api/audio/test
```

Provides standalone WebRTC audio test interface.

### E2E Tests

Run automated tests:
```bash
cd opencv_surveillance/frontend
npx playwright test two-way-audio.spec.js
```

**Test Coverage**:
- ✅ Audio button visibility (active/offline cameras)
- ✅ Modal open/close functionality
- ✅ Microphone permission prompts
- ✅ Connection states (connecting, connected, error)
- ✅ Audio controls (mute/unmute)
- ✅ API endpoints (/devices, /ws, /test)

### Unit Tests

```bash
cd opencv_surveillance
pytest tests/test_two_way_audio.py
```

---

## 🌐 Browser Compatibility

| Browser | Version | WebRTC | Notes |
|---------|---------|--------|-------|
| Chrome  | 80+     | ✅ Full Support | Recommended |
| Edge    | 80+     | ✅ Full Support | Chromium-based |
| Firefox | 75+     | ✅ Full Support | Good performance |
| Safari  | 14+     | ⚠️ Partial | HTTPS required |
| Opera   | 67+     | ✅ Full Support | Chromium-based |
| Mobile  | iOS 14.3+, Android 90+ | ⚠️ Limited | Microphone restrictions |

---

## 📚 Additional Resources

### Documentation
- [WebRTC API Documentation](https://webrtc.org/getting-started/overview)
- [aiortc Documentation](https://aiortc.readthedocs.io/)
- [PyAudio Documentation](https://people.csail.mit.edu/hubert/pyaudio/docs/)

### Related OpenEye Docs
- [API Documentation](./API_DOCUMENTATION.md)
- [WebSocket Implementation](./WEBSOCKET_IMPLEMENTATION.md)
- [Security Guide](./SECURITY_GUIDE.md)

### Support
- GitHub Issues: [Report Issues](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues)
- Discussions: [Community Forum](https://github.com/M1K31/OpenEye-OpenCV_Home_Security/discussions)

---

## 🎓 FAQ

**Q: Does two-way audio work over the internet (WAN)?**
A: Yes, but you need proper port forwarding or a TURN server for NAT traversal.

**Q: Can I use Bluetooth headsets?**
A: Yes, but wired headsets are recommended for lower latency.

**Q: Is audio encrypted?**
A: Yes, WebRTC uses DTLS-SRTP for end-to-end encryption.

**Q: Can multiple users connect to the same camera's audio?**
A: Not simultaneously. Only one audio session per camera at a time.

**Q: Does it work offline (local network only)?**
A: Yes, WebRTC works on LAN without internet, but STUN server access helps with connection establishment.

**Q: What's the audio latency?**
A: Typically 100-300ms depending on network conditions.

---

**Made with ❤️ by Mikel Smart** | **v3.10.0** | **100% Free & Open Source**
