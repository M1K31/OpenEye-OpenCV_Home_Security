# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Camera Manager - Enhanced with Granular Controls (v3.5.0)
Integrates motion detection, image processing, and video quality processors
"""

import os
import cv2
import logging
import numpy as np
import time
import sys
import threading
from abc import ABC, abstractmethod
from collections import deque
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
from backend.core.timeutil import utcnow
from .motion_detector import MotionDetector
from .image_processor import ImageProcessor
from .paths import paths  # single source of truth for snapshot/recording dirs

# This module historically used bare print() for everything, which is why camera
# failures had no level, no timestamp and no module name — and why a single
# repeated message could take over the log. New diagnostics go through logging so
# they can be filtered and rate-limited like everything else.
logger = logging.getLogger(__name__)
from .video_processor import VideoProcessor, VideoSettings
from .recorder import Recorder
from .ffmpeg_recorder import FFmpegRecorder, EncoderCapabilities
from .face_detection import FaceDetector
from .overlay_renderer import render_overlay
from .capture_process import CaptureClient

# Run capture in a child process instead of in this one.
#
# The in-process fixes (single owning thread, dead-capture flag, published
# frames) closed every crash path we found after the 2026-08-19/20 segfaults.
# They cannot close the next one: the fault is in C code Python cannot inspect.
# With isolation on, that crash kills a worker the parent restarts, and a fresh
# child also re-enumerates AVFoundation devices — which is the only thing that
# makes a camera attached AFTER launch visible.
#
# Default off. The in-process path is the one with real-world hours on it; this
# is opt-in until it has the same.
CAPTURE_ISOLATION = os.getenv("OPENEYE_CAPTURE_ISOLATION", "false").lower() == "true"

import asyncio
from backend.core.alert_manager import get_alert_manager
from backend.core.automation_engine import process_face_detection
from backend.database.session import SessionLocal
from backend.database.models import (
    Camera as CameraModel,
    MotionDetectionEvent,
    FaceDetectionEvent,
    FaceCluster,
    Person,
)
from backend.core.capture_policy import (
    CapturePolicy,
    CaptureSettings,
    MODE_SYSTEM_DEFAULT,
)
from backend.database.utils import get_db_context


class Camera(ABC):
    """
    Enhanced Camera base class with granular controls.

    New in v3.5.0:
    - Image quality processor integration
    - Video quality processor integration
    - Database settings loading
    - Dynamic settings reload
    """

    def __init__(
        self,
        source: str,
        camera_id: str = None,
        enable_face_detection: bool = True,
        db_settings: Optional[Dict[str, Any]] = None,
    ):
        self.source = source
        self.camera_id = camera_id
        self.capture = None
        self.is_running = False
        self.motion_detected = False
        self.last_motion_time = 0
        self.manual_record_until = 0.0  # automation-requested recording window (epoch seconds)
        self.post_motion_cooldown = 5  # Default, can be overridden from DB
        self.last_faces_detected = []
        self.current_motion_event_id = None  # Track current motion event for face linking
        # Throttle for UNKNOWN-person automation firing (presence/guest rules). A
        # continuously-visible unknown must not hammer the rules query every frame;
        # per-rule cooldowns still gate the actions themselves.
        self._last_unknown_automation_time = 0.0
        self.unknown_automation_min_interval = float(
            os.getenv("OPENEYE_UNKNOWN_AUTOMATION_INTERVAL", "10")
        )

        # Decides which recognised faces are worth keeping a likeness of. Holds
        # per-camera state, so one policy object per camera and not a shared one.
        # It governs storage only — automation runs from _act_on_face() whatever
        # this decides.
        # Names whose capture history has been read back from the database.
        # Seeded lazily and once: the query is cheap but pointless to repeat,
        # and most cameras see a handful of people.
        self._seeded_capture_history = set()
        # name -> whether a human has vouched for that identity. Cached because
        # this is consulted for every recognised face on every frame, and the
        # answer changes only when somebody names or confirms a person.
        self._person_confirmed: Dict[str, Optional[bool]] = {}
        self._capture_policy = CapturePolicy(
            CaptureSettings(
                required_consecutive_passes=int(
                    (db_settings or {}).get("capture_required_passes", 3)),
                cluster_maturity=int(
                    (db_settings or {}).get("capture_cluster_maturity", 25)),
            )
        )
        self.face_capture_mode = (db_settings or {}).get(
            "face_capture_mode", MODE_SYSTEM_DEFAULT)

        # Recording frame rate limiter - prevents fast playback
        # When recording, we limit frame writes to match the target FPS
        self.last_recording_frame_time = 0

        # Rolling window of recent processed-frame timestamps. Used to measure the
        # ACTUAL capture/processing fps so recordings are encoded at real-time
        # speed. Encoding at the nominal fps_target while the pipeline ran far
        # slower made playback appear sped up. `_recording_fps` freezes the
        # measured rate for the duration of one clip. See todos_changelog.md
        # (2026-07-25 — recording FPS accuracy).
        self._recent_frame_times = deque(maxlen=45)
        self._recording_fps = None

        # Load settings from database or use defaults
        settings = db_settings or {}

        # Initialize Motion Detector with granular controls (v3.5.7 enhanced - recommended defaults)
        self.motion_detector = MotionDetector(
            min_contour_area=settings.get("min_contour_area", 500),
            sensitivity=settings.get("motion_sensitivity", 5),
            var_threshold=settings.get("motion_threshold", 50),
            noise_reduction=settings.get("noise_reduction", "medium"),
            detect_shadows=settings.get("detect_shadows", True),
            detection_zones=settings.get("detection_zones"),
            lighting_compensation=settings.get("lighting_compensation_enabled", True),
            shadow_detection_method=settings.get("shadow_detection_method", "dual"),
            erosion_iterations=settings.get("erosion_iterations", 2),  # Recommended: 2
            dilation_iterations=settings.get("dilation_iterations", 3),  # Recommended: 3
            motion_persistence_frames=settings.get("motion_persistence_frames", 2),
            use_grayscale=settings.get("use_grayscale", True),
        )

        # Initialize Image Processor with quality controls
        self.image_processor = ImageProcessor(
            brightness=settings.get(
                "brightness", 0), contrast=settings.get(
                "contrast", 1.0), saturation=settings.get(
                "saturation", 1.0), sharpness=settings.get(
                    "sharpness", "none"), noise_reduction_strength=settings.get(
                        "noise_reduction_strength", 0), )

        # Initialize Video Processor with quality settings
        video_settings = VideoSettings(
            resolution=settings.get("resolution", "1920x1080"),
            fps_target=settings.get("fps_target", 15),
            bitrate_kbps=settings.get("bitrate_kbps", 2000),
            codec=settings.get("codec", "h264"),
        )
        self.video_processor = VideoProcessor(video_settings)

        # Initialize Recorder and Face Detector with system settings
        # Get system settings for paths and durations
        # Resolved through PathManager rather than passed through raw.
        #
        # These settings are stored as relative strings ("recordings", "faces",
        # "data/snapshots"), and handing them straight to the recorder meant it
        # resolved them against the process working directory. That was survivable
        # while the app was started by a script that cd'd into the right place. It
        # is not survivable in a bundle: the working directory is inside
        # OpenEye.app, so recordings were written into the application bundle
        # itself — a directory that is deleted and rebuilt on every update, and
        # that the download route correctly refuses to serve from because it sits
        # outside the configured recordings directory.
        recordings_path = str(paths.recordings_dir)
        max_recording_duration = settings.get("max_recording_duration", 300)
        faces_path = str(paths.faces_dir)
        snapshots_path = str(paths.snapshots_dir)

        # Check if hardware video encoding is enabled (v3.7.1+)
        use_hardware_encoding = settings.get("hardware_video_encoding", False)
        
        # Check if audio recording is enabled
        enable_audio = settings.get("audio_recording_enabled", False)
        audio_device = settings.get("audio_device", None)

        # Create recorder based on hardware encoding setting
        if use_hardware_encoding:
            # Use FFmpeg recorder with hardware acceleration
            try:
                self.recorder = FFmpegRecorder(
                    output_dir=recordings_path,
                    max_recording_duration=max_recording_duration,
                    use_hardware_encoding=True,
                    enable_frame_buffer=True,
                    buffer_size=300,
                    enable_audio=enable_audio,
                    audio_device=audio_device
                )
                audio_status = "with audio" if enable_audio else "without audio"
                print(f"✅ FFmpeg recorder initialized for camera '{camera_id}' with hardware acceleration ({audio_status})")
            except Exception as e:
                print(f"⚠️ Failed to initialize FFmpeg recorder, falling back to standard recorder: {e}")
                self.recorder = Recorder(
                    output_dir=recordings_path,
                    max_recording_duration=max_recording_duration
                )
        else:
            # Use standard OpenCV VideoWriter recorder (doesn't support audio)
            if enable_audio:
                print(f"⚠️ Audio recording requested but hardware encoding is disabled. Audio recording requires FFmpeg recorder.")
            self.recorder = Recorder(
                output_dir=recordings_path,
                max_recording_duration=max_recording_duration
            )

        # Initialize Face Detector with configurable settings
        # These settings allow tuning for different camera types and resolutions
        self.face_detector = FaceDetector(
            enabled=enable_face_detection,
            faces_dir=faces_path,
            scale_mode=settings.get("face_detection_scale", "auto"),  # "auto", "none", or "0.5"
            upsample_times=settings.get("face_detection_upsample", 1),  # 0, 1, or 2
            min_face_size=settings.get("min_face_size_pixels", 20),  # Minimum face size in pixels
            detection_cooldown=2.0,  # Seconds between detections
            # Only look for faces when something has moved recently. Recognition
            # is the most expensive work this process does and an empty room
            # needs none of it. Sticky, so a stationary person at a door is still
            # identified.
            requires_motion=settings.get("recognition_requires_motion", True),
            motion_sticky_seconds=float(
                settings.get("recognition_motion_window_seconds", 30)),
        )

        # Store snapshots path for motion detection
        self.snapshots_path = snapshots_path

        # Store motion percentage threshold (minimum % of frame with motion to trigger event)
        self.motion_percentage_threshold = settings.get("motion_percentage_threshold", 1.0) or 1.0

        # Overlay settings for timestamp and custom text
        self.overlay_enabled = settings.get("overlay_enabled", True)
        self.overlay_timestamp_enabled = settings.get("overlay_timestamp_enabled", True)
        self.overlay_custom_text = settings.get("overlay_custom_text", None)
        self.overlay_position = settings.get("overlay_position", "top-left")
        self.overlay_font_size = settings.get("overlay_font_size", 1)
        self.overlay_font_color = settings.get("overlay_font_color", "white")

        # Store settings for later updates
        self._db_settings = settings

        # Override post_motion_cooldown if provided in settings
        if "post_motion_cooldown" in settings:
            self.post_motion_cooldown = settings["post_motion_cooldown"]

        # ------------------------------------------------------------------
        # Published-frame buffer
        #
        # The last processed frame, so HTTP handlers can serve video WITHOUT
        # calling get_frame() and therefore without ever reaching
        # VideoCapture.read().
        #
        # This exists because OpenEye segfaulted twice on 2026-08-19/20 inside
        # OpenCV's AVFoundation backend. Both crashes were read() called from a
        # request thread against a capture whose device had gone away: once from
        # the MJPEG stream when a human opened the dashboard, once from the same
        # stream after a reconnect handed back a dead capture. A segfault kills
        # the process outright, so this has to be prevented structurally rather
        # than caught.
        # ------------------------------------------------------------------
        self._published_lock = threading.Condition()
        self._published_frame = None
        self._published_motion = False
        self._published_at = None
        self._published_seq = 0

    def _publish_frame(self, frame, motion_detected: bool) -> None:
        """Make a processed frame available to consumers that must not capture."""
        with self._published_lock:
            self._published_frame = frame
            self._published_motion = bool(motion_detected)
            self._published_at = time.time()
            self._published_seq += 1
            self._published_lock.notify_all()

    def get_published_frame(self, since_seq: int = None, timeout: float = 0.0):
        """
        Return the most recent processed frame without touching the capture.

        Returns (frame, motion_detected, seq), or None when nothing newer than
        since_seq arrived within timeout. Safe to call from any thread — that is
        the entire point of it.
        """
        with self._published_lock:
            if since_seq is not None and self._published_seq <= since_seq and timeout:
                self._published_lock.wait(timeout)
            if self._published_frame is None:
                return None
            if since_seq is not None and self._published_seq <= since_seq:
                return None
            return self._published_frame, self._published_motion, self._published_seq

    def seconds_since_last_frame(self):
        """Age of the published frame, or None if no frame has ever arrived."""
        with self._published_lock:
            if self._published_at is None:
                return None
            return time.time() - self._published_at

    def _record_frame_tick(self) -> None:
        """Record the timestamp of a processed frame (feeds measured_fps)."""
        self._recent_frame_times.append(time.time())

    def measured_fps(self) -> Optional[float]:
        """
        Actual processing fps from recent frames, or None if not enough samples.

        Recordings are encoded at this rate so playback matches real time even
        when per-frame detection keeps the pipeline well below fps_target.
        """
        times = self._recent_frame_times
        if len(times) < 5:
            return None
        span = times[-1] - times[0]
        if span <= 0:
            return None
        fps = (len(times) - 1) / span
        # Clamp AND round to a WHOLE number. cv2.VideoWriter with a fractional fps
        # emits duplicate presentation timestamps for consecutive frames
        # ("Invalid pts N <= last N" / "non monotonic dts"), which the encoder
        # rejects and drops. An integer fps keeps PTS strictly increasing.
        return float(max(1, min(60, round(fps))))

    def _resolve_recording_fps(self) -> float:
        """FPS to encode the next clip at: measured rate, else configured target."""
        return self.measured_fps() or (self.video_processor.settings.fps_target or 15)

    def request_recording(self, duration_seconds: int) -> None:
        """Ask the processing loop to record for the next N seconds.

        Called from the automation engine (possibly another thread); this is a
        GIL-protected read-then-max-write on a float; races only extend the
        window, never corrupt it. The loop starts recording on the next frame
        and won't stop while the window is open.
        """
        until = time.time() + max(1, int(duration_seconds))
        # extend, never shorten, an already-open window
        self.manual_record_until = max(self.manual_record_until, until)

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def get_frame(self):
        pass

    # Face detection methods
    def enable_face_detection(self, enabled: bool):
        """Enable or disable face detection for this camera"""
        self.face_detector.set_enabled(enabled)

    def get_face_statistics(self):
        """Get face detection statistics"""
        return self.face_detector.get_statistics()

    # NEW: Settings management methods
    def update_motion_settings(
        self,
        sensitivity: Optional[int] = None,
        var_threshold: Optional[int] = None,
        noise_reduction: Optional[str] = None,
        detect_shadows: Optional[bool] = None,
        detection_zones: Optional[str] = None,
        shadow_detection_method: Optional[str] = None,
        erosion_iterations: Optional[int] = None,
        dilation_iterations: Optional[int] = None,
        motion_persistence_frames: Optional[int] = None,
        use_grayscale: Optional[bool] = None,
        lighting_compensation: Optional[bool] = None,
        brightness_change_threshold: Optional[int] = None,
    ):
        """Update motion detection settings dynamically (v3.5.7 enhanced)"""
        self.motion_detector.update_settings(
            sensitivity=sensitivity,
            var_threshold=var_threshold,
            noise_reduction=noise_reduction,
            detect_shadows=detect_shadows,
            detection_zones=detection_zones,
            shadow_detection_method=shadow_detection_method,
            erosion_iterations=erosion_iterations,
            dilation_iterations=dilation_iterations,
            motion_persistence_frames=motion_persistence_frames,
            use_grayscale=use_grayscale,
            lighting_compensation=lighting_compensation,
            brightness_change_threshold=brightness_change_threshold,
        )

    def update_image_settings(
        self,
        brightness: Optional[int] = None,
        contrast: Optional[float] = None,
        saturation: Optional[float] = None,
        sharpness: Optional[str] = None,
        noise_reduction_strength: Optional[int] = None,
    ):
        """Update image quality settings dynamically"""
        self.image_processor.update_settings(
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            sharpness=sharpness,
            noise_reduction_strength=noise_reduction_strength,
        )

    def update_video_settings(
        self,
        resolution: Optional[str] = None,
        fps_target: Optional[int] = None,
        bitrate_kbps: Optional[int] = None,
        codec: Optional[str] = None,
    ):
        """Update video quality settings dynamically"""
        self.video_processor.update_settings(
            resolution=resolution,
            fps_target=fps_target,
            bitrate_kbps=bitrate_kbps,
            codec=codec,
        )

    def update_overlay_settings(
        self,
        overlay_enabled: Optional[bool] = None,
        timestamp_enabled: Optional[bool] = None,
        custom_text: Optional[str] = None,
        position: Optional[str] = None,
        font_size: Optional[int] = None,
        font_color: Optional[str] = None,
    ):
        """Update overlay settings dynamically"""
        if overlay_enabled is not None:
            self.overlay_enabled = overlay_enabled
        if timestamp_enabled is not None:
            self.overlay_timestamp_enabled = timestamp_enabled
        if custom_text is not None:
            self.overlay_custom_text = custom_text
        if position is not None:
            self.overlay_position = position
        if font_size is not None:
            self.overlay_font_size = font_size
        if font_color is not None:
            self.overlay_font_color = font_color

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all current camera settings"""
        return {
            "motion": self.motion_detector.get_settings(),
            "image": self.image_processor.get_settings(),
            "video": self.video_processor.get_settings(),
            "post_motion_cooldown": self.post_motion_cooldown,
            "overlay": {
                "enabled": self.overlay_enabled,
                "timestamp_enabled": self.overlay_timestamp_enabled,
                "custom_text": self.overlay_custom_text,
                "position": self.overlay_position,
                "font_size": self.overlay_font_size,
                "font_color": self.overlay_font_color,
            },
        }

    def reload_settings_from_db(self):
        """Reload settings from database"""
        if not self.camera_id:
            return

        try:
            # FIX v3.6.0.1: Use context manager to prevent session leak
            with get_db_context() as db:
                db_camera = (
                    db.query(CameraModel)
                    .filter(CameraModel.camera_id == self.camera_id)
                    .first()
                )

                if db_camera:
                    # Update motion settings (v3.5.7 enhanced - recommended defaults)
                    self.update_motion_settings(
                        sensitivity=db_camera.motion_sensitivity,
                        var_threshold=db_camera.motion_threshold,
                        noise_reduction=db_camera.noise_reduction,
                        detect_shadows=db_camera.detect_shadows,
                        detection_zones=db_camera.detection_zones,
                        shadow_detection_method=getattr(db_camera, 'shadow_detection_method', 'dual'),
                        erosion_iterations=getattr(db_camera, 'erosion_iterations', 2),
                        dilation_iterations=getattr(db_camera, 'dilation_iterations', 3),
                        motion_persistence_frames=getattr(db_camera, 'motion_persistence_frames', 2),
                        use_grayscale=getattr(db_camera, 'use_grayscale', True),
                        lighting_compensation=getattr(db_camera, 'lighting_compensation_enabled', True),
                        brightness_change_threshold=getattr(db_camera, 'brightness_change_threshold', 15),
                    )

                    # Update motion percentage threshold (default to 1.0 if not set)
                    self.motion_percentage_threshold = db_camera.motion_percentage_threshold if db_camera.motion_percentage_threshold is not None else 1.0

                    # Update image settings
                    self.update_image_settings(
                        brightness=db_camera.brightness,
                        contrast=db_camera.contrast,
                        saturation=db_camera.saturation,
                        sharpness=db_camera.sharpness,
                        noise_reduction_strength=db_camera.noise_reduction_strength,
                    )

                    # Update video settings
                    self.update_video_settings(
                        resolution=db_camera.resolution,
                        fps_target=db_camera.fps_target,
                        bitrate_kbps=db_camera.bitrate_kbps,
                        codec=db_camera.codec,
                    )

                    # Update other settings
                    self.post_motion_cooldown = db_camera.post_motion_cooldown

                    print(f"Settings reloaded for camera '{self.camera_id}' from database")
                # Session automatically closed by context manager
        except Exception as e:
            print(f"Error reloading settings from database: {e}")

    def _save_motion_snapshot(
        self, frame: np.ndarray, motion_areas: list
    ) -> Optional[str]:
        """
        Save a motion detection snapshot to disk.

        Args:
            frame: The frame with motion detected
            motion_areas: List of motion area dictionaries

        Returns:
            Path to the saved snapshot or None if save failed
        """
        try:
            # Create snapshots directory if it doesn't exist
            # Use custom path from settings or default
            # Save under paths.snapshots_dir so the write location matches the
            # /data/snapshots and /api/snapshots static mounts (both serve
            # paths.snapshots_dir). Previously this used the cwd-relative
            # self.snapshots_path default ('data/snapshots'), which diverged from
            # the mount when OPENEYE_SNAPSHOTS_DIR was set → every snapshot 404'd
            # in the face-review UI, and files landed in the disposable app copy.
            snapshots_dir = paths.snapshots_dir
            snapshots_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            camera_name = self.camera_id or "unknown"
            filename = f"motion_{camera_name}_{timestamp}.jpg"
            snapshot_path = snapshots_dir / filename

            # Save the frame
            success = cv2.imwrite(str(snapshot_path), frame)

            if success:
                # Return URL path format for frontend access
                return f"/data/snapshots/{filename}"
            else:
                print(f"Failed to save snapshot to {snapshot_path}")
                return None

        except Exception as e:
            print(f"Error saving motion snapshot: {e}")
            return None

    def _create_motion_event(
        self,
        frame: np.ndarray,
        motion_areas: list,
        snapshot_path: Optional[str] = None,
        triggered_zone_ids: Optional[list] = None,
    ) -> Optional[int]:
        """
        Create a MotionDetectionEvent in the database.

        Args:
            frame: The frame where motion was detected
            motion_areas: List of motion area dictionaries
            snapshot_path: Path to the saved snapshot (optional)
            triggered_zone_ids: List of zone IDs that triggered this event (optional)

        Returns:
            The ID of the created motion event or None if creation failed
        """
        if not self.camera_id:
            return None

        try:
            # FIX v3.6.0.1: Use context manager to prevent session leak
            with get_db_context() as db:
                # Calculate total motion area and percentage
                frame_area = frame.shape[0] * frame.shape[1]
                total_motion_area = sum(area.get("area", 0)
                                        for area in motion_areas)
                motion_percentage = (total_motion_area /
                                     frame_area * 100) if frame_area > 0 else 0

                # Get recording path if currently recording
                recording_path = None
                if self.recorder.is_recording and hasattr(self.recorder, "filename"):
                    recording_path = self.recorder.filename

                # Serialize triggered zones to JSON if provided
                triggered_zones_json = None
                if triggered_zone_ids:
                    import json
                    triggered_zones_json = json.dumps(triggered_zone_ids)

                # Create motion event
                motion_event = MotionDetectionEvent(
                    camera_id=self.camera_id,
                    # UTC, like every other persisted timestamp.
                    #
                    # This previously used local time deliberately, to match
                    # face events which also used it — correct in that the two
                    # finally agreed, wrong in which direction they were made to
                    # agree. Storage should not know where the viewer is. The
                    # display problem that motivated it is solved at the API
                    # boundary instead, where timestamps are marked as UTC and
                    # the browser converts them.
                    detected_at=utcnow(),
                    motion_area=total_motion_area,
                    motion_percentage=motion_percentage,
                    contour_count=len(motion_areas),
                    snapshot_path=snapshot_path,
                    frame_width=frame.shape[1],
                    frame_height=frame.shape[0],
                    recording_path=recording_path,
                    triggered_zones=triggered_zones_json,
                )

                db.add(motion_event)
                db.commit()
                db.refresh(motion_event)

                event_id = motion_event.id
                # Session automatically closed by context manager

                print(f"Created motion event {event_id} for camera {self.camera_id}: {motion_percentage:.1f}% motion, {len(motion_areas)} contours")
                return event_id

        except Exception as e:
            print(f"Error creating motion event in database: {e}")
            return None

    def _update_motion_event_faces(self, motion_event_id: int, face_count: int):
        """
        Update a motion event with the number of faces detected.

        Args:
            motion_event_id: ID of the motion event to update
            face_count: Number of faces detected
        """
        if not motion_event_id:
            return

        try:
            # FIX v3.6.0.1: Use context manager to prevent session leak
            with get_db_context() as db:
                motion_event = db.query(MotionDetectionEvent).filter(
                    MotionDetectionEvent.id == motion_event_id
                ).first()

                if motion_event:
                    motion_event.faces_detected = face_count
                    db.commit()
                    print(
                        f"Updated motion event {motion_event_id} with {face_count} faces detected")
                # Session automatically closed by context manager
        except Exception as e:
            print(f"Error updating motion event with faces: {e}")

    def _save_face_snapshot(self, frame: np.ndarray, face_location: dict) -> Optional[str]:
        """
        Save a face detection snapshot to disk.

        Args:
            frame: The frame with the detected face
            face_location: Dictionary with top, right, bottom, left coordinates

        Returns:
            Path to the saved snapshot or None if save failed
        """
        try:
            # Create snapshots directory if it doesn't exist
            # Save under paths.snapshots_dir so the write location matches the
            # /data/snapshots and /api/snapshots static mounts (both serve
            # paths.snapshots_dir). Previously this used the cwd-relative
            # self.snapshots_path default ('data/snapshots'), which diverged from
            # the mount when OPENEYE_SNAPSHOTS_DIR was set → every snapshot 404'd
            # in the face-review UI, and files landed in the disposable app copy.
            snapshots_dir = paths.snapshots_dir
            snapshots_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            camera_name = self.camera_id or "unknown"
            filename = f"face_{camera_name}_{timestamp}.jpg"
            snapshot_path = snapshots_dir / filename

            # Crop face region with some padding
            top = max(0, face_location.get("top", 0) - 20)
            right = min(frame.shape[1], face_location.get("right", frame.shape[1]) + 20)
            bottom = min(frame.shape[0], face_location.get("bottom", frame.shape[0]) + 20)
            left = max(0, face_location.get("left", 0) - 20)

            face_crop = frame[top:bottom, left:right]

            # Save the cropped face
            success = cv2.imwrite(str(snapshot_path), face_crop)

            if success:
                # Return URL path format for frontend access
                return f"/data/snapshots/{filename}"
            else:
                print(f"Failed to save face snapshot to {snapshot_path}")
                return None
        except Exception as e:
            print(f"Error saving face snapshot: {e}")
            return None

    def _act_on_face(self, face: dict) -> None:
        """
        Run the user's automation rules for a recognised face.

        Separate from recording it, and unconditional. Whether a likeness is
        worth keeping is a storage question; whether to unlock a door, change
        the lighting or warn an intruder is not, and the two were previously the
        same function. Every suppression added to the capture policy would
        otherwise have quietly suppressed an automation too.

        Known persons fire every detection. Unknown persons also fire — presence
        and guest-service rules target "Unknown" — but throttled per camera so a
        continuously visible stranger does not hammer the rules query. The
        per-rule cooldown still gates the actions themselves.
        """
        if not self.camera_id:
            return

        person_name = face.get("name", "Unknown")

        fire_automation = person_name != "Unknown"
        if not fire_automation:
            now_ts = time.time()
            if now_ts - self._last_unknown_automation_time >= self.unknown_automation_min_interval:
                self._last_unknown_automation_time = now_ts
                fire_automation = True

        if not fire_automation:
            return

        try:
            process_face_detection(
                person_name=person_name,
                camera_id=self.camera_id,
                confidence=face.get("confidence", 0.0),
                detected_at=utcnow(),
            )
        except Exception as e:
            print(f"Error processing automation rules for {person_name}: {e}")

    def _handle_detected_faces(self, frame: np.ndarray, faces: list) -> None:
        """
        Act on every recognised face, and record the ones worth keeping.

        The order matters: acting comes first and is never skipped, so an
        automation cannot be lost to a storage decision made afterwards.

        This replaces two identical copies of the same loop, one in each frame
        path. They had already drifted into being maintained in parallel, which
        is how a fix to one could silently miss the other.
        """
        if not faces:
            return

        for face in faces:
            self._act_on_face(face)

            self._seed_capture_history(
                (face.get("name") or "Unknown").strip() or "Unknown")
            cluster_size, cluster_trained = self._cluster_state_for(face)
            decision = self._capture_policy.evaluate(
                face,
                camera_id=self.camera_id or "unknown",
                mode=self.face_capture_mode,
                cluster_face_count=cluster_size,
                cluster_is_trained=cluster_trained,
                cluster_id=face.get("cluster_id"),
                person_confirmed=self._is_person_confirmed(
                    (face.get("name") or "").strip()),
            )

            snapshot_path = None
            if decision.capture:
                snapshot_path = self._save_face_snapshot(
                    frame, face.get("location", {})
                )
            else:
                # Periodically, at a level that is actually visible. This was
                # debug-only, so an installation where every capture was being
                # suppressed — the correct behaviour once a person's cluster is
                # well established — looked from the outside like face capture
                # had simply stopped working, with nothing in the log to say
                # otherwise. Rate-limited because the alternative is a line per
                # detection per camera.
                self._suppressed_captures = getattr(self, "_suppressed_captures", 0) + 1
                if self._suppressed_captures % 100 == 1:
                    logger.info(
                        "Not capturing %s on %s: %s (%s suppressed so far; "
                        "sightings are still recorded)",
                        face.get("name"), self.camera_id, decision.reason,
                        self._suppressed_captures,
                    )

            if decision.capture or decision.record_sighting:
                # A sighting keeps the events page, per-person history and an
                # unknown person's location record intact. Without a snapshot it
                # carries no encoding either, so it never feeds clustering or
                # training — which is the cost being avoided.
                self._create_face_detection_event(
                    frame, face, snapshot_path,
                    store_encoding=decision.capture,
                )

    def _seed_capture_history(self, name: str) -> None:
        """
        Recover "already captured today" from what was actually captured.

        The capture policy keeps its state in memory, so quitting and reopening
        the application forgot that someone had already been photographed today
        and the next sighting captured again. In the desktop build, where
        restarting is something a user does rather than a rare event, that made
        "once a day per camera" behave as "once a launch per camera".

        Nothing new is stored to fix it. Every capture already leaves a detection
        row carrying a snapshot path, so the most recent one for this person on
        this camera is exactly the timestamp the policy lost.
        """
        if name in self._seeded_capture_history:
            return
        self._seeded_capture_history.add(name)

        try:
            with get_db_context() as db:
                row = (
                    db.query(FaceDetectionEvent.detected_at)
                    .filter(
                        FaceDetectionEvent.person_name == name,
                        FaceDetectionEvent.camera_id == self.camera_id,
                        FaceDetectionEvent.snapshot_path.isnot(None),
                    )
                    .order_by(FaceDetectionEvent.detected_at.desc())
                    .first()
                )
        except Exception as e:
            # Failing to seed only costs one extra capture, so this must never
            # take the camera down with it.
            logger.debug("Could not seed capture history for %s: %s", name, e)
            return

        if row and row[0]:
            self._capture_policy.seed_last_capture(
                name, self.camera_id, row[0].timestamp())
            logger.info(
                "Capture history for %s on %s resumed from %s",
                name, self.camera_id, row[0],
            )

    def _is_person_confirmed(self, name: str) -> Optional[bool]:
        """
        Whether a human has vouched for this identity.

        None when there is no person record — an older installation before the
        migration, or a name nothing has registered yet. The capture policy
        treats None as "do not know" and applies the ordinary rules, so an
        un-migrated install behaves exactly as it did.
        """
        if not name or name == "Unknown":
            return None
        if name in self._person_confirmed:
            return self._person_confirmed[name]

        answer: Optional[bool] = None
        try:
            with get_db_context() as db:
                person = db.query(Person).filter(Person.name == name).first()
                if person is not None:
                    answer = person.is_confirmed
        except Exception as e:
            logger.debug("Could not read person '%s': %s", name, e)

        self._person_confirmed[name] = answer
        return answer

    def forget_person_cache(self) -> None:
        """
        Drop the confirmation cache.

        Called after a person is named or confirmed, so the change takes effect
        on the next frame rather than the next restart — the difference between
        naming somebody and watching capture behaviour change, and naming
        somebody and wondering whether it worked.
        """
        self._person_confirmed.clear()

    def _cluster_state_for(self, face: dict) -> Tuple[Optional[int], Optional[bool]]:
        """
        The size of the cluster this detection belongs to, and whether that
        cluster has been trained into a profile.

        Both are needed together: size says the cluster is well represented,
        trained says there is a route by which it stays current. Stopping
        collection on size alone would strand a cluster that never got promoted.

        Only the recogniser's own cluster association is consulted; running a
        fresh similarity search here would reintroduce exactly the per-frame
        cost this work exists to remove.
        """
        cluster_id = face.get("cluster_id")
        if not cluster_id:
            return None, None

        try:
            with get_db_context() as db:
                cluster = db.query(FaceCluster).filter(
                    FaceCluster.id == cluster_id
                ).first()
                if cluster is None:
                    return None, None
                return cluster.face_count, cluster.trained_at is not None
        except Exception as e:
            logger.debug("Could not read cluster state: %s", e)
            return None, None

    def _create_face_detection_event(
        self,
        frame: np.ndarray,
        face: dict,
        snapshot_path: Optional[str] = None,
        store_encoding: bool = True,
    ) -> Optional[int]:
        """
        Create a FaceDetectionEvent in the database with face encoding for clustering.

        Args:
            frame: The frame where the face was detected
            face: Dictionary with face detection data (name, confidence, location, encoding)
            snapshot_path: Path to the saved face snapshot (optional)

        Returns:
            The ID of the created face detection event or None if creation failed
        """
        if not self.camera_id:
            return None

        try:
            # FIX v3.6.0.1: Use context manager to prevent session leak
            with get_db_context() as db:
                # Get recording path if currently recording
                recording_path = None
                recording_id = None
                if self.recorder.is_recording and hasattr(self.recorder, "filename"):
                    recording_path = self.recorder.filename
                    # TODO: Get recording_id from database if needed

                location = face.get("location", {})

                # Create face detection event
                face_event = FaceDetectionEvent(
                    camera_id=self.camera_id,
                    person_name=face.get("name", "Unknown"),
                    confidence=face.get("confidence", 0.0),
                    detected_at=utcnow(),
                    location_top=location.get("top", 0),
                    location_right=location.get("right", 0),
                    location_bottom=location.get("bottom", 0),
                    location_left=location.get("left", 0),
                    snapshot_path=snapshot_path,
                    recording_path=recording_path,
                    recording_id=recording_id,
                    motion_detected=face.get("motion_detected", False),
                    frame_width=frame.shape[1],
                    frame_height=frame.shape[0],
                    # Only a captured likeness carries an encoding. A sighting
                    # row records who and where without giving clustering or
                    # training anything new to chew on.
                    face_encoding=face.get("encoding") if store_encoding else None,
                )

                db.add(face_event)
                db.commit()
                db.refresh(face_event)

                event_id = face_event.id
                person_name = face.get("name", "Unknown")
                confidence = face.get("confidence", 0.0)
                # Session automatically closed by context manager

                print(
                    f"Created face detection event {event_id} for camera {self.camera_id}: "
                    f"{person_name} (confidence: {confidence:.2f})"
                )

                # NOTE: automation used to fire from here. It now runs in
                # _act_on_face(), called from the frame loop for every recognised
                # face, because this function is about to become conditional.
                # Leaving the two coupled would have meant that throttling
                # captures also throttled automations — lights not changing,
                # access not granted — and it would have failed silently, since
                # fewer captures is exactly what success looks like.
                return event_id

        except Exception as e:
            print(f"Error creating face detection event in database: {e}")
            return None


