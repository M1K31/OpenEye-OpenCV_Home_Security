# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Face Detector - Integrates face recognition with camera streams
Designed to work alongside motion detection in the OpenEye surveillance system
"""

from typing import Tuple, List, Dict, Optional
import numpy as np
import logging
from datetime import datetime
from pathlib import Path
from backend.core.face_recognition import get_face_manager
from backend.core.paths import paths
import asyncio
from backend.core.alert_manager import get_alert_manager


logger = logging.getLogger(__name__)


class FaceDetector:
    """
    Integrates face recognition with camera streams
    Works alongside motion detection to identify people in video

    Configurable Settings (from database Camera model):
    - scale_mode: "auto", "none", or float like "0.5"
    - upsample_times: 0, 1, or 2 (higher = slower but finds smaller faces)
    - min_face_size: Minimum face size in pixels to detect
    """

    def __init__(
        self,
        enabled: bool = True,
        faces_dir: Optional[Path] = None,
        scale_mode: str = "auto",
        upsample_times: int = 1,
        min_face_size: int = 20,
        detection_cooldown: float = 2.0,
        requires_motion: bool = True,
        motion_sticky_seconds: float = 30.0
    ):
        """
        Initialize face detector

        Args:
            enabled: Whether face detection is enabled
            faces_dir: Directory where face images are stored (uses PathManager if None)
            scale_mode: Scaling strategy for face detection
                - "auto": Adaptive scaling based on resolution (default, recommended)
                - "none": No scaling, use native resolution (slower but more accurate)
                - "0.5": Manual scale factor (0.1 to 1.0)
            upsample_times: Number of times to upsample image (0-2)
                - 0: Fastest, may miss small faces
                - 1: Default, good balance
                - 2: Slowest, finds smaller faces
            min_face_size: Minimum face size in pixels to detect (default: 20)
            detection_cooldown: Seconds between detections (default: 2.0)
        """
        self.enabled = enabled
        self.faces_dir = faces_dir or paths.faces_dir

        # Configurable detection settings
        self.scale_mode = scale_mode
        self.upsample_times = max(0, min(2, upsample_times))  # Clamp to 0-2
        self.min_face_size = max(10, min_face_size)  # Minimum 10px
        self.detection_cooldown = max(0.1, detection_cooldown)  # Minimum 0.1s

        # Use get_face_manager() without args to use consistent PathManager default
        self.face_manager = get_face_manager()
        self.last_detection_time = None
        self.detections_buffer = []  # Store recent detections
        self.max_buffer_size = 10

        # Recognition is by far the most expensive thing this process does, and
        # it was running on a timer alone — an empty room was fully detected,
        # encoded and matched every couple of seconds, around the clock. Motion
        # detection costs a fraction of that, so it decides when recognition is
        # worth doing at all.
        #
        # The window is sticky rather than instantaneous on purpose: someone
        # standing still at a door stops generating motion while very much still
        # being someone the access rules need to identify.
        self.requires_motion = requires_motion
        self.motion_sticky_seconds = max(0.0, motion_sticky_seconds)
        self._last_motion_time = None
        self._skipped_since_motion = 0

        logger.info(
            f"FaceDetector initialized (enabled={enabled}, scale={scale_mode}, "
            f"upsample={upsample_times}, min_size={min_face_size}px, cooldown={detection_cooldown}s)"
        )

    def set_enabled(self, enabled: bool):
        """Enable or disable face detection"""
        self.enabled = enabled
        logger.info(f"Face detection {'enabled' if enabled else 'disabled'}")

    def should_process_frame(self) -> bool:
        """
        Check if enough time has passed since last detection
        This reduces CPU load by not processing every frame

        Returns:
            True if frame should be processed
        """
        if not self.enabled:
            logger.debug("Face detection disabled")
            return False

        if not self.face_manager.is_available():
            logger.debug("Face recognition library not available")
            return False

        if not self._within_motion_window():
            return False

        if self.last_detection_time is None:
            return True

        time_since_last = (
            datetime.now() -
            self.last_detection_time).total_seconds()
        return time_since_last >= self.detection_cooldown

    def note_motion(self, motion_detected: bool):
        """
        Record that something moved, whether or not recognition runs.

        Called on every frame, before the decision to recognise. Motion has to
        be tracked continuously — if it were only recorded on frames that
        already passed the cooldown, the window would be sampled at the very
        rate it is supposed to gate.
        """
        if motion_detected:
            self._last_motion_time = datetime.now()
            if self._skipped_since_motion:
                logger.debug("Resuming recognition after %s skipped frame(s)",
                             self._skipped_since_motion)
                self._skipped_since_motion = 0

    def _within_motion_window(self) -> bool:
        """Whether anything has moved recently enough to be worth looking at."""
        if not self.requires_motion:
            return True

        if self._last_motion_time is None:
            self._skipped_since_motion += 1
            return False

        idle = (datetime.now() - self._last_motion_time).total_seconds()
        if idle <= self.motion_sticky_seconds:
            return True

        self._skipped_since_motion += 1
        # Logged so a camera that never recognises anything is diagnosable —
        # a motion configuration that excludes everything would otherwise
        # silently disable face recognition on that camera.
        if self._skipped_since_motion % 500 == 1:
            logger.debug(
                "Skipping recognition: no motion for %.0fs (%s frames skipped). "
                "Disable recognition_requires_motion for this camera to run it "
                "continuously.", idle, self._skipped_since_motion,
            )
        return False

    def process_frame(
        self, frame: np.ndarray, motion_detected: bool = False
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        Process a frame for face detection and recognition

        Args:
            frame: OpenCV frame (BGR format)
            motion_detected: Whether motion was detected in this frame

        Returns:
            Tuple of (annotated_frame, list of detected faces)
        """
        self.note_motion(motion_detected)

        if not self.should_process_frame():
            return frame, []

        try:
            # Perform face recognition with configurable settings
            annotated_frame, detected_faces = (
                self.face_manager.recognize_faces_in_frame(
                    frame,
                    scale_mode=self.scale_mode,
                    upsample_times=self.upsample_times,
                    min_face_size=self.min_face_size
                )
            )

            # Update last detection time
            self.last_detection_time = datetime.now()

            # Add detections to buffer
            if detected_faces:
                for face in detected_faces:
                    face["motion_detected"] = motion_detected
                    face["event_type"] = "face_detected"
                    self.detections_buffer.append(face)

                    # Trigger face recognition alert
                    try:
                        alert_manager = get_alert_manager()
                        camera_id = getattr(self, "camera_id", "unknown")
                        is_known = face["name"] != "Unknown"

                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    alert_manager.trigger_face_recognition_alert(
                                        camera_id=camera_id,
                                        person_name=face["name"],
                                        confidence=face["confidence"],
                                        is_known=is_known,
                                        event_data=face,
                                    ),
                                    loop,
                                )
                        except RuntimeError:
                            pass
                    except Exception as e:
                        logger.error(f"Error triggering face alert: {e}")

                logger.info(
                    f"Detected {len(detected_faces)} face(s): "
                    f"{[f['name'] for f in detected_faces]}"
                )

            elif motion_detected:
                # Record motion-without-face event so the history API can
                # differentiate "motion + face" from "motion only".
                motion_event = {
                    "name": None,
                    "confidence": 0.0,
                    "location": None,
                    "timestamp": datetime.now().isoformat(),
                    "motion_detected": True,
                    "event_type": "motion_only",
                }
                self.detections_buffer.append(motion_event)

                try:
                    alert_manager = get_alert_manager()
                    camera_id = getattr(self, "camera_id", "unknown")
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                alert_manager.trigger_motion_without_face_alert(
                                    camera_id=camera_id,
                                    event_data=motion_event,
                                ),
                                loop,
                            )
                    except RuntimeError:
                        pass
                except Exception as e:
                    logger.error(f"Error triggering motion-only alert: {e}")

            # Trim buffer to max size
            if len(self.detections_buffer) > self.max_buffer_size:
                self.detections_buffer = self.detections_buffer[
                    -self.max_buffer_size:
                ]

            return annotated_frame, detected_faces

        except Exception as e:
            logger.error(f"Error processing frame for face detection: {e}")
            return frame, []

    def get_recent_detections(self, count: int = 10) -> List[Dict]:
        """
        Get recent face detections

        Args:
            count: Number of recent detections to return

        Returns:
            List of recent detections
        """
        return self.detections_buffer[-count:]

    def clear_detections(self):
        """Clear the detections buffer"""
        self.detections_buffer = []
        logger.info("Detections buffer cleared")

    def get_statistics(self) -> Dict:
        """
        Get face detection statistics

        Returns:
            Dictionary with statistics
        """
        unique_people = set(
            d["name"] for d in self.detections_buffer if d["name"] != "Unknown"
        )

        return {
            "enabled": self.enabled,
            "total_detections": len(self.detections_buffer),
            "unique_people_detected": len(unique_people),
            "unknown_detections": len([d for d in self.detections_buffer if d["name"] == "Unknown"]),
            "last_detection_time": (
                self.last_detection_time.isoformat()
                if self.last_detection_time
                else None
            ),
            "face_manager_ready": self.face_manager.is_available(),
            "known_faces_trained": len(self.face_manager.known_face_encodings),
        }
