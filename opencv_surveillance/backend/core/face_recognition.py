# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Face Recognition Manager for OpenEye Surveillance System
Uses face_recognition library built on dlib for accurate face detection and recognition
"""

import os
import pickle
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
import face_recognition
import numpy as np
import cv2
from backend.core.paths import paths

logger = logging.getLogger(__name__)


class FaceRecognitionManager:
    """
    Manages face recognition operations including training, recognition, and storage
    """

    def __init__(self, faces_folder: Optional[Path] = None,
                 encodings_file: str = "face_encodings.pkl"):
        """
        Initialize the face recognition manager

        Args:
            faces_folder: Directory containing person subdirectories with face images (uses PathManager if None)
            encodings_file: Path to save/load face encodings
        """
        # Use PathManager for faces directory
        self.faces_folder = Path(faces_folder) if faces_folder else paths.faces_dir
        self.encodings_file = encodings_file
        self.known_face_encodings = []
        self.known_face_names = []
        self.face_locations = []
        self.face_names = []
        self.detection_method = "hog"  # 'hog' for CPU, 'cnn' for GPU
        self.recognition_threshold = 0.6
        self.last_recognition_time = None
        self.statistics = {
            "total_people": 0,
            "total_encodings": 0,
            "recognitions_today": 0,
            "last_recognition": None,
        }

        # Create faces folder if it doesn't exist
        self.faces_folder.mkdir(parents=True, exist_ok=True)

        # Load existing encodings if available
        self.load_encodings()

        logger.info(
            f"FaceRecognitionManager initialized with {len(self.known_face_names)} known faces"
        )

    def set_detection_method(self, method: str):
        """Set face detection method (hog or cnn)"""
        if method.lower() in ["hog", "cnn"]:
            self.detection_method = method.lower()
            logger.info(f"Detection method set to: {self.detection_method}")
            # Save settings to persist across restarts
            self.save_encodings()
        else:
            logger.warning(f"Invalid detection method: {method}")

    def set_recognition_threshold(self, threshold: float):
        """Set recognition confidence threshold (0.0 - 1.0, lower = stricter)"""
        self.recognition_threshold = max(0.0, min(1.0, threshold))
        logger.info(
            f"Recognition threshold set to: {
                self.recognition_threshold}")
        # Save settings to persist across restarts
        self.save_encodings()

    def train_face_recognition(self) -> Dict:
        """
        Train the face recognition model by loading all images from the faces folder

        Returns:
            Dict with training statistics
        """
        logger.info("Starting face recognition training...")
        start_time = datetime.now()

        self.known_face_encodings = []
        self.known_face_names = []

        if not self.faces_folder.exists():
            logger.warning(f"Faces folder not found: {self.faces_folder}")
            return {
                "total_people": 0,
                "total_encodings": 0,
                "training_time": 0}

        people_count = 0
        encodings_count = 0

        # Iterate through each person's folder
        for person_path in self.faces_folder.iterdir():
            if not person_path.is_dir():
                continue
            person_name = person_path.name

            people_count += 1
            logger.info(f"Processing images for: {person_name}")

            # Load all images for this person
            for image_file_path in person_path.iterdir():
                if not image_file_path.name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue

                image_path = image_file_path

                try:
                    # Load image and get face encodings
                    image = face_recognition.load_image_file(image_path)
                    face_encodings = face_recognition.face_encodings(
                        image, model="large"  # Use large model for better accuracy
                    )

                    if len(face_encodings) > 0:
                        # Use the first face found in the image
                        self.known_face_encodings.append(face_encodings[0])
                        self.known_face_names.append(person_name)
                        encodings_count += 1
                        logger.debug(f"Encoded face from: {image_file}")
                    else:
                        logger.warning(f"No face found in: {image_path}")

                except Exception as e:
                    logger.error(f"Error processing {image_path}: {e}")

        # Save encodings to file
        self.save_encodings()

        training_time = (datetime.now() - start_time).total_seconds()

        # Update statistics
        self.statistics["total_people"] = people_count
        self.statistics["total_encodings"] = encodings_count

        result = {
            "total_people": people_count,
            "total_encodings": encodings_count,
            "training_time": training_time,
        }

        logger.info(f"Training complete: {result}")
        return result

    def save_encodings(self):
        """Save face encodings to file"""
        try:
            data = {
                "encodings": self.known_face_encodings,
                "names": self.known_face_names,
                "threshold": self.recognition_threshold,
                "method": self.detection_method,
            }
            with open(self.encodings_file, "wb") as f:
                pickle.dump(data, f)
            logger.info(f"Encodings saved to: {self.encodings_file}")
        except Exception as e:
            logger.error(f"Error saving encodings: {e}")

    def load_encodings(self):
        """Load face encodings from file"""
        if not os.path.exists(self.encodings_file):
            logger.info("No existing encodings file found")
            return

        try:
            with open(self.encodings_file, "rb") as f:
                data = pickle.load(f)

            self.known_face_encodings = data.get("encodings", [])
            self.known_face_names = data.get("names", [])
            self.recognition_threshold = data.get("threshold", 0.6)
            self.detection_method = data.get("method", "hog")

            # Update statistics
            self.statistics["total_encodings"] = len(self.known_face_encodings)
            self.statistics["total_people"] = len(set(self.known_face_names))

            logger.info(
                f"Loaded {len(self.known_face_encodings)} encodings for "
                f"{len(set(self.known_face_names))} people"
            )
        except Exception as e:
            logger.error(f"Error loading encodings: {e}")

    def recognize_faces_in_frame(
        self, frame: np.ndarray
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        Detect and recognize faces in a video frame

        Args:
            frame: OpenCV frame (BGR format)

        Returns:
            Tuple of (annotated_frame, list of detected faces with metadata)
        """
        if len(self.known_face_encodings) == 0:
            return frame, []

        # Convert BGR to RGB for face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Resize frame for faster processing (optional)
        small_frame = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)

        # Detect faces
        face_locations = face_recognition.face_locations(
            small_frame, model=self.detection_method
        )

        # Get face encodings
        face_encodings = face_recognition.face_encodings(
            small_frame, face_locations)

        detected_faces = []

        # Process each detected face
        for (top, right, bottom, left), face_encoding in zip(
            face_locations, face_encodings
        ):
            # Scale back up face locations
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            # Compare with known faces
            matches = face_recognition.compare_faces(
                self.known_face_encodings,
                face_encoding,
                tolerance=self.recognition_threshold,
            )

            name = "Unknown"
            confidence = 0.0

            # Calculate face distances
            face_distances = face_recognition.face_distance(
                self.known_face_encodings, face_encoding
            )

            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name = self.known_face_names[best_match_index]
                    confidence = 1.0 - face_distances[best_match_index]

            # Encode face encoding to base64 for database storage
            import base64
            encoding_str = base64.b64encode(face_encoding.tobytes()).decode('utf-8')

            # Store detection info
            detected_faces.append(
                {
                    "name": name,
                    "confidence": float(confidence),
                    "location": {
                        "top": int(top),
                        "right": int(right),
                        "bottom": int(bottom),
                        "left": int(left),
                    },
                    "timestamp": datetime.now().isoformat(),
                    "encoding": encoding_str,  # Add encoding for clustering
                }
            )

            # Draw rectangle around face
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

            # Draw label background
            cv2.rectangle(
                frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED
            )

            # Draw label text
            label = f"{name} ({
                confidence:.2f})" if name != "Unknown" else "Unknown"
            cv2.putText(
                frame,
                label,
                (left + 6, bottom - 6),
                cv2.FONT_HERSHEY_DUPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

        # Update statistics
        if detected_faces:
            self.last_recognition_time = datetime.now()
            self.statistics["last_recognition"] = self.last_recognition_time.isoformat(
            )
            self.statistics["recognitions_today"] += len(detected_faces)

        return frame, detected_faces

    def add_person(self, person_name: str) -> bool:
        """
        Create a new person directory

        Args:
            person_name: Name of the person to add

        Returns:
            True if successful, False otherwise
        """
        person_path = self.faces_folder / person_name

        if person_path.exists():
            logger.warning(f"Person already exists: {person_name}")
            return False

        try:
            os.makedirs(person_path)
            logger.info(f"Created person directory: {person_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating person directory: {e}")
            return False

    def delete_person(self, person_name: str) -> bool:
        """
        Delete a person and all their images

        Args:
            person_name: Name of the person to delete

        Returns:
            True if successful, False otherwise
        """
        person_path = self.faces_folder / person_name

        if not os.path.exists(person_path):
            logger.warning(f"Person not found: {person_name}")
            return False

        try:
            import shutil

            shutil.rmtree(person_path)
            logger.info(f"Deleted person: {person_name}")

            # Retrain model
            self.train_face_recognition()
            return True
        except Exception as e:
            logger.error(f"Error deleting person: {e}")
            return False

    def list_people(self) -> List[Dict]:
        """
        Get list of all people with their photo counts

        Returns:
            List of person dictionaries
        """
        people = []

        if not os.path.exists(self.faces_folder):
            return people

        for person_path in self.faces_folder.iterdir():
            if not person_path.is_dir():
                continue
            person_name = person_path.name

            # Count photos
            photo_count = len(
                [
                    f
                    for f in os.listdir(person_path)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ]
            )

            people.append({"name": person_name,
                           "photo_count": photo_count,
                           "path": person_path})

        return sorted(people, key=lambda x: x["name"])

    def get_statistics(self) -> Dict:
        """Get face recognition statistics"""
        return self.statistics.copy()

    def is_available(self) -> bool:
        """Check if face recognition is available and ready"""
        return len(self.known_face_encodings) > 0


# Global instance
_face_manager: Optional[FaceRecognitionManager] = None


def get_face_manager(faces_folder: str = "faces") -> FaceRecognitionManager:
    """
    Get or create the global face recognition manager instance

    Args:
        faces_folder: Directory containing person subdirectories with face images

    Returns:
        Global FaceRecognitionManager instance
    """
    global _face_manager
    if _face_manager is None:
        _face_manager = FaceRecognitionManager(faces_folder=faces_folder)
    elif _face_manager.faces_folder != faces_folder:
        # Reinitialize if faces folder changed
        logger.info(
            f"Faces folder changed from {
                _face_manager.faces_folder} to {faces_folder}")
        _face_manager = FaceRecognitionManager(faces_folder=faces_folder)
    return _face_manager