class MockCamera(Camera):
    """Enhanced MockCamera with granular controls"""

    def __init__(
        self,
        source: str = "mock",
        camera_id: str = None,
        enable_face_detection: bool = True,
        db_settings: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(source, camera_id, enable_face_detection, db_settings)
        self.width = 640
        self.height = 480
        self.frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

    def start(self):
        self.is_running = True
        print("Mock camera started.")

        # Load polygon-based motion zones from database (v3.6.2+)
        if self.camera_id:
            try:
                db = SessionLocal()
                self.motion_detector.load_polygon_zones(self.camera_id, db)
            except Exception as e:
                print(f"Warning: Could not load motion zones: {e}")
            finally:
                if db:
                    db.close()

    def stop(self):
        if self.recorder.is_recording:
            self.recorder.stop()
        self.is_running = False
        print("Mock camera stopped.")

    def get_frame(self):
        if not self.is_running:
            return None, False

        # Check if we should process this frame based on FPS target
        if not self.video_processor.should_process_frame():
            return None, False

        # Sample the real frame cadence (drives measured_fps for accurate encoding).
        self._record_frame_tick()

        # Create a blank frame with a timestamp
        self.frame.fill(0)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cv2.putText(
            self.frame,
            f"Mock Camera",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            self.frame,
            timestamp,
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        # Add a moving circle for visual feedback
        seconds = int(time.time())
        x = int(self.width / 2 + 100 * np.cos(seconds))
        y = int(self.height / 2 + 100 * np.sin(seconds))
        cv2.circle(self.frame, (x, y), 20, (0, 255, 0), -1)

        # Store clean frame for recording
        clean_frame = self.frame.copy()

        # Apply video processing (resolution adjustment if needed)
        processed_frame = self.video_processor.process_frame(clean_frame)

        # Apply image quality adjustments
        if self.image_processor.has_adjustments():
            processed_frame = self.image_processor.process(processed_frame)

        # Motion detection on processed frame
        # draw_boxes=False to only show face detection boxes, not motion boxes
        processed_frame, self.motion_detected, motion_areas, triggered_zone_ids = (
            self.motion_detector.detect(processed_frame, draw_boxes=False)
        )

        # Check motion percentage threshold before triggering event
        # If motion_areas is empty but motion_detected is True, reset motion_detected
        # This handles edge cases like lighting compensation where motion is suppressed
        if self.motion_detected and not motion_areas:
            self.motion_detected = False
            triggered_zone_ids = []
        elif self.motion_detected and motion_areas:
            # Calculate motion percentage
            frame_area = processed_frame.shape[0] * processed_frame.shape[1]
            total_motion_area = sum(area.get("area", 0) for area in motion_areas)
            motion_percentage = (total_motion_area / frame_area * 100) if frame_area > 0 else 0

            # Only trigger if motion percentage exceeds threshold
            if motion_percentage < self.motion_percentage_threshold:
                # Motion detected but below threshold - ignore it
                self.motion_detected = False
                motion_areas = []
                triggered_zone_ids = []

        # Trigger motion alert if motion detected (and has motion areas)
        if self.motion_detected and motion_areas:
            # Save snapshot and create database record
            snapshot_path = self._save_motion_snapshot(
                processed_frame, motion_areas)
            self.current_motion_event_id = self._create_motion_event(
                processed_frame, motion_areas, snapshot_path, triggered_zone_ids
            )

            try:
                alert_manager = get_alert_manager()
                camera_id = self.camera_id or "mock_cam"
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            alert_manager.trigger_motion_alert(
                                camera_id=camera_id,
                                event_data={
                                    "timestamp": time.time(),
                                    "motion_areas": motion_areas,
                                    "motion_event_id": self.current_motion_event_id,
                                    "snapshot_path": snapshot_path,
                                },
                            ),
                            loop,
                        )
                except RuntimeError:
                    # No event loop running, skip alert
                    pass
            except Exception as e:
                print(f"Error triggering motion alert: {e}")
        else:
            # Clear motion event when no motion detected
            self.current_motion_event_id = None

        # Face detection
        if self.face_detector.enabled:
            processed_frame, self.last_faces_detected = (
                self.face_detector.process_frame(
                    processed_frame, self.motion_detected))

            # Act on every face, record the ones worth keeping.
            self._handle_detected_faces(processed_frame, self.last_faces_detected)

            # Update motion event with face count if faces detected
            if self.last_faces_detected and self.current_motion_event_id:
                self._update_motion_event_faces(
                    self.current_motion_event_id, len(
                        self.last_faces_detected)
                )

            # Log faces to recorder if recording
            if self.recorder.is_recording and self.last_faces_detected:
                for face in self.last_faces_detected:
                    self.recorder.add_face_detection(face)

        # Recording logic
        manual_record = time.time() < self.manual_record_until
        if self.motion_detected or manual_record:
            if self.motion_detected:
                self.last_motion_time = time.time()
            if not self.recorder.is_recording:
                # Encode at the MEASURED capture rate so playback matches real time
                # (nominal fps_target overshot the achieved rate → sped-up playback).
                self._recording_fps = self._resolve_recording_fps()
                self.recorder.start(self.width, self.height, fps=self._recording_fps, camera_id=self.camera_id or "mock")
                self.last_recording_frame_time = 0  # Reset frame time for new recording

            # Link motion event to the recording (if recording is active)
            if self.recorder.is_recording and self.current_motion_event_id:
                self.recorder.add_motion_event_id(self.current_motion_event_id)

        if self.recorder.is_recording:
            # Add recording indicator to the processed frame for streaming
            cv2.circle(processed_frame, (self.width - 30, 30),
                       10, (0, 0, 255), -1)

            # Frame rate limiting for recording - prevents fast playback. Use the
            # same measured rate the writer was created with so writes and the
            # encoded fps stay consistent.
            recording_fps = self._recording_fps or self._resolve_recording_fps()
            frame_interval = 1.0 / recording_fps
            current_time = time.time()

            if current_time - self.last_recording_frame_time >= frame_interval:
                self.recorder.write(clean_frame)  # Write clean frame to file
                self.last_recording_frame_time = current_time

            # Stop recording if: no motion for cooldown period OR max duration
            # exceeded
            if (
                not manual_record
                and (
                    not self.motion_detected
                    and (time.time() - self.last_motion_time > self.post_motion_cooldown)
                )
            ) or self.recorder.should_stop_recording():
                self.recorder.stop()

        # Apply timestamp/custom text overlay (for streaming only, not recording)
        processed_frame = render_overlay(
            processed_frame,
            overlay_enabled=self.overlay_enabled,
            timestamp_enabled=self.overlay_timestamp_enabled,
            custom_text=self.overlay_custom_text,
            position=self.overlay_position,
            font_size=self.overlay_font_size,
            font_color=self.overlay_font_color
        )

        # Publish alongside RTSPCamera so consumers have one interface for both
        # camera types and never need to know which they are talking to.
        self._publish_frame(processed_frame, self.motion_detected)

        return processed_frame, self.motion_detected


class RTSPCamera(Camera):
    """Enhanced RTSPCamera with granular controls and background processing"""

    def __init__(
        self,
        source: str,
        camera_id: str = None,
        enable_face_detection: bool = True,
        db_settings: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(source, camera_id, enable_face_detection, db_settings)
        self._background_thread = None
        self._stop_background = threading.Event()
        self._frame_lock = threading.Lock()  # Lock for thread-safe frame access
        # Enable background processing by default for 24/7 surveillance
        self._background_processing_enabled = db_settings.get("background_processing", True) if db_settings else True

        # Failure tracking, so a camera that goes away is handled once rather than
        # rediscovered ten times a second.
        #
        # Previously every failed read printed a line and retried after 0.1s. A
        # phone that locked overnight produced 18,665 lines — 96.6% of the entire
        # log — and the handle was never reopened, so the camera stayed dead until
        # the whole service restarted. Both halves of that are fixed here: log the
        # transition rather than the attempt, and actually try to recover.
        self._consecutive_failures = 0
        self._failure_since = None
        self._last_failure_log = 0.0
        self._reconnect_attempts = 0
        self._was_connected = False

        # Set once the capture is judged unusable. While set, get_frame() returns
        # immediately and NEVER calls read(). Only _reopen_capture() clears it,
        # and only after proving a new capture delivers a frame.
        self._capture_dead = threading.Event()

        # Thread id of the capture loop. Any other thread calling get_frame() is
        # a bug, and is refused rather than allowed to reach read(). Both
        # segfaults came through a request thread; naming the owner turns "only
        # the capture loop reads" from a convention into something enforced.
        self._capture_owner_thread = None

        # Retrying a dead capture is driven by the clock, not by the failure
        # counter. Once the capture is marked dead, get_frame() returns before
        # _note_frame_failure() runs, so _consecutive_failures stops growing —
        # and the old trigger (`failures % RECONNECT_AFTER_FAILURES == 0`) could
        # then never fire again. An unplugged camera went dead and stayed dead
        # until the process restarted. Confirmed against real hardware.
        self._next_reopen_attempt = 0.0
        self._reopen_backoff = 1.0

    # Consecutive failed reads before the capture is considered lost and reopened.
    # ~2s at the background loop's cadence: long enough to ride out a dropped
    # frame, short enough that a real disconnect is handled promptly.
    RECONNECT_AFTER_FAILURES = int(os.getenv("OPENEYE_RECONNECT_AFTER_FAILURES", "20"))
    RECONNECT_BACKOFF_MAX = float(os.getenv("OPENEYE_RECONNECT_BACKOFF_MAX", "60"))
    FAILURE_LOG_INTERVAL = 60.0   # seconds between "still down" heartbeats

    # Consecutive failed reads before the capture is declared DEAD and released.
    # Much smaller than RECONNECT_AFTER_FAILURES on purpose: that counter governs
    # how often we retry, this one governs how long we keep messaging a possibly
    # freed object. At the loop's ~10fps this is about a third of a second, well
    # inside the six seconds that separated the first failed read from the
    # segfault on 2026-08-20.
    FATAL_AFTER_FAILURES = int(os.getenv("OPENEYE_FATAL_AFTER_FAILURES", "3"))

    # How long a proven-working reopen may spend waiting for its first frame.
    REOPEN_PROVE_SECONDS = float(os.getenv("OPENEYE_REOPEN_PROVE_SECONDS", "2"))

    def is_capture_dead(self) -> bool:
        """True when the capture has been released and must not be read."""
        return self._capture_dead.is_set()

    def _mark_capture_dead(self, reason: str) -> None:
        """
        Declare the capture unusable, release it, and stop reading from it.

        Releasing here is deliberate and is the last time we touch the object.
        The alternative — leaving it open and retrying — is what killed the
        process twice: capture.isOpened() keeps returning True for a device that
        has gone away, so every subsequent read() is a message to freed memory.
        """
        if self._capture_dead.is_set():
            return
        self._capture_dead.set()
        logger.error(
            "Camera %s: capture marked DEAD (%s). No further reads will be "
            "attempted until a reopen proves a working capture.",
            self._describe_self(), reason)

        with self._frame_lock:
            capture, self.capture = self.capture, None
        if capture is not None:
            try:
                capture.release()
            except Exception as e:
                logger.debug("Releasing dead capture for %s raised %s",
                             self.camera_id, e)

    def _describe_self(self) -> str:
        """Camera id and its real source type, for log messages."""
        try:
            int(self.source)
            kind = "USB/local index"
        except (ValueError, TypeError):
            kind = "stream URL"
        return f"{self.camera_id} ({kind} {self.source})"

    def _note_frame_failure(self):
        """
        Record a failed read, logging the transition rather than every attempt.

        The old code printed "Failed to grab frame from RTSP stream." on every
        failure, for every camera type. It was wrong twice over: it named RTSP
        when the camera was a USB webcam or an iPhone, which actively misled
        diagnosis, and at ten failures a second it buried everything else in the
        log — 18,665 lines from a single phone that had gone to sleep.
        """
        now = time.time()
        self._consecutive_failures += 1

        if self._consecutive_failures == 1:
            self._failure_since = now
            self._last_failure_log = now
            logger.warning("Camera %s stopped delivering frames", self._describe_self())
        elif (now - self._last_failure_log) >= self.FAILURE_LOG_INTERVAL:
            self._last_failure_log = now
            down_for = int(now - (self._failure_since or now))
            logger.warning(
                "Camera %s still down after %ss (%s failed reads)",
                self._describe_self(), down_for, self._consecutive_failures)

        # Stop reading before the next read can hit freed memory. The device may
        # simply be busy, in which case the reopen below brings it straight back
        # — that costs a couple of seconds. Guessing wrong the other way costs
        # the whole process.
        if self._consecutive_failures >= self.FATAL_AFTER_FAILURES:
            self._mark_capture_dead(
                f"{self._consecutive_failures} consecutive failed reads")

    def _note_frame_success(self):
        """Record a good read, and announce recovery if we had been failing."""
        if self._consecutive_failures:
            down_for = int(time.time() - (self._failure_since or time.time()))
            logger.info(
                "Camera %s recovered after %ss (%s failed reads)",
                self._describe_self(), down_for, self._consecutive_failures)
        self._consecutive_failures = 0
        self._failure_since = None
        self._reconnect_attempts = 0
        self._was_connected = True

    def _maybe_reopen_dead_capture(self) -> bool:
        """
        Retry a dead capture when its backoff has elapsed. True if attempted.

        Independent of the failure counter on purpose: a dead capture is not
        being read, so nothing is counting, and recovery must not depend on a
        number that has stopped moving.
        """
        if not self._capture_dead.is_set():
            return False

        now = time.time()
        if self._next_reopen_attempt and now < self._next_reopen_attempt:
            return False

        self._reconnect_attempts += 1
        logger.info(
            "Camera %s: retrying dead capture (attempt #%s)",
            self._describe_self(), self._reconnect_attempts)

        recovered = self._reopen_capture()

        if recovered:
            self._reopen_backoff = 1.0
            self._next_reopen_attempt = 0.0
        else:
            # Back off so an absent camera costs one open a minute rather than
            # a spin loop, but keep trying — the device may come back at any time.
            self._next_reopen_attempt = time.time() + self._reopen_backoff
            self._reopen_backoff = min(
                self._reopen_backoff * 2, self.RECONNECT_BACKOFF_MAX)
        return True

    def _reopen_capture(self) -> bool:
        """
        Release the capture and open it again. Returns True if frames resume.

        This is the piece whose absence meant a camera that blipped was gone
        until the whole service restarted: the capture was opened once at start
        and never reopened, so a webcam unplugged and plugged straight back in
        stayed dead while macOS listed it as present the entire time.

        Releasing first is essential — reopening without releasing hands back the
        same dead handle. The pause afterwards is not superstition either: on
        macOS an immediate reopen can return a capture that never delivers a
        frame, which is why a hurried restart earlier produced a process that was
        born broken.
        """
        with self._frame_lock:
            try:
                if self.capture is not None:
                    self.capture.release()
            except Exception as e:
                logger.debug("Releasing capture for %s raised %s", self.camera_id, e)
            self.capture = None

        time.sleep(float(os.getenv("OPENEYE_RECONNECT_SETTLE_SECONDS", "2")))

        try:
            try:
                device_index = int(self.source)
                if CAPTURE_ISOLATION:
                    # A NEW child process, which is what re-enumerates devices.
                    # This is why isolation also fixes "camera attached after
                    # launch is never seen".
                    capture = CaptureClient(
                        source=self.source, camera_id=self.camera_id or "camera",
                        target_fps=self.video_processor.settings.fps_target or 15)
                    capture.start()
                else:
                    capture = cv2.VideoCapture(device_index)
            except (ValueError, TypeError):
                if CAPTURE_ISOLATION:
                    capture = CaptureClient(
                        source=self.source, camera_id=self.camera_id or "camera",
                        target_fps=self.video_processor.settings.fps_target or 15)
                    capture.start()
                else:
                    capture = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
        except Exception as e:
            logger.warning("Reopen of %s raised %s", self._describe_self(), e)
            return False

        if capture is None or not capture.isOpened():
            if capture is not None:
                capture.release()
            return False

        # Prove it before trusting it.
        #
        # isOpened() is not evidence: a capture bound to a device that has gone
        # away opens happily and then never delivers. That is exactly what the
        # reconnect endpoint used to hand back with a 200 — and streaming from
        # that capture is what killed the process at 00:17 on 2026-08-20. A
        # capture is only accepted once it has produced a real frame.
        deadline = time.time() + self.REOPEN_PROVE_SECONDS
        proven = False
        while time.time() < deadline:
            try:
                ret, frame = capture.read()
            except Exception as e:
                logger.warning("Proving read for %s raised %s",
                               self._describe_self(), e)
                break
            if ret and frame is not None:
                proven = True
                break
            time.sleep(0.1)

        if not proven:
            logger.warning(
                "Camera %s: reopened capture delivered no frame within %.1fs — "
                "discarding it rather than reporting a working camera.",
                self._describe_self(), self.REOPEN_PROVE_SECONDS)
            try:
                capture.release()
            except Exception:
                pass
            return False

        with self._frame_lock:
            self.capture = capture
        # Only a proven capture revives the camera.
        self._capture_dead.clear()
        self._consecutive_failures = 0
        self._failure_since = None
        logger.info("Camera %s: reopened capture delivered a frame; camera is live",
                    self._describe_self())
        return True

    def _background_processor(self):
        """
        Background thread that continuously processes frames for motion/face detection.
        This ensures surveillance runs 24/7 regardless of stream viewers.
        """
        print(f"🎥 [BACKGROUND] Starting background processor for camera {self.camera_id}")
        # Claim the capture. From here on get_frame() refuses any other thread,
        # so the only path to VideoCapture.read() is this loop.
        self._capture_owner_thread = threading.get_ident()
        frame_interval = 1.0 / 10  # Process at ~10 FPS for efficiency

        while not self._stop_background.is_set():
            try:
                if not self.is_running or not self.capture or not self.capture.isOpened():
                    time.sleep(0.5)
                    continue

                # Process frame (motion detection, face recognition, recording)
                frame, motion_detected = self.get_frame()

                if frame is None:
                    # A dead capture is retried on its own schedule. This has to
                    # come first: once the capture is dead nothing counts
                    # failures any more, so every counter-driven branch below is
                    # unreachable.
                    if self._capture_dead.is_set():
                        self._maybe_reopen_dead_capture()
                        self._stop_background.wait(0.5)
                        continue

                    # Isolated capture is checked FIRST, ahead of the
                    # failure-count shortcut below.
                    #
                    # With isolation on, an empty read is not counted as a
                    # failure (the worker may simply have nothing new yet), so
                    # _consecutive_failures stays 0 — and the early `continue`
                    # below then meant a worker that had DIED was never noticed.
                    # The client tracks its own health, so ask it directly.
                    if CAPTURE_ISOLATION and isinstance(self.capture, CaptureClient):
                        if self.capture.restart_if_needed():
                            self._capture_dead.clear()
                            self._consecutive_failures = 0
                            self._failure_since = None
                            continue

                    # A None frame is not always a failure — the FPS limiter
                    # returns one too — so only react once reads are genuinely
                    # failing, which _note_frame_failure has counted.
                    fails = self._consecutive_failures
                    if fails == 0:
                        time.sleep(0.1)
                        continue

                    # With isolation on, a dead or wedged worker is replaced
                    # here. The client decides when that is warranted, judging
                    # liveness by whether frames are arriving rather than by
                    # whether the process exists.
                    if CAPTURE_ISOLATION and isinstance(self.capture, CaptureClient):
                        if self.capture.restart_if_needed():
                            self._capture_dead.clear()
                            self._consecutive_failures = 0
                            self._failure_since = None
                            continue

                    if fails % self.RECONNECT_AFTER_FAILURES == 0:
                        self._reconnect_attempts += 1
                        logger.info(
                            "Camera %s: attempting reconnect #%s after %s failed reads",
                            self._describe_self(), self._reconnect_attempts, fails)
                        if self._reopen_capture():
                            # Don't declare victory here — the next successful read
                            # does that, via _note_frame_success. A capture can open
                            # and still deliver nothing.
                            logger.info("Camera %s: capture reopened, awaiting frames",
                                        self._describe_self())
                            continue

                    # Back off as failures persist instead of hammering a dead
                    # device ten times a second. Doubling from the base interval up
                    # to a ceiling keeps a brief glitch responsive while an absent
                    # phone costs one read a minute rather than 36,000 an hour.
                    delay = min(0.1 * (2 ** min(self._reconnect_attempts, 10)),
                                self.RECONNECT_BACKOFF_MAX)
                    self._stop_background.wait(delay)
                    continue

                # Sleep to maintain target FPS
                time.sleep(frame_interval)

            except Exception as e:
                print(f"⚠️ [BACKGROUND] Error in background processor for {self.camera_id}: {e}")
                time.sleep(1)  # Wait before retrying

        print(f"🛑 [BACKGROUND] Background processor stopped for camera {self.camera_id}")

    def start(self):
        # Detect if source is a USB device index (integer or numeric string)
        # Open with a few retries — a USB device can be briefly busy right after a
        # restart (previous handle not fully released, or another app grabbed it).
        #
        # macOS: the FIRST open from OpenEye.app raises a camera-permission dialog,
        # and the open keeps failing until the user clicks Allow. Three quick tries
        # (~6s) expired long before a human could react, so the camera came up dead
        # on first launch. Give Darwin a longer — but still bounded — window, and log
        # every attempt so a slow open never looks like a hang. Once granted, the
        # permission persists and the open succeeds on the first attempt.
        _is_darwin = sys.platform == "darwin"
        max_attempts = int(os.getenv("OPENEYE_CAMERA_OPEN_ATTEMPTS", "0") or 0) or (
            8 if _is_darwin else 3
        )
        retry_delay = float(os.getenv("OPENEYE_CAMERA_OPEN_RETRY_DELAY", "2"))
        for attempt in range(1, max_attempts + 1):
            try:
                # Try to convert to int - if successful, it's a USB device
                device_index = int(self.source)
                print(f"Connecting to USB camera at index: {device_index} "
                      f"(attempt {attempt}/{max_attempts})")
                # Default backend. On macOS this resolves to AVFoundation and handles
                # capture-by-index correctly (forcing CAP_AVFOUNDATION explicitly warns
                # "can't be used to capture by index" and just falls back here anyway).
                if CAPTURE_ISOLATION:
                    # CaptureClient is VideoCapture-shaped, so everything below
                    # this point works unchanged — but read() now crosses a
                    # process boundary and cannot segfault this process.
                    self.capture = CaptureClient(
                        source=self.source, camera_id=self.camera_id or "camera",
                        target_fps=self.video_processor.settings.fps_target or 15)
                    self.capture.start()
                else:
                    self.capture = cv2.VideoCapture(device_index)
            except (ValueError, TypeError):
                # Not a number, assume it's an RTSP URL or device path
                print(f"Connecting to RTSP stream: {self.source}")
                if CAPTURE_ISOLATION:
                    self.capture = CaptureClient(
                        source=self.source, camera_id=self.camera_id or "camera",
                        target_fps=self.video_processor.settings.fps_target or 15)
                    self.capture.start()
                else:
                    self.capture = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)

            if self.capture is not None and self.capture.isOpened():
                break
            print(f"Camera open attempt {attempt}/{max_attempts} failed for {self.source}")
            if self.capture is not None:
                self.capture.release()
            if attempt < max_attempts:
                if _is_darwin and attempt == 1:
                    print("  (macOS: if a camera-permission dialog is showing, click "
                          "Allow — retrying while you respond)")
                time.sleep(retry_delay)

        if self.capture is None or not self.capture.isOpened():
            print(f"Error: Could not open camera source: {self.source} after {max_attempts} attempts")
            if _is_darwin:
                print("  macOS camera access is required for local cameras. Launch "
                      "OpenEye.app (or run ./start.sh from a Terminal) and approve the "
                      "prompt, or enable OpenEye under System Settings > Privacy & "
                      "Security > Camera, then restart OpenEye.")
            self.is_running = False
            return
        self.is_running = True

        # Ask the device to capture at the configured fps so the hardware target
        # actually matches the setting (previously fps_target only labelled the
        # output file and was never sent to the device). Best-effort: many USB
        # webcams ignore or clamp this, so recordings are still encoded at the
        # MEASURED rate. See todos_changelog.md (2026-07-25 — camera fps accuracy).
        try:
            target_fps = self.video_processor.settings.fps_target or 15
            self.capture.set(cv2.CAP_PROP_FPS, float(target_fps))
            actual = self.capture.get(cv2.CAP_PROP_FPS)
            print(f"Requested camera fps={target_fps}, device reports fps={actual}")
        except Exception as e:
            print(f"Could not set CAP_PROP_FPS: {e}")
        print("Camera started successfully.")

        # Load polygon-based motion zones from database (v3.6.2+)
        if self.camera_id:
            try:
                db = SessionLocal()
                self.motion_detector.load_polygon_zones(self.camera_id, db)
            except Exception as e:
                print(f"Warning: Could not load motion zones: {e}")
            finally:
                if db:
                    db.close()

        # Start background processing thread for 24/7 surveillance
        if self._background_processing_enabled:
            self._stop_background.clear()
            self._background_thread = threading.Thread(
                target=self._background_processor,
                daemon=True,
                name=f"bg_processor_{self.camera_id}"
            )
            self._background_thread.start()
            print(f"✅ [BACKGROUND] Background processing enabled for camera {self.camera_id}")
        else:
            print(f"⚠️ [BACKGROUND] Background processing disabled for camera {self.camera_id}")

    def stop(self):
        # Stop background processing thread first
        if self._background_thread and self._background_thread.is_alive():
            print(f"🛑 [BACKGROUND] Stopping background processor for {self.camera_id}...")
            self._stop_background.set()
            self._background_thread.join(timeout=5.0)
            if self._background_thread.is_alive():
                print(f"⚠️ [BACKGROUND] Background thread did not stop cleanly for {self.camera_id}")
            else:
                print(f"✅ [BACKGROUND] Background processor stopped for {self.camera_id}")

        if self.recorder.is_recording:
            self.recorder.stop()
        if self.is_running and self.capture:
            self.capture.release()
        self.is_running = False
        print("RTSP camera stopped.")

    def get_frame(self):
        # A dead capture is never read from again. Checked before everything
        # else, including isOpened(), which cannot be trusted: it returned True
        # throughout both segfaults while the underlying device was gone.
        if self._capture_dead.is_set():
            return None, False

        # Only the capture-owning thread may reach read(). Both crashes arrived
        # here from com.apple.main-thread — an HTTP handler serving the MJPEG
        # stream. Request handlers must use get_published_frame() instead.
        owner = self._capture_owner_thread
        if owner is not None and threading.get_ident() != owner:
            logger.error(
                "Camera %s: get_frame() called from thread %s, but the capture is "
                "owned by thread %s. Refusing. Request handlers must call "
                "get_published_frame(); reading the capture off-thread is what "
                "segfaulted the process on 2026-08-19 and 2026-08-20.",
                self.camera_id, threading.get_ident(), owner)
            return None, False

        if not self.is_running or self.capture is None or not self.capture.isOpened():
            return None, False

        # Check if we should process this frame based on FPS target
        if not self.video_processor.should_process_frame():
            return None, False

        # Thread-safe frame capture and processing
        with self._frame_lock:
            capture = self.capture
            if capture is None:
                return None, False
            ret, frame = capture.read()
        if not ret:
            # With an isolated capture, "no new frame right now" is not a
            # failure. The worker takes a moment to open the device after spawn,
            # and between frames there is simply nothing new to read — counting
            # those as failed reads marked the capture dead one second after
            # startup. The client is the authority on its own health, and it
            # judges by whether frames are arriving.
            if isinstance(capture, CaptureClient):
                if not capture.needs_restart():
                    return None, False
            self._note_frame_failure()
            return None, False

        self._note_frame_success()

        # Sample the real frame cadence (drives measured_fps for accurate encoding).
        self._record_frame_tick()

        # Store clean frame for recording
        clean_frame = frame.copy()

        # Apply video processing (resolution adjustment if needed)
        processed_frame = self.video_processor.process_frame(frame)

        # Apply image quality adjustments
        if self.image_processor.has_adjustments():
            processed_frame = self.image_processor.process(processed_frame)

        # Motion detection on processed frame
        # draw_boxes=False to only show face detection boxes, not motion boxes
        processed_frame, self.motion_detected, motion_areas, triggered_zone_ids = (
            self.motion_detector.detect(processed_frame, draw_boxes=False)
        )

        # Check motion percentage threshold before triggering event
        # If motion_areas is empty but motion_detected is True, reset motion_detected
        # This handles edge cases like lighting compensation where motion is suppressed
        if self.motion_detected and not motion_areas:
            self.motion_detected = False
            triggered_zone_ids = []
        elif self.motion_detected and motion_areas:
            # Calculate motion percentage
            frame_area = processed_frame.shape[0] * processed_frame.shape[1]
            total_motion_area = sum(area.get("area", 0) for area in motion_areas)
            motion_percentage = (total_motion_area / frame_area * 100) if frame_area > 0 else 0

            # Only trigger if motion percentage exceeds threshold
            if motion_percentage < self.motion_percentage_threshold:
                # Motion detected but below threshold - ignore it
                self.motion_detected = False
                motion_areas = []
                triggered_zone_ids = []

        # Trigger motion alert if motion detected (and has motion areas)
        if self.motion_detected and motion_areas:
            # Save snapshot and create database record
            snapshot_path = self._save_motion_snapshot(
                processed_frame, motion_areas)
            self.current_motion_event_id = self._create_motion_event(
                processed_frame, motion_areas, snapshot_path, triggered_zone_ids
            )

            try:
                alert_manager = get_alert_manager()
                camera_id = self.camera_id or "rtsp_cam"
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            alert_manager.trigger_motion_alert(
                                camera_id=camera_id,
                                event_data={
                                    "timestamp": time.time(),
                                    "motion_areas": motion_areas,
                                    "motion_event_id": self.current_motion_event_id,
                                    "snapshot_path": snapshot_path,
                                },
                            ),
                            loop,
                        )
                except RuntimeError:
                    # No event loop running, skip alert
                    pass
            except Exception as e:
                print(f"Error triggering motion alert: {e}")
        else:
            # Clear motion event when no motion detected
            self.current_motion_event_id = None

        # Face detection
        if self.face_detector.enabled:
            processed_frame, self.last_faces_detected = (
                self.face_detector.process_frame(
                    processed_frame, self.motion_detected))

            # Act on every face, record the ones worth keeping.
            self._handle_detected_faces(processed_frame, self.last_faces_detected)

            # Update motion event with face count if faces detected
            if self.last_faces_detected and self.current_motion_event_id:
                self._update_motion_event_faces(
                    self.current_motion_event_id, len(
                        self.last_faces_detected)
                )

            # Log faces to recorder if recording
            if self.recorder.is_recording and self.last_faces_detected:
                for face in self.last_faces_detected:
                    self.recorder.add_face_detection(face)

        # Recording logic
        manual_record = time.time() < self.manual_record_until
        if self.motion_detected or manual_record:
            if self.motion_detected:
                self.last_motion_time = time.time()
            if not self.recorder.is_recording:
                height, width, _ = clean_frame.shape
                # Encode at the MEASURED capture rate so playback matches real time
                # (nominal fps_target overshot the achieved rate → sped-up playback).
                self._recording_fps = self._resolve_recording_fps()
                self.recorder.start(width, height, fps=self._recording_fps, camera_id=self.camera_id or "rtsp")
                self.last_recording_frame_time = 0  # Reset frame time for new recording

            # Link motion event to the recording (if recording is active)
            if self.recorder.is_recording and self.current_motion_event_id:
                self.recorder.add_motion_event_id(self.current_motion_event_id)

        if self.recorder.is_recording:
            height, width, _ = clean_frame.shape
            # Add recording indicator to the processed frame for streaming
            cv2.circle(processed_frame, (width - 30, 30), 10, (0, 0, 255), -1)

            # Frame rate limiting for recording - prevents fast playback. Use the
            # same measured rate the writer was created with so writes and the
            # encoded fps stay consistent.
            recording_fps = self._recording_fps or self._resolve_recording_fps()
            frame_interval = 1.0 / recording_fps
            current_time = time.time()

            if current_time - self.last_recording_frame_time >= frame_interval:
                # Write original clean frame to file
                self.recorder.write(clean_frame)
                self.last_recording_frame_time = current_time

            if not manual_record and (
                not self.motion_detected and (
                    time.time() - self.last_motion_time > self.post_motion_cooldown
                )
            ):
                self.recorder.stop()

        # Apply timestamp/custom text overlay (for streaming only, not recording)
        processed_frame = render_overlay(
            processed_frame,
            overlay_enabled=self.overlay_enabled,
            timestamp_enabled=self.overlay_timestamp_enabled,
            custom_text=self.overlay_custom_text,
            position=self.overlay_position,
            font_size=self.overlay_font_size,
            font_color=self.overlay_font_color
        )

        # Publish so HTTP handlers can serve this frame without ever reaching
        # the capture. This is the mechanism that makes the stream and snapshot
        # endpoints incapable of segfaulting the process.
        self._publish_frame(processed_frame, self.motion_detected)

        return processed_frame, self.motion_detected


