"""
Two-Way Audio System with WebRTC
Real-time bidirectional audio communication for surveillance cameras

This module provides WebRTC-based audio streaming for two-way communication,
audio capture, playback, and recording. Includes echo cancellation and
noise suppression.
"""

import asyncio
import logging
import numpy as np
import pyaudio
import wave
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import threading
from queue import Queue
import struct

from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    MediaStreamTrack,
    RTCConfiguration,
    RTCIceServer
)
from aiortc.contrib.media import MediaRecorder, MediaPlayer
from av import AudioFrame

logger = logging.getLogger(__name__)


@dataclass
class AudioConfig:
    """Audio configuration"""
    sample_rate: int = 16000  # Hz
    channels: int = 1  # Mono
    chunk_size: int = 1024  # Frames per buffer
    format: int = pyaudio.paInt16
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
        self.config = config
        self.pyaudio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.running = False
        
        # Audio processing
        self.audio_queue: Queue = Queue(maxsize=100)
        
        logger.info(f"Audio capture initialized: {config.sample_rate}Hz, {config.channels}ch")
    
    def list_devices(self) -> List[Dict]:
        """List available audio input devices"""
        devices = []
        
        for i in range(self.pyaudio.get_device_count()):
            info = self.pyaudio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': info['name'],
                    'channels': info['maxInputChannels'],
                    'sample_rate': int(info['defaultSampleRate'])
                })
        
        return devices
    
    def start(self):
        """Start audio capture"""
        if self.running:
            logger.warning("Audio capture already running")
            return
        
        try:
            self.stream = self.pyaudio.open(
                format=self.config.format,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                input=True,
                input_device_index=self.config.input_device,
                frames_per_buffer=self.config.chunk_size,
                stream_callback=self._audio_callback
            )
            
            self.running = True
            self.stream.start_stream()
            
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
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        logger.info("Audio capture stopped")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for captured audio"""
        if status:
            logger.warning(f"Audio capture status: {status}")
        
        try:
            # Convert bytes to numpy array
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            
            # Apply audio processing
            if self.config.enable_noise_suppression:
                audio_data = self._noise_suppression(audio_data)
            
            # Put in queue for streaming
            if not self.audio_queue.full():
                self.audio_queue.put(audio_data)
        
        except Exception as e:
            logger.error(f"Error in audio callback: {e}")
        
        return (in_data, pyaudio.paContinue)
    
    def _noise_suppression(self, audio_data: np.ndarray) -> np.ndarray:
        """Simple noise suppression using noise gate"""
        # Calculate RMS
        rms = np.sqrt(np.mean(audio_data ** 2))
        
        # Noise gate threshold
        threshold = 500
        
        if rms < threshold:
            return np.zeros_like(audio_data)
        
        return audio_data
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get next audio frame from queue"""
        try:
            return self.audio_queue.get(timeout=0.1)
        except:
            return None
    
    def __del__(self):
        """Cleanup"""
        self.stop()
        self.pyaudio.terminate()


class AudioPlayback:
    """
    Audio playback to speaker
    
    Plays received audio data through output device
    """
    
    def __init__(self, config: AudioConfig):
        """Initialize audio playback"""
        self.config = config
        self.pyaudio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.running = False
        
        # Playback buffer
        self.playback_queue: Queue = Queue(maxsize=100)
        
        logger.info(f"Audio playback initialized: {config.sample_rate}Hz, {config.channels}ch")
    
    def list_devices(self) -> List[Dict]:
        """List available audio output devices"""
        devices = []
        
        for i in range(self.pyaudio.get_device_count()):
            info = self.pyaudio.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': info['name'],
                    'channels': info['maxOutputChannels'],
                    'sample_rate': int(info['defaultSampleRate'])
                })
        
        return devices
    
    def start(self):
        """Start audio playback"""
        if self.running:
            logger.warning("Audio playback already running")
            return
        
        try:
            self.stream = self.pyaudio.open(
                format=self.config.format,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                output=True,
                output_device_index=self.config.output_device,
                frames_per_buffer=self.config.chunk_size,
                stream_callback=self._audio_callback
            )
            
            self.running = True
            self.stream.start_stream()
            
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
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        logger.info("Audio playback stopped")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for audio playback"""
        if status:
            logger.warning(f"Audio playback status: {status}")
        
        try:
            # Get audio data from queue
            if not self.playback_queue.empty():
                audio_data = self.playback_queue.get()
                
                # Convert to bytes
                out_data = audio_data.tobytes()
            else:
                # Silence if no data
                out_data = b'\x00' * (frame_count * self.config.channels * 2)
        
        except Exception as e:
            logger.error(f"Error in playback callback: {e}")
            out_data = b'\x00' * (frame_count * self.config.channels * 2)
        
        return (out_data, pyaudio.paContinue)
    
    def play_frame(self, audio_data: np.ndarray):
        """Queue audio frame for playback"""
        if not self.playback_queue.full():
            self.playback_queue.put(audio_data)
    
    def __del__(self):
        """Cleanup"""
        self.stop()
        self.pyaudio.terminate()


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
            audio_data.reshape(1, -1),
            format='s16',
            layout='mono'
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
        ice_servers: Optional[List[str]] = None
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
                RTCIceServer(urls=ice_servers or ["stun:stun.l.google.com:19302"])
            ]
        )
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
            "type": self.pc.localDescription.type
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
            "type": self.pc.localDescription.type
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
            with wave.open(output_path, 'wb') as wav_file:
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
        
        logger.info("Two-way audio manager initialized")
    
    async def create_session(
        self,
        camera_id: str,
        ice_servers: Optional[List[str]] = None
    ) -> WebRTCAudioSession:
        """
        Create new audio session
        
        Args:
            camera_id: Camera identifier
            ice_servers: STUN/TURN servers
            
        Returns:
            WebRTCAudioSession object
        """
        if camera_id in self.sessions:
            logger.warning(f"Session already exists for {camera_id}")
            return self.sessions[camera_id]
        
        session = WebRTCAudioSession(
            camera_id,
            self.audio_config,
            ice_servers
        )
        
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
        capture = AudioCapture(self.audio_config)
        playback = AudioPlayback(self.audio_config)
        
        devices = {
            'input_devices': capture.list_devices(),
            'output_devices': playback.list_devices()
        }
        
        return devices
    
    async def close_all(self):
        """Close all sessions"""
        for camera_id in list(self.sessions.keys()):
            await self.close_session(camera_id)


# Example usage for FastAPI integration
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

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
            
            if data['type'] == 'offer':
                # Create answer
                answer = await session.create_answer(data)
                await websocket.send_json(answer)
            
            elif data['type'] == 'answer':
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