# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Face Detector - Integrates face recognition with camera streams
Designed to work alongside motion detection in the OpenEye surveillance system
"""

import cv2
import numpy as np
import logging
from typing import Tuple, List, Dict, Optional
from datetime import datetime
from backend.core.face_recognition import get_face_manager
import asyncio
from backend.core.alert_manager import get_alert_manager



logger = logging.getLogger(__name__)


class FaceDetector:
    """
    Integrates face recognition with camera streams
    Works alongside motion detection to identify people in video
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize face detector

        Args:
            enabled: Whether face detection is enabled
        """
        self.enabled = enabled
        self.face_manager = get_face_manager()
        self.last_detection_time = None
        self.detection_cooldown = 2.0  # Seconds between detections to reduce CPU load
        self.detections_buffer = []  # Store recent detections
        self.max_buffer_size = 10

        logger.info(f"FaceDetector initialized (enabled={enabled})")

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
            return False

        if not self.face_manager.is_available():
            return False

        if self.last_detection_time is None:
            return True

        time_since_last = (datetime.now() - self.last_detection_time).total_seconds()
        return time_since_last >= self.detection_cooldown

    def process_frame(self, frame: np.ndarray, motion_detected: bool = False) -> Tuple[np.ndarray, List[Dict]]:
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
            # Perform face recognition
            annotated_frame, detected_faces = self.face_manager.recognize_faces_in_frame(frame)

            # Update last detection time
            self.last_detection_time = datetime.now()

            # Add detections to buffer
            if detected_faces:
                for face in detected_faces:
                    face['motion_detected'] = motion_detected
                    self.detections_buffer.append(face)
                    
                    # NEW: Trigger face recognition alert
                    try:
                        alert_manager = get_alert_manager()
                        camera_id = getattr(self, 'camera_id', 'unknown')
                        is_known = face['name'] != 'Unknown'
                        
                        asyncio.create_task(alert_manager.trigger_face_recognition_alert(
                            camera_id=camera_id,
                            person_name=face['name'],
                            confidence=face['confidence'],
                            is_known=is_known,
                            event_data=face
                        ))
                    except Exception as e:
                        logger.error(f"Error triggering face alert: {e}")

                # Trim buffer to max size
                if len(self.detections_buffer) > self.max_buffer_size:
                    self.detections_buffer = self.detections_buffer[-self.max_buffer_size:]

                logger.info(f"Detected {len(detected_faces)} face(s): "
                          f"{[f['name'] for f in detected_faces]}")

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
        unique_people = set(d['name'] for d in self.detections_buffer if d['name'] != 'Unknown')

        return {
            'enabled': self.enabled,
            'total_detections': len(self.detections_buffer),
            'unique_people_detected': len(unique_people),
            'last_detection_time': self.last_detection_time.isoformat() if self.last_detection_time else None,
            'face_manager_ready': self.face_manager.is_available()
        }