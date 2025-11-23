"""
v3.10.0: Object Detection System using YOLO
Detects and tracks vehicles, animals, and packages using YOLOv8
"""
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("ultralytics not installed. Object detection disabled. Install with: pip install ultralytics")


@dataclass
class ObjectDetection:
    """Dataclass for object detection results"""
    class_name: str  # vehicle, animal, package, person
    subclass: str  # car, truck, dog, cat, box, etc.
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    yolo_class_id: int  # Original YOLO class ID
    yolo_class_name: str  # Original YOLO class name


class ObjectDetectionManager:
    """
    Manages YOLO-based object detection for surveillance cameras

    Detects and classifies:
    - Vehicles (cars, trucks, buses, motorcycles, bicycles)
    - Animals (dogs, cats, birds, horses, cows, sheep, etc.)
    - Packages (backpack, handbag, suitcase, umbrella, etc.)
    - People (person class - can be used alongside face recognition)
    """

    # YOLO COCO class mappings to our object classes
    # Based on COCO dataset (80 classes)
    CLASS_MAPPINGS = {
        # Vehicles
        'car': ('vehicle', 'car'),
        'truck': ('vehicle', 'truck'),
        'bus': ('vehicle', 'bus'),
        'motorcycle': ('vehicle', 'motorcycle'),
        'bicycle': ('vehicle', 'bicycle'),
        'train': ('vehicle', 'train'),
        'boat': ('vehicle', 'boat'),
        'airplane': ('vehicle', 'airplane'),

        # Animals
        'dog': ('animal', 'dog'),
        'cat': ('animal', 'cat'),
        'bird': ('animal', 'bird'),
        'horse': ('animal', 'horse'),
        'sheep': ('animal', 'sheep'),
        'cow': ('animal', 'cow'),
        'elephant': ('animal', 'elephant'),
        'bear': ('animal', 'bear'),
        'zebra': ('animal', 'zebra'),
        'giraffe': ('animal', 'giraffe'),

        # Packages/Objects
        'backpack': ('package', 'backpack'),
        'umbrella': ('package', 'umbrella'),
        'handbag': ('package', 'handbag'),
        'tie': ('package', 'tie'),
        'suitcase': ('package', 'suitcase'),
        'frisbee': ('package', 'frisbee'),
        'skis': ('package', 'skis'),
        'snowboard': ('package', 'snowboard'),
        'sports ball': ('package', 'sports_ball'),
        'kite': ('package', 'kite'),
        'baseball bat': ('package', 'baseball_bat'),
        'baseball glove': ('package', 'baseball_glove'),
        'skateboard': ('package', 'skateboard'),
        'surfboard': ('package', 'surfboard'),
        'tennis racket': ('package', 'tennis_racket'),
        'bottle': ('package', 'bottle'),
        'wine glass': ('package', 'wine_glass'),
        'cup': ('package', 'cup'),
        'fork': ('package', 'fork'),
        'knife': ('package', 'knife'),
        'spoon': ('package', 'spoon'),
        'bowl': ('package', 'bowl'),

        # People (optional - can be used alongside face recognition)
        'person': ('person', 'person'),
    }

    def __init__(
        self,
        model_size: str = "yolov8n",  # nano (fastest), s, m, l, x (most accurate)
        confidence_threshold: float = 0.5,
        device: str = "cpu",  # 'cpu' or 'cuda' for GPU
        enable_tracking: bool = False,  # Enable object tracking between frames
    ):
        """
        Initialize YOLO object detection manager

        Args:
            model_size: YOLO model variant (yolov8n, yolov8s, yolov8m, yolov8l, yolov8x)
            confidence_threshold: Minimum confidence for detections (0.0-1.0)
            device: Device to run inference on ('cpu' or 'cuda')
            enable_tracking: Enable object tracking (uses ByteTrack algorithm)
        """
        self.model_size = model_size
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.enable_tracking = enable_tracking
        self.model = None
        self.initialized = False

        if not YOLO_AVAILABLE:
            logger.error("YOLO not available. Install ultralytics: pip install ultralytics")
            return

        try:
            # Load YOLO model
            logger.info(f"Loading YOLO model: {model_size} on {device}")
            self.model = YOLO(f"{model_size}.pt")

            # Move to device
            if device == "cuda":
                import torch
                if torch.cuda.is_available():
                    self.model.to('cuda')
                    logger.info("YOLO model loaded on GPU")
                else:
                    logger.warning("CUDA not available. Falling back to CPU")
                    self.device = "cpu"
            else:
                logger.info("YOLO model loaded on CPU")

            self.initialized = True
            logger.info(f"Object detection initialized with {model_size}")

        except Exception as e:
            logger.error(f"Failed to initialize YOLO model: {e}")
            self.initialized = False

    def detect_objects(
        self,
        frame: np.ndarray,
        classes_filter: Optional[List[str]] = None
    ) -> List[ObjectDetection]:
        """
        Detect objects in a frame

        Args:
            frame: Input image (BGR format from OpenCV)
            classes_filter: Optional list of classes to detect ['vehicle', 'animal', 'package', 'person']
                           If None, detects all supported classes

        Returns:
            List of ObjectDetection dataclasses with detection results
        """
        if not self.initialized or self.model is None:
            return []

        try:
            # Run YOLO inference
            if self.enable_tracking:
                results = self.model.track(
                    frame,
                    conf=self.confidence_threshold,
                    persist=True,
                    verbose=False
                )
            else:
                results = self.model(
                    frame,
                    conf=self.confidence_threshold,
                    verbose=False
                )

            detections = []

            # Process results
            for result in results:
                boxes = result.boxes

                for i, box in enumerate(boxes):
                    # Get class ID and name
                    class_id = int(box.cls[0])
                    yolo_class_name = self.model.names[class_id]

                    # Map to our object classes
                    if yolo_class_name not in self.CLASS_MAPPINGS:
                        continue  # Skip unmapped classes

                    object_class, object_subclass = self.CLASS_MAPPINGS[yolo_class_name]

                    # Filter by class if specified
                    if classes_filter and object_class not in classes_filter:
                        continue

                    # Get confidence and bbox
                    confidence = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                    # Convert to (x, y, width, height) format
                    x = int(x1)
                    y = int(y1)
                    width = int(x2 - x1)
                    height = int(y2 - y1)

                    # Create detection
                    detection = ObjectDetection(
                        class_name=object_class,
                        subclass=object_subclass,
                        confidence=confidence,
                        bbox=(x, y, width, height),
                        yolo_class_id=class_id,
                        yolo_class_name=yolo_class_name
                    )

                    detections.append(detection)

            return detections

        except Exception as e:
            logger.error(f"Object detection failed: {e}")
            return []

    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[ObjectDetection],
        show_confidence: bool = True
    ) -> np.ndarray:
        """
        Draw bounding boxes and labels on frame

        Args:
            frame: Input image
            detections: List of detections to draw
            show_confidence: Whether to show confidence scores

        Returns:
            Frame with drawn detections
        """
        # Color map for different object classes
        COLOR_MAP = {
            'vehicle': (0, 255, 255),  # Yellow
            'animal': (255, 0, 255),   # Magenta
            'package': (0, 255, 0),    # Green
            'person': (255, 255, 0),   # Cyan
        }

        frame_copy = frame.copy()

        for detection in detections:
            x, y, width, height = detection.bbox
            color = COLOR_MAP.get(detection.class_name, (255, 255, 255))

            # Draw bounding box
            cv2.rectangle(
                frame_copy,
                (x, y),
                (x + width, y + height),
                color,
                2
            )

            # Draw label
            label = f"{detection.subclass}"
            if show_confidence:
                label += f" {detection.confidence:.2f}"

            # Background for label
            (label_width, label_height), _ = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                1
            )
            cv2.rectangle(
                frame_copy,
                (x, y - label_height - 10),
                (x + label_width, y),
                color,
                -1
            )

            # Text
            cv2.putText(
                frame_copy,
                label,
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1
            )

        return frame_copy

    def get_detection_summary(self, detections: List[ObjectDetection]) -> Dict[str, int]:
        """
        Get summary counts of detected objects by class

        Args:
            detections: List of detections

        Returns:
            Dictionary with counts by object class
        """
        summary = {
            'vehicle': 0,
            'animal': 0,
            'package': 0,
            'person': 0,
            'total': len(detections)
        }

        for detection in detections:
            if detection.class_name in summary:
                summary[detection.class_name] += 1

        return summary


# Global singleton instance (similar to face_recognition pattern)
_object_detection_manager: Optional[ObjectDetectionManager] = None


def get_object_detection_manager(
    model_size: str = "yolov8n",
    confidence_threshold: float = 0.5,
    device: str = "cpu",
    enable_tracking: bool = False,
    force_reload: bool = False
) -> ObjectDetectionManager:
    """
    Factory function to get object detection manager (singleton pattern)

    Args:
        model_size: YOLO model variant
        confidence_threshold: Minimum confidence threshold
        device: Device to run inference on
        enable_tracking: Enable object tracking
        force_reload: Force reload of model

    Returns:
        ObjectDetectionManager instance
    """
    global _object_detection_manager

    if _object_detection_manager is None or force_reload:
        _object_detection_manager = ObjectDetectionManager(
            model_size=model_size,
            confidence_threshold=confidence_threshold,
            device=device,
            enable_tracking=enable_tracking
        )

    return _object_detection_manager
