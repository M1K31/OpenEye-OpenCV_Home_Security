# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
FFmpeg-based Video Recorder with Hardware Acceleration
Replaces cv2.VideoWriter with FFmpeg subprocess for better performance and hardware support

Features:
- Hardware acceleration (NVENC, QuickSync, VAAPI)
- Async frame buffer queue (no dropped frames)
- Web-optimized encoding (faststart flag)
- Automatic fallback to software encoding
- Face detection metadata tracking
"""

import subprocess
import os
import json
import time
import asyncio
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


class EncoderCapabilities:
    """
    Detect available hardware encoders
    """

    @staticmethod
    def detect_available_encoders() -> Dict[str, bool]:
        """
        Detect which hardware encoders are available

        Returns:
            Dict with encoder availability: {
                'nvenc': bool,  # NVIDIA NVENC
                'qsv': bool,    # Intel QuickSync
                'vaapi': bool,  # Intel/AMD VAAPI (Linux)
                'videotoolbox': bool  # Apple VideoToolbox (macOS)
            }
        """
        encoders = {
            'nvenc': False,
            'qsv': False,
            'vaapi': False,
            'videotoolbox': False
        }

        try:
            # Check available encoders via ffmpeg
            result = subprocess.run(
                ['ffmpeg', '-hide_banner', '-encoders'],
                capture_output=True,
                text=True,
                timeout=5
            )

            output = result.stdout

            # Check for NVENC (NVIDIA)
            if 'h264_nvenc' in output or 'hevc_nvenc' in output:
                encoders['nvenc'] = True
                logger.info("✅ NVIDIA NVENC hardware encoder detected")

            # Check for QuickSync (Intel)
            if 'h264_qsv' in output or 'hevc_qsv' in output:
                encoders['qsv'] = True
                logger.info("✅ Intel QuickSync hardware encoder detected")

            # Check for VAAPI (Intel/AMD on Linux)
            if 'h264_vaapi' in output or 'hevc_vaapi' in output:
                encoders['vaapi'] = True
                logger.info("✅ VAAPI hardware encoder detected")

            # Check for VideoToolbox (macOS)
            if 'h264_videotoolbox' in output or 'hevc_videotoolbox' in output:
                encoders['videotoolbox'] = True
                logger.info("✅ Apple VideoToolbox hardware encoder detected")

        except FileNotFoundError:
            logger.warning("⚠️ FFmpeg not found. Install FFmpeg for hardware acceleration support.")
            logger.warning("   Install: brew install ffmpeg (macOS) | apt install ffmpeg (Linux)")
        except Exception as e:
            logger.error(f"Error detecting encoders: {e}")

        return encoders

    @staticmethod
    def get_best_encoder() -> Tuple[str, str]:
        """
        Get the best available encoder

        Returns:
            (codec_name, description) tuple
        """
        encoders = EncoderCapabilities.detect_available_encoders()

        # Priority order: NVENC > QuickSync > VideoToolbox > VAAPI > Software
        if encoders['nvenc']:
            return ('h264_nvenc', 'NVIDIA NVENC (Hardware)')
        elif encoders['qsv']:
            return ('h264_qsv', 'Intel QuickSync (Hardware)')
        elif encoders['videotoolbox']:
            return ('h264_videotoolbox', 'Apple VideoToolbox (Hardware)')
        elif encoders['vaapi']:
            return ('h264_vaapi', 'VAAPI (Hardware)')
        else:
            return ('libx264', 'H.264 Software (CPU)')


class FrameBuffer:
    """
    Async frame buffer queue for smooth recording
    Prevents dropped frames by queuing frames in background thread
    """

    def __init__(self, max_size: int = 300):
        """
        Initialize frame buffer

        Args:
            max_size: Maximum number of frames to buffer (default: 300 = 10 seconds at 30fps)
        """
        self.buffer = queue.Queue(maxsize=max_size)
        self.is_active = False
        self.writer_thread: Optional[threading.Thread] = None
        self.frames_queued = 0
        self.frames_written = 0
        self.frames_dropped = 0

    def add_frame(self, frame: np.ndarray) -> bool:
        """
        Add frame to buffer (non-blocking)

        Returns:
            True if frame added, False if buffer full (frame dropped)
        """
        try:
            self.buffer.put_nowait(frame)
            self.frames_queued += 1
            return True
        except queue.Full:
            self.frames_dropped += 1
            logger.warning(f"⚠️ Frame buffer full, dropped frame (total dropped: {self.frames_dropped})")
            return False

    def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Get next frame from buffer (blocking with timeout)
        """
        try:
            frame = self.buffer.get(timeout=timeout)
            self.frames_written += 1
            return frame
        except queue.Empty:
            return None

    def clear(self):
        """Clear all buffered frames"""
        while not self.buffer.empty():
            try:
                self.buffer.get_nowait()
            except queue.Empty:
                break

    def get_stats(self) -> Dict:
        """Get buffer statistics"""
        return {
            'frames_queued': self.frames_queued,
            'frames_written': self.frames_written,
            'frames_dropped': self.frames_dropped,
            'buffer_size': self.buffer.qsize(),
            'drop_rate': (self.frames_dropped / max(self.frames_queued, 1)) * 100
        }


