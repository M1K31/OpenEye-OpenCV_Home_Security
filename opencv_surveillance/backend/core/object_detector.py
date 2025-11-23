"""
v3.10.0: Object Detector - Integrates YOLO object detection with camera streams
Works alongside motion and face detection in the OpenEye surveillance system
"""

from typing import Tuple, List, Dict, Optional
import numpy as np
import logging
from datetime import datetime
from pathlib import Path
from backend.core.object_detection import get_object_detection_manager, ObjectDetection
from backend.core.paths import paths
from backend.database.session import SessionLocal
from backend.database import crud
from backend.core.alert_manager import get_alert_manager
import cv2
import asyncio

logger = logging.getLogger(__name__)


class ObjectDetector:
    """
    Integrates YOLO object detection with camera streams
    Detects vehicles, animals, and packages in video frames
    """

    def __init__(
        self,
        enabled: bool = False,  # Default OFF - user must opt-in
        model_size: str = "yolov8n",  # Nano model for speed
        confidence_threshold: float = 0.5,
        device: str = "cpu",
        classes_filter: Optional[List[str]] = None
    ):
        """
        Initialize object detector

        Args:
            enabled: Whether object detection is enabled
            model_size: YOLO model variant (yolov8n, yolov8s, yolov8m, yolov8l, yolov8x)
            confidence_threshold: Minimum confidence for detections (0.0-1.0)
            device: Device to run inference on ('cpu' or 'cuda')
            classes_filter: Filter to specific classes (e.g., ['vehicle', 'animal'])
        """
        self.enabled = enabled
        self.model_size = model_size
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.classes_filter = classes_filter or ['vehicle', 'animal', 'package']  # Default: exclude person

        # Initialize YOLO manager (lazy loading)
        self.object_manager = None
        if self.enabled:
            try:
                self.object_manager = get_object_detection_manager(
                    model_size=model_size,
                    confidence_threshold=confidence_threshold,
                    device=device
                )
                if not self.object_manager.initialized:
                    logger.error("YOLO object detection failed to initialize")
                    self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize object detector: {e}")
                self.enabled = False

        self.last_detection_time = None
        self.detection_cooldown = 3.0  # Seconds between detections (YOLO is heavier than face detection)
        self.detections_buffer = []  # Store recent detections
        self.max_buffer_size = 20

        logger.info(
            f"ObjectDetector initialized (enabled={enabled}, model={model_size}, "
            f"device={device}, classes={self.classes_filter})"
        )

    def set_enabled(self, enabled: bool):
        """Enable or disable object detection"""
        self.enabled = enabled

        # Initialize manager if enabling and not already initialized
        if enabled and self.object_manager is None:
            try:
                self.object_manager = get_object_detection_manager(
                    model_size=self.model_size,
                    confidence_threshold=self.confidence_threshold,
                    device=self.device
                )
                if not self.object_manager.initialized:
                    logger.error("YOLO object detection failed to initialize")
                    self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize object detector: {e}")
                self.enabled = False

        logger.info(f"Object detection {'enabled' if self.enabled else 'disabled'}")

    def should_process_frame(self) -> bool:
        """
        Check if enough time has passed since last detection
        YOLO is computationally expensive, so we process less frequently

        Returns:
            True if frame should be processed
        """
        if not self.enabled:
            return False

        if self.object_manager is None or not self.object_manager.initialized:
            return False

        if self.last_detection_time is None:
            return True

        time_since_last = (
            datetime.now() - self.last_detection_time
        ).total_seconds()
        return time_since_last >= self.detection_cooldown

    def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        motion_detected: bool = False,
        recording_id: Optional[int] = None
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        Process a frame for object detection

        Args:
            frame: OpenCV frame (BGR format)
            camera_id: ID of the camera
            motion_detected: Whether motion was detected in this frame
            recording_id: Optional recording ID to link detections

        Returns:
            Tuple of (annotated_frame, list of detected objects)
        """
        if not self.should_process_frame():
            return frame, []

        try:
            # Perform YOLO object detection
            detections: List[ObjectDetection] = self.object_manager.detect_objects(
                frame=frame,
                classes_filter=self.classes_filter
            )

            # Update last detection time
            self.last_detection_time = datetime.now()

            # Convert detections to dict format for storage
            detection_dicts = []
            if detections:
                # Draw detections on frame
                annotated_frame = self.object_manager.draw_detections(
                    frame=frame,
                    detections=detections,
                    show_confidence=True
                )

                # Save detections to database
                for detection in detections:
                    detection_dict = self._save_detection(
                        detection=detection,
                        camera_id=camera_id,
                        frame_shape=frame.shape,
                        motion_detected=motion_detected,
                        recording_id=recording_id
                    )
                    if detection_dict:
                        detection_dicts.append(detection_dict)

                # Add to buffer
                self.detections_buffer.extend(detection_dicts)
                if len(self.detections_buffer) > self.max_buffer_size:
                    self.detections_buffer = self.detections_buffer[-self.max_buffer_size:]

                logger.info(
                    f"Detected {len(detections)} objects in {camera_id}: "
                    f"{self.object_manager.get_detection_summary(detections)}"
                )

                return annotated_frame, detection_dicts
            else:
                return frame, []

        except Exception as e:
            logger.error(f"Object detection error: {e}")
            return frame, []

    def _save_detection(
        self,
        detection: ObjectDetection,
        camera_id: str,
        frame_shape: tuple,
        motion_detected: bool = False,
        recording_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Save object detection to database

        Args:
            detection: ObjectDetection instance
            camera_id: Camera ID
            frame_shape: Shape of the frame (height, width, channels)
            motion_detected: Whether motion was detected
            recording_id: Optional recording ID

        Returns:
            Dictionary with detection data or None on error
        """
        try:
            db = SessionLocal()

            # Prepare detection data
            x, y, width, height = detection.bbox
            frame_height, frame_width = frame_shape[:2]

            event_data = {
                'camera_id': camera_id,
                'object_class': detection.class_name,
                'object_subclass': detection.subclass,
                'confidence': detection.confidence,
                'bbox_x': x,
                'bbox_y': y,
                'bbox_width': width,
                'bbox_height': height,
                'frame_width': frame_width,
                'frame_height': frame_height,
                'motion_detected': motion_detected,
                'recording_id': recording_id,
                'detected_at': datetime.utcnow(),
            }

            # Create detection event
            db_event = crud.create_object_detection_event(db, event_data)

            # Try to match with identified objects (future enhancement)
            # For now, just create the detection without identification
            identified_object_name = None
            if db_event.identified_object:
                identified_object_name = db_event.identified_object.name

            db.close()

            # Trigger alert notification (async in background)
            # v3.10.0: Object detection alerts
            try:
                alert_manager = get_alert_manager()
                asyncio.create_task(
                    alert_manager.trigger_object_detection_alert(
                        camera_id=camera_id,
                        object_class=detection.class_name,
                        object_subclass=detection.subclass,
                        identified_object_name=identified_object_name,
                        confidence=detection.confidence,
                        event_data={
                            'detection_id': db_event.id,
                            'bbox': detection.bbox,
                            'frame_dimensions': (frame_width, frame_height),
                        }
                    )
                )
            except Exception as alert_error:
                # Don't fail detection if alert fails
                logger.error(f"Failed to trigger object detection alert: {alert_error}")

            return {
                'id': db_event.id,
                'object_class': detection.class_name,
                'object_subclass': detection.subclass,
                'confidence': detection.confidence,
                'bbox': detection.bbox,
                'detected_at': db_event.detected_at
            }

        except Exception as e:
            logger.error(f"Failed to save object detection: {e}")
            return None

    def get_recent_detections(self, limit: int = 10) -> List[Dict]:
        """Get recent detections from buffer"""
        return self.detections_buffer[-limit:]

    def clear_buffer(self):
        """Clear detections buffer"""
        self.detections_buffer.clear()


# Global singleton instance (similar to face_recognition pattern)
_object_detector: Optional[ObjectDetector] = None


def get_object_detector(
    enabled: bool = False,
    model_size: str = "yolov8n",
    confidence_threshold: float = 0.5,
    device: str = "cpu",
    classes_filter: Optional[List[str]] = None,
    force_reload: bool = False
) -> ObjectDetector:
    """
    Factory function to get object detector (singleton pattern)

    Args:
        enabled: Whether object detection is enabled
        model_size: YOLO model variant
        confidence_threshold: Minimum confidence threshold
        device: Device to run inference on
        classes_filter: Filter to specific object classes
        force_reload: Force reload of detector

    Returns:
        ObjectDetector instance
    """
    global _object_detector

    if _object_detector is None or force_reload:
        _object_detector = ObjectDetector(
            enabled=enabled,
            model_size=model_size,
            confidence_threshold=confidence_threshold,
            device=device,
            classes_filter=classes_filter
        )

    return _object_detector