class CameraManager:
    """
    Enhanced Camera Manager with database integration.

    New in v3.5.0:
    - Loads camera settings from database
    - Passes settings to processor instances
    - Supports dynamic settings reload
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CameraManager, cls).__new__(cls)
            cls._instance.cameras = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def _load_camera_settings(
            self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Load camera settings from database and merge with system settings"""
        try:
            # FIXED: Use context manager to prevent session leak (v3.6.0.1)
            with get_db_context() as db:
                # Load system settings
                from backend.database.crud import get_all_system_settings

                settings_list = get_all_system_settings(db)

                # Convert list to dictionary
                system_settings = {}
                for setting in settings_list:
                    try:
                        if setting.setting_type == "int":
                            system_settings[setting.setting_key] = int(
                                setting.setting_value
                            )
                        elif setting.setting_type == "float":
                            system_settings[setting.setting_key] = float(
                                setting.setting_value
                            )
                        elif setting.setting_type == "boolean":
                            system_settings[setting.setting_key] = (
                                setting.setting_value.lower() == "true"
                            )
                        else:
                            system_settings[setting.setting_key] = setting.setting_value
                    except (ValueError, AttributeError):
                        system_settings[setting.setting_key] = setting.setting_value

                # Load camera-specific settings
                db_camera = (
                    db.query(CameraModel).filter(
                        CameraModel.camera_id == camera_id).first())

                if db_camera:
                    settings = {
                        # Motion detection settings
                        "min_contour_area": db_camera.min_contour_area,
                        "motion_sensitivity": db_camera.motion_sensitivity,
                        "motion_threshold": db_camera.motion_threshold,
                        "motion_percentage_threshold": db_camera.motion_percentage_threshold,
                        "noise_reduction": db_camera.noise_reduction,
                        "detect_shadows": db_camera.detect_shadows,
                        "detection_zones": db_camera.detection_zones,
                        # Image quality settings
                        "brightness": db_camera.brightness,
                        "contrast": db_camera.contrast,
                        "saturation": db_camera.saturation,
                        "sharpness": db_camera.sharpness,
                        "noise_reduction_strength": db_camera.noise_reduction_strength,
                        # Video quality settings
                        "resolution": db_camera.resolution,
                        "fps_target": db_camera.fps_target,
                        "bitrate_kbps": db_camera.bitrate_kbps,
                        "codec": db_camera.codec,
                        # Recording settings
                        "post_motion_cooldown": db_camera.post_motion_cooldown,
                        # Capture policy. getattr with a default so a database
                        # that predates these columns still starts — the inline
                        # schema check adds them, but settings are read on paths
                        # that can run before it.
                        "face_capture_mode": getattr(
                            db_camera, "face_capture_mode", None) or "system_default",
                        "recognition_requires_motion": bool(getattr(
                            db_camera, "recognition_requires_motion", True)),
                        "recognition_motion_window_seconds": int(getattr(
                            db_camera, "recognition_motion_window_seconds", None) or 30),
                        # System-wide capture tunables.
                        "capture_required_passes": int(
                            system_settings.get("capture_required_passes", 3)),
                        "capture_cluster_maturity": int(
                            system_settings.get("capture_cluster_maturity", 25)),
                        # System settings (paths, max duration, display mode)
                        "recordings_path": system_settings.get(
                            "recordings_path", "recordings"
                        ),
                        "faces_path": system_settings.get("faces_path", "faces"),
                        "snapshots_path": system_settings.get("snapshots_path", "data/snapshots"),
                        "max_recording_duration": int(
                            system_settings.get("max_recording_duration", 300)
                        ),
                        "display_mode": system_settings.get("display_mode", "grid"),
                        "cycle_interval": int(system_settings.get("cycle_interval", 10)),
                        # Hardware encoding (v3.7.1+)
                        "hardware_video_encoding": system_settings.get("hardware_video_encoding", False),
                    }

                    return settings

                return None

        except Exception as e:
            print(f"Error loading camera settings from database: {e}")
            return None

    def add_camera(
        self,
        camera_id: str,
        camera_type: str,
        source: str,
        enable_face_detection: bool = True,
    ) -> "tuple[bool, str]":
        """
        Add a camera with settings loaded from database.

        Returns:
            tuple[bool, str]: (success, message) - success indicates if camera started,
                              message contains error details if failed
        """
        with self._lock:
            if camera_id in self.cameras:
                msg = f"Camera with ID '{camera_id}' already exists."
                print(msg)
                return False, msg

            # Load settings from database
            db_settings = self._load_camera_settings(camera_id)
            if db_settings:
                print(
                    f"Loaded settings for camera '{camera_id}' from database")
            else:
                print(f"Using default settings for camera '{camera_id}'")

            # Create camera with appropriate type
            if camera_type == "rtsp":
                camera = RTSPCamera(
                    source, camera_id, enable_face_detection, db_settings
                )
            elif camera_type == "usb":
                # USB cameras use RTSP camera class with device index or path
                camera = RTSPCamera(
                    source, camera_id, enable_face_detection, db_settings
                )
            elif camera_type == "mock":
                camera = MockCamera(
                    source, camera_id, enable_face_detection, db_settings
                )
            else:
                msg = f"Unknown camera type: {camera_type}"
                print(msg)
                return False, msg

            # Start camera
            camera.start()
            if camera.is_running:
                camera.recorder.camera_id = camera_id
                self.cameras[camera_id] = camera
                msg = f"Camera '{camera_id}' added and started (face detection: {enable_face_detection})."
                print(msg)
                return True, msg
            else:
                # Determine failure reason based on camera type
                if camera_type == "usb":
                    msg = f"USB camera '{camera_id}' (device {source}) unavailable - device may be disconnected"
                elif camera_type == "rtsp":
                    msg = f"RTSP camera '{camera_id}' ({source}) unavailable - stream unreachable"
                else:
                    msg = f"Camera '{camera_id}' failed to start - source unavailable"
                print(msg)
                return False, msg

    def get_camera(self, camera_id: str):
        """Get camera instance by ID"""
        with self._lock:
            return self.cameras.get(camera_id)

    def remove_camera(self, camera_id: str):
        """Remove and stop a camera"""
        with self._lock:
            if camera_id in self.cameras:
                self.cameras[camera_id].stop()
                del self.cameras[camera_id]
                print(f"Camera '{camera_id}' removed.")

    def reload_camera_settings(self, camera_id: str):
        """Reload settings from database for a specific camera"""
        with self._lock:
            camera = self.cameras.get(camera_id)
            if camera:
                camera.reload_settings_from_db()
            else:
                print(f"Camera '{camera_id}' not found.")

    def reload_motion_zones(self, camera_id: str) -> bool:
        """
        Re-read a running camera's motion zones from the database.

        Zones were previously loaded exactly once, when the camera started. The
        CRUD routes committed changes and called db.refresh(), which refreshes
        the SQLAlchemy object — not the detector — so a user could draw, edit or
        delete a zone, see the UI confirm the save, and have the running camera
        keep enforcing the old geometry until the whole service restarted. On a
        surveillance system that means an exclusion zone someone just drew over
        a busy road quietly does nothing.

        Returns True if a running camera picked the zones up.
        """
        with self._lock:
            camera = self.cameras.get(camera_id)

        if not camera:
            # Not an error: zones can be edited for a camera that is disabled or
            # currently disconnected. It will load them when it next starts.
            logger.debug(
                "Zone reload requested for '%s', which is not running", camera_id)
            return False

        detector = getattr(camera, "motion_detector", None)
        if detector is None or not hasattr(detector, "load_polygon_zones"):
            logger.debug("Camera '%s' has no motion detector to reload", camera_id)
            return False

        db = None
        try:
            db = SessionLocal()
            detector.load_polygon_zones(camera_id, db)
            logger.info("Reloaded motion zones for running camera '%s'", camera_id)
            return True
        except Exception as e:
            logger.warning("Could not reload motion zones for '%s': %s", camera_id, e)
            return False
        finally:
            if db is not None:
                db.close()

    def get_camera_settings(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Get current settings for a camera"""
        with self._lock:
            camera = self.cameras.get(camera_id)
            if camera:
                return camera.get_all_settings()
            return None

    def get_all_face_detections(self):
        """Get face detections from all cameras"""
        with self._lock:
            all_detections = {}
            for camera_id, camera in self.cameras.items():
                all_detections[camera_id] = {
                    "recent_faces": camera.last_faces_detected,
                    "statistics": camera.get_face_statistics(),
                }
            return all_detections


manager = CameraManager()
