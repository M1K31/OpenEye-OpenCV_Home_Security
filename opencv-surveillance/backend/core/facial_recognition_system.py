# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Facial Recognition System
Complete face detection, recognition, and database management

This module provides real-time face detection, encoding, and matching using
OpenCV DNN for detection and dlib/face_recognition for encoding. Includes
face database management, training, and privacy features.
"""

import cv2
import numpy as np
import face_recognition
import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import pickle
import json
from pathlib import Path
import threading
from queue import Queue
import time

logger = logging.getLogger(__name__)


@dataclass
class Face:
    """Represents a detected face"""
    name: str
    encoding: np.ndarray
    bounding_box: Tuple[int, int, int, int]  # (top, right, bottom, left)
    confidence: float
    timestamp: datetime
    camera_id: str
    image_path: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary (excluding encoding for size)"""
        return {
            'name': self.name,
            'bounding_box': self.bounding_box,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'camera_id': self.camera_id,
            'image_path': self.image_path
        }


@dataclass
class Person:
    """Represents a person in the face database"""
    id: str
    name: str
    encodings: List[np.ndarray] = field(default_factory=list)
    face_images: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_seen: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)


class FaceDetector:
    """
    Face detection using OpenCV DNN
    
    Uses pre-trained deep learning model for fast and accurate face detection
    """
    
    def __init__(
        self,
        model_path: str = "models/face_detection_model/res10_300x300_ssd_iter_140000.caffemodel",
        config_path: str = "models/face_detection_model/deploy.prototxt",
        confidence_threshold: float = 0.5
    ):
        """
        Initialize face detector
        
        Args:
            model_path: Path to Caffe model file
            config_path: Path to prototxt config file
            confidence_threshold: Minimum confidence for detection
        """
        self.confidence_threshold = confidence_threshold
        
        try:
            self.net = cv2.dnn.readNetFromCaffe(config_path, model_path)
            logger.info("Face detection model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load face detection model: {e}")
            # Fallback to Haar Cascade
            self.net = None
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            logger.info("Using Haar Cascade fallback for face detection")
    
    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect faces in frame
        
        Args:
            frame: Input image (BGR format)
            
        Returns:
            List of bounding boxes (top, right, bottom, left)
        """
        if self.net is not None:
            return self._detect_dnn(frame)
        else:
            return self._detect_haar(frame)
    
    def _detect_dnn(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces using DNN model"""
        (h, w) = frame.shape[:2]
        
        # Prepare blob from frame
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)),
            1.0,
            (300, 300),
            (104.0, 177.0, 123.0)
        )
        
        # Forward pass
        self.net.setInput(blob)
        detections = self.net.forward()
        
        # Extract faces
        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            if confidence > self.confidence_threshold:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")
                
                # Convert to face_recognition format (top, right, bottom, left)
                faces.append((startY, endX, endY, startX))
        
        return faces
    
    def _detect_haar(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces using Haar Cascade"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detected_faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        # Convert to face_recognition format
        faces = []
        for (x, y, w, h) in detected_faces:
            faces.append((y, x + w, y + h, x))
        
        return faces


class FaceRecognitionSystem:
    """
    Complete face recognition system
    
    Handles face detection, encoding, matching, and database management
    """
    
    def __init__(
        self,
        database_path: str = "data/faces/database.pkl",
        face_images_dir: str = "data/faces/images",
        unknown_faces_dir: str = "data/faces/unknown",
        tolerance: float = 0.6,
        model: str = "hog"  # 'hog' or 'cnn'
    ):
        """
        Initialize face recognition system
        
        Args:
            database_path: Path to face database file
            face_images_dir: Directory for known face images
            unknown_faces_dir: Directory for unknown face images
            tolerance: Face matching tolerance (lower = stricter)
            model: Detection model ('hog' = CPU, 'cnn' = GPU)
        """
        self.database_path = Path(database_path)
        self.face_images_dir = Path(face_images_dir)
        self.unknown_faces_dir = Path(unknown_faces_dir)
        self.tolerance = tolerance
        self.model = model
        
        # Create directories
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.face_images_dir.mkdir(parents=True, exist_ok=True)
        self.unknown_faces_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize face detector
        self.detector = FaceDetector()
        
        # Load face database
        self.people: Dict[str, Person] = {}
        self.known_encodings: List[np.ndarray] = []
        self.known_names: List[str] = []
        self._load_database()
        
        # Recognition cache
        self._recognition_cache: Dict[str, Tuple[str, float, datetime]] = {}
        self._cache_timeout = timedelta(seconds=5)
        
        # Processing queue for async operations
        self._processing_queue: Queue = Queue()
        self._processing_thread = threading.Thread(
            target=self._process_queue,
            daemon=True
        )
        self._processing_thread.start()
        
        logger.info(f"Face recognition system initialized with {len(self.people)} people")
    
    def _load_database(self):
        """Load face database from disk"""
        try:
            if self.database_path.exists():
                with open(self.database_path, 'rb') as f:
                    data = pickle.load(f)
                    self.people = data.get('people', {})
                    
                    # Rebuild encoding lists
                    self.known_encodings = []
                    self.known_names = []
                    for person in self.people.values():
                        for encoding in person.encodings:
                            self.known_encodings.append(encoding)
                            self.known_names.append(person.name)
                    
                    logger.info(f"Loaded {len(self.people)} people from database")
        except Exception as e:
            logger.error(f"Error loading face database: {e}")
    
    def _save_database(self):
        """Save face database to disk"""
        try:
            data = {
                'people': self.people,
                'updated_at': datetime.now()
            }
            
            with open(self.database_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.debug("Face database saved")
        except Exception as e:
            logger.error(f"Error saving face database: {e}")
    
    def add_person(
        self,
        person_id: str,
        name: str,
        face_images: List[np.ndarray],
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Add person to face database
        
        Args:
            person_id: Unique identifier
            name: Person's name
            face_images: List of face images for training
            metadata: Additional metadata
            
        Returns:
            True if successful
        """
        try:
            encodings = []
            saved_paths = []
            
            for idx, image in enumerate(face_images):
                # Detect faces
                face_locations = face_recognition.face_locations(image, model=self.model)
                
                if len(face_locations) == 0:
                    logger.warning(f"No face detected in image {idx} for {name}")
                    continue
                
                if len(face_locations) > 1:
                    logger.warning(f"Multiple faces detected in image {idx} for {name}")
                    # Use the largest face
                    face_locations = [max(face_locations, key=lambda x: (x[2]-x[0]) * (x[1]-x[3]))]
                
                # Generate encoding
                face_encodings = face_recognition.face_encodings(image, face_locations)
                
                if len(face_encodings) > 0:
                    encodings.append(face_encodings[0])
                    
                    # Save face image
                    image_path = self.face_images_dir / f"{person_id}_{idx}.jpg"
                    cv2.imwrite(str(image_path), image)
                    saved_paths.append(str(image_path))
            
            if len(encodings) == 0:
                logger.error(f"Could not generate encodings for {name}")
                return False
            
            # Create person object
            person = Person(
                id=person_id,
                name=name,
                encodings=encodings,
                face_images=saved_paths,
                metadata=metadata or {}
            )
            
            # Add to database
            self.people[person_id] = person
            
            # Update known encodings
            for encoding in encodings:
                self.known_encodings.append(encoding)
                self.known_names.append(name)
            
            # Save database
            self._save_database()
            
            logger.info(f"Added {name} to face database with {len(encodings)} encodings")
            return True
        
        except Exception as e:
            logger.error(f"Error adding person to database: {e}")
            return False
    
    def remove_person(self, person_id: str) -> bool:
        """Remove person from database"""
        if person_id not in self.people:
            logger.warning(f"Person {person_id} not found in database")
            return False
        
        person = self.people[person_id]
        
        # Remove face images
        for image_path in person.face_images:
            try:
                Path(image_path).unlink()
            except:
                pass
        
        # Remove from database
        del self.people[person_id]
        
        # Rebuild encoding lists
        self.known_encodings = []
        self.known_names = []
        for p in self.people.values():
            for encoding in p.encodings:
                self.known_encodings.append(encoding)
                self.known_names.append(p.name)
        
        self._save_database()
        
        logger.info(f"Removed {person.name} from database")
        return True
    
    def recognize_faces(
        self,
        frame: np.ndarray,
        camera_id: str = "unknown"
    ) -> List[Face]:
        """
        Detect and recognize faces in frame
        
        Args:
            frame: Input image (BGR format)
            camera_id: Camera identifier
            
        Returns:
            List of Face objects
        """
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect face locations
        face_locations = self.detector.detect_faces(frame)
        
        if len(face_locations) == 0:
            return []
        
        # Generate encodings for detected faces
        try:
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        except Exception as e:
            logger.error(f"Error encoding faces: {e}")
            return []
        
        # Match faces
        faces = []
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # Check cache first
            encoding_hash = hash(face_encoding.tobytes())
            cache_key = f"{camera_id}_{encoding_hash}"
            
            cached = self._recognition_cache.get(cache_key)
            if cached and (datetime.now() - cached[2]) < self._cache_timeout:
                name, confidence = cached[0], cached[1]
            else:
                # Match against known faces
                name, confidence = self._match_face(face_encoding)
                
                # Update cache
                self._recognition_cache[cache_key] = (name, confidence, datetime.now())
            
            # Create Face object
            face = Face(
                name=name,
                encoding=face_encoding,
                bounding_box=face_location,
                confidence=confidence,
                timestamp=datetime.now(),
                camera_id=camera_id
            )
            
            faces.append(face)
            
            # Update last seen
            if name != "unknown":
                for person in self.people.values():
                    if person.name == name:
                        person.last_seen = datetime.now()
            
            # Save unknown faces
            if name == "unknown":
                self._queue_unknown_face(frame, face_location)
        
        return faces
    
    def _match_face(self, face_encoding: np.ndarray) -> Tuple[str, float]:
        """
        Match face encoding against known faces
        
        Returns:
            Tuple of (name, confidence)
        """
        if len(self.known_encodings) == 0:
            return "unknown", 0.0
        
        # Calculate distances
        distances = face_recognition.face_distance(self.known_encodings, face_encoding)
        
        # Find best match
        min_distance = min(distances)
        
        if min_distance > self.tolerance:
            return "unknown", 1.0 - min_distance
        
        # Get name of best match
        best_match_idx = np.argmin(distances)
        name = self.known_names[best_match_idx]
        confidence = 1.0 - min_distance
        
        return name, confidence
    
    def _queue_unknown_face(self, frame: np.ndarray, face_location: Tuple):
        """Queue unknown face for saving"""
        self._processing_queue.put(('save_unknown', frame, face_location))
    
    def _process_queue(self):
        """Background thread to process queued tasks"""
        while True:
            try:
                task = self._processing_queue.get(timeout=1)
                
                if task[0] == 'save_unknown':
                    _, frame, face_location = task
                    self._save_unknown_face(frame, face_location)
                
            except:
                continue
    
    def _save_unknown_face(self, frame: np.ndarray, face_location: Tuple):
        """Save unknown face to disk for later training"""
        try:
            top, right, bottom, left = face_location
            
            # Extract face region with padding
            padding = 20
            face_image = frame[
                max(0, top-padding):min(frame.shape[0], bottom+padding),
                max(0, left-padding):min(frame.shape[1], right+padding)
            ]
            
            # Save image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            image_path = self.unknown_faces_dir / f"unknown_{timestamp}.jpg"
            cv2.imwrite(str(image_path), face_image)
            
            logger.debug(f"Saved unknown face to {image_path}")
        except Exception as e:
            logger.error(f"Error saving unknown face: {e}")
    
    def draw_faces(
        self,
        frame: np.ndarray,
        faces: List[Face],
        draw_names: bool = True,
        blur_unknown: bool = False
    ) -> np.ndarray:
        """
        Draw bounding boxes and labels on frame
        
        Args:
            frame: Input frame
            faces: List of detected faces
            draw_names: Whether to draw names
            blur_unknown: Whether to blur unknown faces
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        for face in faces:
            top, right, bottom, left = face.bounding_box
            
            # Choose color based on recognition
            if face.name == "unknown":
                color = (0, 0, 255)  # Red for unknown
                
                if blur_unknown:
                    # Blur face region
                    face_region = annotated[top:bottom, left:right]
                    blurred = cv2.GaussianBlur(face_region, (99, 99), 30)
                    annotated[top:bottom, left:right] = blurred
            else:
                color = (0, 255, 0)  # Green for known
            
            # Draw rectangle
            cv2.rectangle(annotated, (left, top), (right, bottom), color, 2)
            
            # Draw label
            if draw_names:
                label = f"{face.name} ({face.confidence:.2f})"
                
                # Background for text
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                cv2.rectangle(
                    annotated,
                    (left, bottom - label_size[1] - 10),
                    (right, bottom),
                    color,
                    cv2.FILLED
                )
                
                # Text
                cv2.putText(
                    annotated,
                    label,
                    (left + 6, bottom - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    1
                )
        
        return annotated
    
    def get_statistics(self) -> Dict:
        """Get face recognition statistics"""
        return {
            'total_people': len(self.people),
            'total_encodings': len(self.known_encodings),
            'cache_size': len(self._recognition_cache),
            'people': [
                {
                    'id': p.id,
                    'name': p.name,
                    'num_encodings': len(p.encodings),
                    'last_seen': p.last_seen.isoformat() if p.last_seen else None
                }
                for p in self.people.values()
            ]
        }
    
    def export_database(self, export_path: str):
        """Export database to JSON format"""
        data = {
            'people': [
                {
                    'id': p.id,
                    'name': p.name,
                    'face_images': p.face_images,
                    'created_at': p.created_at.isoformat(),
                    'last_seen': p.last_seen.isoformat() if p.last_seen else None,
                    'metadata': p.metadata
                }
                for p in self.people.values()
            ],
            'exported_at': datetime.now().isoformat()
        }
        
        with open(export_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Database exported to {export_path}")


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize system
    fr_system = FaceRecognitionSystem()
    
    # Add a person (example)
    # Load sample images
    sample_images = [
        cv2.imread("path/to/person1_1.jpg"),
        cv2.imread("path/to/person1_2.jpg"),
        cv2.imread("path/to/person1_3.jpg")
    ]
    
    if all(img is not None for img in sample_images):
        fr_system.add_person(
            person_id="person_001",
            name="John Doe",
            face_images=sample_images,
            metadata={"role": "employee", "department": "IT"}
        )
    
    # Test with webcam
    cap = cv2.VideoCapture(0)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Recognize faces
            faces = fr_system.recognize_faces(frame, camera_id="webcam")
            
            # Draw annotations
            annotated = fr_system.draw_faces(frame, faces)
            
            # Display
            cv2.imshow('Face Recognition', annotated)
            
            # Print detections
            for face in faces:
                print(f"Detected: {face.name} (confidence: {face.confidence:.2f})")
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        
        # Print statistics
        stats = fr_system.get_statistics()
        print(f"\nStatistics: {json.dumps(stats, indent=2)}")