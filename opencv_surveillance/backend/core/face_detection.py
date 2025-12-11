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
        detection_cooldown: float = 2.0
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

        if self.last_detection_time is None:
            return True

        time_since_last = (
            datetime.now() -
            self.last_detection_time).total_seconds()
        return time_since_last >= self.detection_cooldown

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
                    self.detections_buffer.append(face)

                    # NEW: Trigger face recognition alert
                    try:
                        alert_manager = get_alert_manager()
                        camera_id = getattr(self, "camera_id", "unknown")
                        is_known = face["name"] != "Unknown"

                        asyncio.create_task(
                            alert_manager.trigger_face_recognition_alert(
                                camera_id=camera_id,
                                person_name=face["name"],
                                confidence=face["confidence"],
                                is_known=is_known,
                                event_data=face,
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error triggering face alert: {e}")

                # Trim buffer to max size
                if len(self.detections_buffer) > self.max_buffer_size:
                    self.detections_buffer = self.detections_buffer[
                        -self.max_buffer_size:
                    ]

                logger.info(
                    f"Detected {len(detected_faces)} face(s): "
                    f"{[f['name'] for f in detected_faces]}"
                )

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