class FFmpegRecorder:
    """
    Enhanced video recorder using FFmpeg with hardware acceleration
    """

    def __init__(
        self,
        output_dir: str = "recordings",
        max_recording_duration: int = 300,
        use_hardware_encoding: bool = True,
        enable_frame_buffer: bool = True,
        buffer_size: int = 300,
        enable_audio: bool = False,
        audio_device: Optional[str] = None
    ):
        """
        Initialize FFmpeg recorder

        Args:
            output_dir: Directory to save recordings
            max_recording_duration: Maximum recording time in seconds
            use_hardware_encoding: Enable hardware acceleration if available
            enable_frame_buffer: Enable async frame buffering
            buffer_size: Maximum frames to buffer (default: 300)
            enable_audio: Enable audio recording from microphone (default: False)
            audio_device: Audio input device (None = default system microphone)
        """
        self.output_dir = Path(output_dir)
        self.max_recording_duration = max_recording_duration
        self.use_hardware_encoding = use_hardware_encoding
        self.enable_frame_buffer = enable_frame_buffer
        self.enable_audio = enable_audio
        self.audio_device = audio_device

        # Recording state
        self.is_recording = False
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.filename = ""
        self.metadata_filename = ""
        self.recording_start_time: Optional[datetime] = None
        self.frame_count = 0
        self.detected_faces: List[Dict] = []
        
        # Track motion event IDs associated with this recording
        # These will be linked to recording_id when recording stops
        self.associated_motion_event_ids = []
        
        # Store the last created recording_id (set after stop())
        self.last_recording_id = None

        # Frame buffer
        self.frame_buffer: Optional[FrameBuffer] = None
        self.writer_thread: Optional[threading.Thread] = None

        # Encoder selection
        self.encoder, self.encoder_description = EncoderCapabilities.get_best_encoder()
        logger.info(f"🎬 Selected encoder: {self.encoder_description}")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(
        self,
        frame_width: int,
        frame_height: int,
        fps: int = 30,
        camera_id: str = "unknown"
    ) -> bool:
        """
        Start recording session

        Args:
            frame_width: Video width
            frame_height: Video height
            fps: Frames per second
            camera_id: Camera identifier

        Returns:
            True if started successfully
        """
        if self.is_recording:
            logger.warning("Already recording")
            return False

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = str(self.output_dir / f"{camera_id}_motion_{timestamp}.mp4")
        self.metadata_filename = str(self.output_dir / f"{camera_id}_motion_{timestamp}_metadata.json")

        # Select codec and build FFmpeg command
        codec = self.encoder if self.use_hardware_encoding else 'libx264'

        # Build FFmpeg command - video input first
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{frame_width}x{frame_height}',
            '-r', str(fps),
            '-i', '-',  # Read video from stdin
        ]
        
        # Add audio input if enabled (before video codec settings)
        if self.enable_audio:
            # Use default system microphone
            try:
                import platform
                if platform.system() == 'Darwin':
                    # macOS - use avfoundation
                    if self.audio_device:
                        # Use specific audio device index
                        ffmpeg_cmd.extend([
                            '-f', 'avfoundation',
                            '-i', f':{self.audio_device}'
                        ])
                    else:
                        # Use default audio input device
                        ffmpeg_cmd.extend([
                            '-f', 'avfoundation',
                            '-i', ':0'  # Default audio input device
                        ])
                elif platform.system() == 'Linux':
                    # Linux - use pulse or alsa
                    if self.audio_device:
                        ffmpeg_cmd.extend([
                            '-f', 'pulse',
                            '-i', self.audio_device
                        ])
                    else:
                        ffmpeg_cmd.extend([
                            '-f', 'pulse',
                            '-i', 'default'
                        ])
                else:
                    # Windows - use dshow
                    if self.audio_device:
                        ffmpeg_cmd.extend([
                            '-f', 'dshow',
                            '-i', f'audio="{self.audio_device}"'
                        ])
                    else:
                        ffmpeg_cmd.extend([
                            '-f', 'dshow',
                            '-i', 'audio="Microphone"'
                        ])
            except Exception as e:
                logger.warning(f"Could not detect audio input device, audio recording disabled: {e}")
                self.enable_audio = False
        
        # Add video codec settings
        ffmpeg_cmd.append('-c:v')
        ffmpeg_cmd.append(codec)

        # Add codec-specific parameters
        if codec == 'h264_nvenc':
            # NVENC (NVIDIA) settings
            ffmpeg_cmd.extend([
                '-preset', 'fast',  # fast, medium, slow
                '-b:v', '4M',  # 4 Mbps bitrate
                '-maxrate', '6M',
                '-bufsize', '8M',
                '-gpu', '0'  # Use first GPU
            ])
        elif codec == 'h264_qsv':
            # QuickSync (Intel) settings
            ffmpeg_cmd.extend([
                '-preset', 'fast',
                '-b:v', '4M',
                '-maxrate', '6M'
            ])
        elif codec == 'h264_videotoolbox':
            # VideoToolbox (macOS) settings
            ffmpeg_cmd.extend([
                '-b:v', '4M',
                '-allow_sw', '1',  # Allow software fallback
                '-realtime', '1'
            ])
        elif codec == 'libx264':
            # Software H.264 settings
            ffmpeg_cmd.extend([
                '-preset', 'fast',  # ultrafast, superfast, veryfast, faster, fast, medium
                '-crf', '23',  # Constant Rate Factor (18-28, lower = better quality)
                '-b:v', '4M',
                '-maxrate', '6M',
                '-bufsize', '8M'
            ])

        # Add audio codec if audio is enabled
        if self.enable_audio:
            ffmpeg_cmd.extend([
                '-c:a', 'aac',  # AAC audio codec (widely supported)
                '-b:a', '128k',  # Audio bitrate
                '-ar', '44100',  # Audio sample rate
                '-ac', '2',  # Stereo audio
            ])
        
        # Add web optimization (moov atom at start for progressive playback)
        ffmpeg_cmd.extend([
            '-movflags', '+faststart',  # CRITICAL for web playback
            '-pix_fmt', 'yuv420p',  # Browser-compatible pixel format
            self.filename
        ])

        try:
            # Start FFmpeg process
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8  # 100MB buffer
            )

            logger.info(f"✅ Started recording: {self.filename}")
            logger.info(f"   Encoder: {codec}")
            logger.info(f"   Resolution: {frame_width}x{frame_height} @ {fps}fps")

            # Initialize state
            self.is_recording = True
            self.recording_start_time = datetime.now()
            self.frame_count = 0
            self.detected_faces = []
            self.associated_motion_event_ids = []  # Reset for new recording
            self.last_recording_id = None

            # Start frame buffer if enabled
            if self.enable_frame_buffer:
                self.frame_buffer = FrameBuffer(max_size=300)
                self.frame_buffer.is_active = True
                self.writer_thread = threading.Thread(
                    target=self._write_frames_worker,
                    daemon=True
                )
                self.writer_thread.start()
                logger.info("✅ Frame buffer enabled (async mode)")

            return True

        except FileNotFoundError:
            logger.error("❌ FFmpeg not found. Install: brew install ffmpeg (macOS) | apt install ffmpeg (Linux)")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to start FFmpeg: {e}")
            return False

    def _write_frames_worker(self):
        """
        Background thread worker for writing frames from buffer
        """
        logger.info("Frame writer thread started")

        while self.frame_buffer and self.frame_buffer.is_active:
            frame = self.frame_buffer.get_frame(timeout=1.0)

            if frame is not None:
                self._write_frame_to_ffmpeg(frame)

            # Check if we should stop
            if not self.is_recording and self.frame_buffer.buffer.empty():
                break

        logger.info("Frame writer thread stopped")

    def _write_frame_to_ffmpeg(self, frame: np.ndarray):
        """Write frame directly to FFmpeg stdin"""
        if self.ffmpeg_process and self.ffmpeg_process.stdin:
            try:
                self.ffmpeg_process.stdin.write(frame.tobytes())
            except BrokenPipeError:
                logger.error("❌ FFmpeg pipe broken")
                self.is_recording = False
            except Exception as e:
                logger.error(f"❌ Error writing frame: {e}")

    def write(self, frame: np.ndarray, faces: Optional[List[Dict]] = None):
        """
        Write frame to recording

        Args:
            frame: Video frame (numpy array)
            faces: Optional list of detected faces in this frame
        """
        if not self.is_recording:
            return

        # Track faces
        if faces:
            for face in faces:
                self.detected_faces.append({
                    'frame_number': self.frame_count,
                    'timestamp': (datetime.now() - self.recording_start_time).total_seconds(),
                    'person_name': face.get('name', 'Unknown'),
                    'confidence': face.get('confidence', 0.0)
                })

        # Write frame
        if self.enable_frame_buffer and self.frame_buffer:
            # Add to buffer (async)
            self.frame_buffer.add_frame(frame)
        else:
            # Write directly (sync)
            self._write_frame_to_ffmpeg(frame)

        self.frame_count += 1

        # Note: Caller should check should_stop_recording() to stop when max duration reached

    def stop(self) -> Optional[Dict]:
        """
        Stop recording and finalize video

        Returns:
            Recording metadata dict or None if failed
        """
        if not self.is_recording:
            return None

        logger.info("Stopping recording...")
        self.is_recording = False

        # Stop frame buffer
        if self.frame_buffer:
            self.frame_buffer.is_active = False
            if self.writer_thread and self.writer_thread.is_alive():
                self.writer_thread.join(timeout=5)

            # Log buffer stats
            stats = self.frame_buffer.get_stats()
            logger.info(f"Frame buffer stats: {stats['frames_written']} written, "
                       f"{stats['frames_dropped']} dropped ({stats['drop_rate']:.2f}% drop rate)")

        # Close FFmpeg stdin to signal end of input
        if self.ffmpeg_process and self.ffmpeg_process.stdin:
            try:
                self.ffmpeg_process.stdin.close()
                self.ffmpeg_process.wait(timeout=10)
                logger.info("✅ FFmpeg encoding finished")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ FFmpeg did not finish in time, terminating...")
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.wait(timeout=5)
            except Exception as e:
                logger.error(f"❌ Error stopping FFmpeg: {e}")

        # Calculate duration
        duration_seconds = 0
        if self.recording_start_time:
            duration_seconds = (datetime.now() - self.recording_start_time).total_seconds()

        # Save metadata
        metadata = {
            'filename': self.filename,
            'start_time': self.recording_start_time.isoformat() if self.recording_start_time else None,
            'duration_seconds': duration_seconds,
            'frame_count': self.frame_count,
            'fps': self.frame_count / duration_seconds if duration_seconds > 0 else 0,
            'detected_faces': self.detected_faces,
            'encoder': self.encoder_description,
            'buffer_stats': self.frame_buffer.get_stats() if self.frame_buffer else None
        }

        try:
            with open(self.metadata_filename, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"✅ Metadata saved: {self.metadata_filename}")
        except Exception as e:
            logger.error(f"❌ Failed to save metadata: {e}")

        # Check if file exists and has size > 0
        if os.path.exists(self.filename):
            file_size = os.path.getsize(self.filename)
            logger.info(f"✅ Recording saved: {self.filename} ({file_size / 1024 / 1024:.2f} MB)")
        else:
            logger.error(f"❌ Recording file not created: {self.filename}")
            return None

        # Save to database and link motion events
        try:
            from backend.database.utils import get_db_context
            from backend.database import crud
            from backend.database.models import MotionDetectionEvent, FaceDetectionEvent
            from backend.core.paths import paths

            with get_db_context() as db:
                # Get relative path for database storage
                relative_path = paths.get_relative_path(self.filename)

                camera_id = getattr(self, "camera_id", "unknown")

                # Count known vs unknown faces
                known_faces_count = sum(1 for face in self.detected_faces 
                                      if face.get("person_name", "Unknown") != "Unknown")
                unknown_faces_count = len(self.detected_faces) - known_faces_count

                recording_data = {
                    "camera_id": camera_id,
                    "recording_path": relative_path,
                    "started_at": self.recording_start_time,
                    "ended_at": datetime.now(),
                    "duration_seconds": duration_seconds,
                    "motion_detected": True,  # Always true if we're recording
                    "faces_detected": len(self.detected_faces),
                    "known_faces_detected": known_faces_count,
                    "file_size_bytes": file_size,
                    "frame_count": self.frame_count,
                }

                db_event = crud.create_recording_event(db, recording_data)
                self.last_recording_id = db_event.id
                logger.info(f"✅ Recording event created in database: ID={db_event.id}")
                
                # Link associated motion events to this recording
                if self.associated_motion_event_ids:
                    linked_count = db.query(MotionDetectionEvent).filter(
                        MotionDetectionEvent.id.in_(self.associated_motion_event_ids)
                    ).update(
                        {"recording_id": db_event.id, "recording_path": relative_path},
                        synchronize_session=False
                    )
                    db.commit()
                    logger.info(f"🔗 Linked {linked_count} motion events to recording ID={db_event.id}")
                
                # Also link any face detection events from this recording period
                if self.recording_start_time:
                    face_linked_count = db.query(FaceDetectionEvent).filter(
                        FaceDetectionEvent.camera_id == camera_id,
                        FaceDetectionEvent.detected_at >= self.recording_start_time,
                        FaceDetectionEvent.detected_at <= datetime.now(),
                        FaceDetectionEvent.recording_id.is_(None)
                    ).update(
                        {"recording_id": db_event.id, "recording_path": relative_path},
                        synchronize_session=False
                    )
                    db.commit()
                    if face_linked_count > 0:
                        logger.info(f"🔗 Linked {face_linked_count} face events to recording ID={db_event.id}")

        except Exception as db_error:
            logger.error(f"⚠️ Failed to save recording to database: {db_error}")
            import traceback
            traceback.print_exc()
            # Don't fail the entire operation if database save fails

        # Cleanup
        self.ffmpeg_process = None
        self.frame_buffer = None

        return metadata

    def is_recording_active(self) -> bool:
        """Check if recording is active"""
        return self.is_recording

    def get_recording_duration(self) -> float:
        """Get current recording duration in seconds"""
        if not self.is_recording or not self.recording_start_time:
            return 0.0
        return (datetime.now() - self.recording_start_time).total_seconds()

    def should_stop_recording(self) -> bool:
        """
        Check if recording should stop due to maximum duration exceeded.

        Returns:
            True if max duration exceeded, False otherwise
        """
        if not self.is_recording or not self.recording_start_time:
            return False

        duration = (datetime.now() - self.recording_start_time).total_seconds()
        if duration >= self.max_recording_duration:
            logger.info(f"⏱️ Max recording duration ({self.max_recording_duration}s) reached")
            return True
        return False

    def add_face_detection(self, face_data: Dict):
        """
        Add face detection data to the recording metadata.
        Compatible with legacy Recorder API.

        Args:
            face_data: Dictionary containing face detection information
        """
        if self.is_recording:
            face_data_copy = face_data.copy()
            face_data_copy["frame_number"] = self.frame_count
            face_data_copy["timestamp"] = (datetime.now() - self.recording_start_time).total_seconds() if self.recording_start_time else 0
            self.detected_faces.append(face_data_copy)

    def add_motion_event_id(self, motion_event_id: int):
        """
        Track a motion event ID associated with this recording.
        These will be linked to the recording when it stops.

        Args:
            motion_event_id: ID of the motion event to associate
        """
        if self.is_recording and motion_event_id:
            if motion_event_id not in self.associated_motion_event_ids:
                self.associated_motion_event_ids.append(motion_event_id)
                logger.info(f"📎 Linked motion event {motion_event_id} to current recording")
