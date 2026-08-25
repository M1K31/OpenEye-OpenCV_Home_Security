# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Two-Way Audio System with WebRTC
Real-time bidirectional audio communication for surveillance cameras

This module provides WebRTC-based audio streaming for two-way communication,
audio capture, playback, and recording. Includes echo cancellation and
noise suppression.
"""

from fastapi.responses import HTMLResponse
from fastapi import FastAPI, WebSocket
import asyncio
import logging
import numpy as np
import wave
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import threading
from queue import Queue
import struct

logger = logging.getLogger(__name__)

# Optional heavy dependencies — graceful degradation when unavailable
# sounddevice rather than PyAudio. Both drive the same PortAudio engine, but
# PyAudio publishes wheels for Windows only, so on macOS and Linux it compiled
# from source against PortAudio's headers. When those headers were missing the
# build failed — and pip aborts the whole transaction, so one absent system
# library took every other dependency down with it and surfaced as an unrelated
# import error. sounddevice ships pure-Python wheels that never compile: the
# macOS wheel bundles libportaudio.dylib outright, and Linux needs only the
# runtime libportaudio2 package.
#
# OSError is caught alongside ImportError deliberately: on Linux without
# libportaudio2, sounddevice imports and then raises OSError('PortAudio library
# not found'). Catching only ImportError would let that escape and take the
# whole application down over an optional feature.
try:
    import sounddevice as sd
    AUDIO_IO_AVAILABLE = True
except (ImportError, OSError) as exc:
    sd = None
    AUDIO_IO_AVAILABLE = False
    logger.warning(
        f"sounddevice unavailable ({exc}) — audio capture/playback disabled. "
        "Install with: pip install sounddevice "
        "(Linux also needs the libportaudio2 package). "
        "Run install-deps.sh for guided installation."
    )

try:
    from aiortc import (
        RTCPeerConnection,
        RTCSessionDescription,
        MediaStreamTrack,
        RTCConfiguration,
        RTCIceServer,
    )
    from aiortc.contrib.media import MediaRecorder, MediaPlayer
    from av import AudioFrame
    WEBRTC_AVAILABLE = True
except ImportError:
    RTCPeerConnection = None
    RTCSessionDescription = None
    # `object` (not None) so the module-level `class AudioTrack(MediaStreamTrack)`
    # still defines when WebRTC is unavailable. The class is never instantiated
    # in that state — all usage is gated by WEBRTC_AVAILABLE.
    MediaStreamTrack = object
    RTCConfiguration = None
    RTCIceServer = None
    MediaRecorder = None
    MediaPlayer = None
    AudioFrame = None
    WEBRTC_AVAILABLE = False
    logger.warning(
        "aiortc/av not installed — WebRTC audio streaming disabled. "
        "Install with: pip install aiortc av. "
        "Run install-deps.sh for guided installation."
    )

# Signed 16-bit samples throughout. Named rather than inlined because the
# playback callback has to size its silence buffer in bytes, and that arithmetic
# is wrong in a way nothing catches if the two ever disagree.
SAMPLE_DTYPE = "int16"
BYTES_PER_SAMPLE = 2

# How much undelivered playback audio may accumulate before the oldest is
# dropped. Two-way audio is a conversation: stale audio is worse than missing
# audio, because latency that grows during a call never recovers on its own.
MAX_PLAYBACK_BACKLOG_BLOCKS = 4


@dataclass
class AudioConfig:
    """Audio configuration"""

    sample_rate: int = 16000  # Hz
    channels: int = 1  # Mono
    chunk_size: int = 1024  # Frames per buffer
    # Was a pyaudio.paInt16 constant; sounddevice takes a dtype string. Nothing
    # outside this module ever set it.
    dtype: str = SAMPLE_DTYPE
    input_device: Optional[int] = None
    output_device: Optional[int] = None
    enable_echo_cancellation: bool = True
    enable_noise_suppression: bool = True


class AudioCapture:
    """
    Audio capture from microphone

    Captures audio from input device and provides frames for streaming
    """

    def __init__(self, config: AudioConfig):
        """Initialize audio capture"""
        if not AUDIO_IO_AVAILABLE:
            raise RuntimeError(
                "Audio capture unavailable — sounddevice could not be loaded. "
                "Run install-deps.sh for guided installation."
            )

        self.config = config
        # sounddevice needs no engine object; PortAudio is initialised on demand
        # and devices are queried at module level, so there is nothing to hold
        # open or terminate.
        self.stream = None
        self.running = False

        # Audio processing
        self.audio_queue: Queue = Queue(maxsize=100)

        logger.info(
            f"Audio capture initialized: {config.sample_rate}Hz, {config.channels}ch")

    def list_devices(self) -> List[Dict]:
        """List available audio input devices"""
        devices = []

        for i, info in enumerate(sd.query_devices()):
            if info["max_input_channels"] > 0:
                devices.append(
                    {
                        "index": i,
                        "name": info["name"],
                        "channels": info["max_input_channels"],
                        "sample_rate": int(info["default_samplerate"]),
                    }
                )

        return devices

    def start(self):
        """Start audio capture"""
        if self.running:
            logger.warning("Audio capture already running")
            return

        try:
            self.stream = sd.RawInputStream(
                samplerate=self.config.sample_rate,
                blocksize=self.config.chunk_size,
                device=self.config.input_device,
                channels=self.config.channels,
                dtype=self.config.dtype,
                callback=self._audio_callback,
            )

            self.running = True
            self.stream.start()

            logger.info("Audio capture started")

        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            raise

    def stop(self):
        """Stop audio capture"""
        if not self.running:
            return

        self.running = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        logger.info("Audio capture stopped")

    def _audio_callback(self, indata, frame_count, time_info, status):
        """
        sounddevice callback for captured audio.

        Two differences from the PyAudio callback this replaces, both of which
        are silent corruption rather than errors if missed:

        1. PyAudio handed the callback an immutable `bytes` object, so a numpy
           view over it stayed valid once queued. sounddevice reuses the same
           underlying buffer for every block, so a view would be overwritten by
           the next block while still sitting in the queue — the copy below is
           required, not defensive.
        2. sounddevice callbacks return nothing; PyAudio expected
           `(data, paContinue)`.
        """
        if status:
            logger.warning(f"Audio capture status: {status}")

        try:
            # Copy out of the reused buffer before queueing — see note above.
            audio_data = np.frombuffer(indata, dtype=np.int16).copy()

            # Apply audio processing
            if self.config.enable_noise_suppression:
                audio_data = self._noise_suppression(audio_data)

            # Put in queue for streaming
            if not self.audio_queue.full():
                self.audio_queue.put(audio_data)

        except Exception as e:
            logger.error(f"Error in audio callback: {e}")

    def _noise_suppression(self, audio_data: np.ndarray) -> np.ndarray:
        """Simple noise suppression using noise gate"""
        # Calculate RMS. Guard against empty/invalid buffers: np.mean of an empty
        # array is NaN and float overflow can make the mean negative, either of
        # which makes np.sqrt emit "invalid value encountered in sqrt".
        if audio_data.size == 0:
            return audio_data
        mean_sq = np.mean(np.square(audio_data, dtype=np.float64))
        rms = np.sqrt(mean_sq) if np.isfinite(mean_sq) and mean_sq >= 0 else 0.0

        # Noise gate threshold
        threshold = 500

        if rms < threshold:
            return np.zeros_like(audio_data)

        return audio_data

    def get_frame(self) -> Optional[np.ndarray]:
        """Get next audio frame from queue"""
        try:
            return self.audio_queue.get(timeout=0.1)
        except BaseException:
            return None

    def __del__(self):
        """
        Cleanup.

        A partially constructed object is still finalised, so this cannot assume
        __init__ ran to completion: when the availability check rejects the
        construction, `running` and `stream` were never assigned, and reaching
        for them here raised AttributeError inside the garbage collector.
        """
        if getattr(self, "running", False):
            self.stop()


class AudioPlayback:
    """
    Audio playback to speaker

    Plays received audio data through output device
    """

    def __init__(self, config: AudioConfig):
        """Initialize audio playback"""
        if not AUDIO_IO_AVAILABLE:
            raise RuntimeError(
                "Audio playback unavailable — sounddevice could not be loaded. "
                "Run install-deps.sh for guided installation."
            )

        self.config = config
        self.stream = None
        self.running = False

        # Playback buffer
        self.playback_queue: Queue = Queue(maxsize=100)

        # Bytes left over when a queued frame does not divide evenly into a
        # PortAudio block. Held here and emitted at the start of the next block
        # so no samples are dropped — see _audio_callback.
        self._residual = b""

        logger.info(
            f"Audio playback initialized: {config.sample_rate}Hz, {config.channels}ch")

    def list_devices(self) -> List[Dict]:
        """List available audio output devices"""
        devices = []

        for i, info in enumerate(sd.query_devices()):
            if info["max_output_channels"] > 0:
                devices.append(
                    {
                        "index": i,
                        "name": info["name"],
                        "channels": info["max_output_channels"],
                        "sample_rate": int(info["default_samplerate"]),
                    }
                )

        return devices

    def start(self):
        """Start audio playback"""
        if self.running:
            logger.warning("Audio playback already running")
            return

        try:
            self.stream = sd.RawOutputStream(
                samplerate=self.config.sample_rate,
                blocksize=self.config.chunk_size,
                device=self.config.output_device,
                channels=self.config.channels,
                dtype=self.config.dtype,
                callback=self._audio_callback,
            )

            self.running = True
            self.stream.start()

            logger.info("Audio playback started")

        except Exception as e:
            logger.error(f"Failed to start audio playback: {e}")
            raise

    def stop(self):
        """Stop audio playback"""
        if not self.running:
            return

        self.running = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        logger.info("Audio playback stopped")

    def _audio_callback(self, outdata, frame_count, time_info, status):
        """
        sounddevice callback for audio playback.

        PyAudio accepted a returned buffer; sounddevice hands the callback a
        writable buffer that must be filled completely. A short write leaves the
        tail of the block holding the PREVIOUS block's samples, which is audible
        as a stutter or repeated fragment rather than an error, so the queued
        frame is padded or truncated to exactly the block size here.

        A queued frame is not guaranteed to match the block size: producers push
        whatever the far end sent, and nothing upstream enforces chunk_size.
        """
        if status:
            logger.warning(f"Audio playback status: {status}")

        needed = frame_count * self.config.channels * BYTES_PER_SAMPLE

        buffered = self._residual
        try:
            # Frames arrive sized by the far end, not by our block size, so pull
            # until the block can be filled rather than assuming one frame is
            # one block.
            while len(buffered) < needed and not self.playback_queue.empty():
                buffered += self.playback_queue.get().tobytes()
        except Exception as e:
            logger.error(f"Error in playback callback: {e}")

        if len(buffered) < needed:
            # Underrun: pad with silence rather than leave stale samples in the
            # tail of the buffer.
            out_data = buffered + b"\x00" * (needed - len(buffered))
            self._residual = b""
        else:
            out_data = buffered[:needed]
            remainder = buffered[needed:]
            # Cap the carry-over. Without this, a producer that consistently
            # outruns playback grows the backlog without bound and the delay
            # between speaking and being heard climbs for as long as the call
            # lasts. Dropping the oldest audio keeps the intercom responsive.
            limit = needed * MAX_PLAYBACK_BACKLOG_BLOCKS
            if len(remainder) > limit:
                logger.warning(
                    "Playback backlog exceeded %d blocks — dropping %d bytes "
                    "of buffered audio to keep latency bounded",
                    MAX_PLAYBACK_BACKLOG_BLOCKS, len(remainder) - limit,
                )
                remainder = remainder[-limit:]
            self._residual = remainder

        outdata[:] = out_data

    def play_frame(self, audio_data: np.ndarray):
        """Queue audio frame for playback"""
        if not self.playback_queue.full():
            self.playback_queue.put(audio_data)

    def __del__(self):
        """
        Cleanup.

        A partially constructed object is still finalised, so this cannot assume
        __init__ ran to completion: when the availability check rejects the
        construction, `running` and `stream` were never assigned, and reaching
        for them here raised AttributeError inside the garbage collector.
        """
        if getattr(self, "running", False):
            self.stop()


class AudioTrack(MediaStreamTrack):
    """
    Custom audio track for WebRTC

    Provides audio frames from capture device to WebRTC peer connection
    """

    kind = "audio"

    def __init__(self, audio_capture: AudioCapture):
        super().__init__()
        self.audio_capture = audio_capture

    async def recv(self) -> AudioFrame:
        """Receive next audio frame"""
        # Get audio data from capture
        audio_data = self.audio_capture.get_frame()

        if audio_data is None:
            # Return silence if no data
            audio_data = np.zeros(1024, dtype=np.int16)

        # Create AudioFrame
        frame = AudioFrame.from_ndarray(
            audio_data.reshape(1, -1), format="s16", layout="mono"
        )

        frame.sample_rate = self.audio_capture.config.sample_rate
        frame.pts = None

        return frame


class WebRTCAudioSession:
    """
    WebRTC audio session

    Manages WebRTC peer connection for two-way audio communication
    """

    def __init__(
        self,
        camera_id: str,
        audio_config: AudioConfig,
        ice_servers: Optional[List[str]] = None,
    ):
        """
        Initialize WebRTC audio session

        Args:
            camera_id: Camera identifier
            audio_config: Audio configuration
            ice_servers: List of STUN/TURN servers
        """
        self.camera_id = camera_id
        self.audio_config = audio_config

        # WebRTC peer connection
        rtc_config = RTCConfiguration(
            iceServers=[
                RTCIceServer(
                    urls=ice_servers or ["stun:stun.l.google.com:19302"])])
        self.pc = RTCPeerConnection(configuration=rtc_config)

        # Audio capture and playback
        self.audio_capture = AudioCapture(audio_config)
        self.audio_playback = AudioPlayback(audio_config)

        # Audio track
        self.audio_track: Optional[AudioTrack] = None

        # Setup event handlers
        self._setup_handlers()

        # Recording
        self.recording = False
        self.recorded_frames: List[np.ndarray] = []

        logger.info(f"WebRTC audio session created for {camera_id}")

    def _setup_handlers(self):
        """Setup WebRTC event handlers"""

        @self.pc.on("track")
        async def on_track(track):
            """Handle incoming audio track"""
            logger.info(f"Received {track.kind} track")

            if track.kind == "audio":
                # Start playback
                self.audio_playback.start()

                # Process incoming audio frames
                while True:
                    try:
                        frame = await track.recv()

                        # Convert to numpy array
                        audio_data = frame.to_ndarray()

                        # Play audio
                        self.audio_playback.play_frame(audio_data.flatten())

                        # Record if enabled
                        if self.recording:
                            self.recorded_frames.append(audio_data.flatten())

                    except Exception as e:
                        logger.error(f"Error receiving audio: {e}")
                        break

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            """Handle connection state changes"""
            logger.info(f"Connection state: {self.pc.connectionState}")

            if self.pc.connectionState == "connected":
                logger.info("WebRTC connection established")
            elif self.pc.connectionState == "failed":
                logger.error("WebRTC connection failed")
                await self.close()

    async def create_offer(self) -> Dict:
        """
        Create WebRTC offer

        Returns:
            SDP offer as dictionary
        """
        # Start audio capture
        self.audio_capture.start()

        # Create audio track
        self.audio_track = AudioTrack(self.audio_capture)
        self.pc.addTrack(self.audio_track)

        # Create offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)

        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type,
        }

    async def create_answer(self, offer: Dict) -> Dict:
        """
        Create WebRTC answer

        Args:
            offer: SDP offer from remote peer

        Returns:
            SDP answer as dictionary
        """
        # Set remote description
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer["sdp"], type=offer["type"])
        )

        # Start audio capture
        self.audio_capture.start()

        # Create audio track
        self.audio_track = AudioTrack(self.audio_capture)
        self.pc.addTrack(self.audio_track)

        # Create answer
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type,
        }

    async def set_remote_description(self, answer: Dict):
        """Set remote description (answer)"""
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
        )

    def start_recording(self):
        """Start recording audio conversation"""
        self.recording = True
        self.recorded_frames = []
        logger.info("Audio recording started")

    def stop_recording(self, output_path: str) -> bool:
        """
        Stop recording and save to file

        Args:
            output_path: Path to save WAV file

        Returns:
            True if successful
        """
        self.recording = False

        if len(self.recorded_frames) == 0:
            logger.warning("No audio frames recorded")
            return False

        try:
            # Concatenate frames
            audio_data = np.concatenate(self.recorded_frames)

            # Save as WAV
            with wave.open(output_path, "wb") as wav_file:
                wav_file.setnchannels(self.audio_config.channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.audio_config.sample_rate)
                wav_file.writeframes(audio_data.tobytes())

            logger.info(f"Audio recording saved to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving audio recording: {e}")
            return False

    async def close(self):
        """Close WebRTC session"""
        # Stop audio
        self.audio_capture.stop()
        self.audio_playback.stop()

        # Close peer connection
        await self.pc.close()

        logger.info("WebRTC audio session closed")


class TwoWayAudioManager:
    """
    Manager for multiple audio sessions

    Handles WebRTC signaling and session management for multiple cameras
    """

    def __init__(self, audio_config: Optional[AudioConfig] = None):
        """Initialize audio manager"""
        self.audio_config = audio_config or AudioConfig()
        self.sessions: Dict[str, WebRTCAudioSession] = {}
        self.available = AUDIO_IO_AVAILABLE and WEBRTC_AVAILABLE

        if not self.available:
            missing = []
            if not AUDIO_IO_AVAILABLE:
                missing.append("sounddevice")
            if not WEBRTC_AVAILABLE:
                missing.append("aiortc/av")
            logger.warning(
                f"Two-way audio manager initialized in DEGRADED mode — "
                f"missing: {', '.join(missing)}"
            )
        else:
            logger.info("Two-way audio manager initialized")

    async def create_session(
        self, camera_id: str, ice_servers: Optional[List[str]] = None
    ) -> "WebRTCAudioSession":
        """
        Create new audio session

        Args:
            camera_id: Camera identifier
            ice_servers: STUN/TURN servers

        Returns:
            WebRTCAudioSession object
        """
        if not self.available:
            raise RuntimeError(
                "Two-way audio unavailable — sounddevice and/or aiortc not installed. "
                "Run install-deps.sh for guided installation."
            )

        if camera_id in self.sessions:
            logger.warning(f"Session already exists for {camera_id}")
            return self.sessions[camera_id]

        session = WebRTCAudioSession(camera_id, self.audio_config, ice_servers)

        self.sessions[camera_id] = session

        logger.info(f"Created audio session for {camera_id}")
        return session

    async def close_session(self, camera_id: str):
        """Close audio session"""
        if camera_id not in self.sessions:
            logger.warning(f"No session found for {camera_id}")
            return

        session = self.sessions[camera_id]
        await session.close()

        del self.sessions[camera_id]

        logger.info(f"Closed audio session for {camera_id}")

    def get_session(self, camera_id: str) -> Optional[WebRTCAudioSession]:
        """Get existing session"""
        return self.sessions.get(camera_id)

    def list_audio_devices(self) -> Dict:
        """List available audio devices"""
        if not AUDIO_IO_AVAILABLE:
            return {
                "input_devices": [],
                "output_devices": [],
                "error": "sounddevice not installed",
            }

        capture = AudioCapture(self.audio_config)
        playback = AudioPlayback(self.audio_config)

        devices = {
            "input_devices": capture.list_devices(),
            "output_devices": playback.list_devices(),
        }

        return devices

    async def close_all(self):
        """Close all sessions"""
        for camera_id in list(self.sessions.keys()):
            await self.close_session(camera_id)


# Example usage for FastAPI integration

app = FastAPI()
audio_manager = TwoWayAudioManager()


@app.get("/")
async def index():
    """Serve test page"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Two-Way Audio Test</title>
    </head>
    <body>
        <h1>Two-Way Audio Communication</h1>
        <button id="start">Start Audio</button>
        <button id="stop">Stop Audio</button>
        <div id="status"></div>

        <script>
            const ws = new WebSocket('ws://localhost:8000/ws/audio/camera_1');
            let pc = null;

            document.getElementById('start').onclick = async () => {
                pc = new RTCPeerConnection({
                    iceServers: [{urls: 'stun:stun.l.google.com:19302'}]
                });

                // Get user audio
                const stream = await navigator.mediaDevices.getUserMedia({audio: true});
                stream.getTracks().forEach(track => pc.addTrack(track, stream));

                // Handle incoming audio
                pc.ontrack = event => {
                    const audio = new Audio();
                    audio.srcObject = event.streams[0];
                    audio.play();
                };

                // Create offer
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);

                // Send offer to server
                ws.send(JSON.stringify({
                    type: 'offer',
                    sdp: offer.sdp
                }));
            };

            ws.onmessage = async (event) => {
                const message = JSON.parse(event.data);

                if (message.type === 'answer') {
                    await pc.setRemoteDescription({
                        type: 'answer',
                        sdp: message.sdp
                    });
                }
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)


@app.websocket("/ws/audio/{camera_id}")
async def websocket_audio(websocket: WebSocket, camera_id: str):
    """WebSocket endpoint for audio signaling"""
    await websocket.accept()

    # Create session
    session = await audio_manager.create_session(camera_id)

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            if data["type"] == "offer":
                # Create answer
                answer = await session.create_answer(data)
                await websocket.send_json(answer)

            elif data["type"] == "answer":
                # Set remote description
                await session.set_remote_description(data)

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        await audio_manager.close_session(camera_id)


if __name__ == "__main__":
    import uvicorn

    # Run server
    uvicorn.run(app, host="0.0.0.0", port=8000)
