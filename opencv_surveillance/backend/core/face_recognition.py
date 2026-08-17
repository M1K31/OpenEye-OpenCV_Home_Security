# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Face Recognition Manager for OpenEye Surveillance System
Uses face_recognition library built on dlib for accurate face detection and recognition

IMPORTANT: Face recognition training and OpenCV MOG2 motion detection can cause
memory corruption when running concurrently due to thread safety issues in dlib/OpenCV.
A global lock is used to prevent concurrent access during intensive operations.
"""

import os
import json
import logging
import threading
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
import numpy as np
import cv2
from backend.core.paths import paths
from backend.core.image_preprocessing import get_preprocessor

logger = logging.getLogger(__name__)

# Graceful degradation: face_recognition requires dlib which may not be available
# (especially on Raspberry Pi or lightweight installs)
try:
    import face_recognition as _face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    _face_recognition = None  # type: ignore[assignment]
    FACE_RECOGNITION_AVAILABLE = False
    logger.warning(
        "face_recognition not installed — face detection/recognition disabled. "
        "Install with: pip install face_recognition (requires dlib). "
        "Run install-deps.sh for guided installation."
    )

# Global lock to prevent concurrent dlib/OpenCV operations that cause memory corruption
# This is necessary because dlib (used by face_recognition) and OpenCV's MOG2
# background subtractor can corrupt memory when running in parallel threads
_face_recognition_lock = threading.Lock()

# Flag to indicate training is in progress (for UI feedback)
_training_in_progress = False


def _encode_gallery_image(image):
    """
    Produce face encodings for a gallery photo, tolerating pre-cropped faces.

    Gallery photos come from two very different sources. Some are ordinary
    photos a user dropped in, where the face is one region of a larger scene.
    Others are detection snapshots the system cropped itself — 144x144 boxes
    that are *entirely* face, with no margin around them.

    The detector cannot find a face in the second kind. HOG needs some context
    around the head to match its gradient template, and a tight crop has none,
    so every snapshot silently failed to encode. That is why a person built out
    of their own detections ended up with photos on disk but zero encodings, and
    could never be recognised afterwards.

    So: try normal detection first, and only if it finds nothing, fall back to
    treating the whole image as the face box. The fallback is gated on the image
    looking like a crop — small and roughly square — so a large photo that
    genuinely contains no face still yields nothing rather than a meaningless
    encoding of scenery.
    """
    encodings = _face_recognition.face_encodings(image, model="large")
    if encodings:
        return encodings

    height, width = image.shape[:2]
    aspect = width / height if height else 0
    if max(width, height) > 400 or not (0.6 <= aspect <= 1.7):
        return []

    # (top, right, bottom, left) — the entire image.
    return _face_recognition.face_encodings(
        image, known_face_locations=[(0, width, height, 0)], model="large"
    )


# ---------------------------------------------------------------- gallery size
#
# Recognition compares every detected face against the whole gallery on every
# frame, so per-frame cost is linear in the number of encodings held. Training
# appends and never removed, which made that cost grow by roughly one encoding
# per person per camera per day, without limit.
#
# Two mechanisms, because they answer different problems. Dedupe stops the
# gallery growing for the ordinary case — the same person, the same doorway,
# the same light — where another encoding teaches the recogniser nothing. The
# cap is a backstop for a subject whose appearance genuinely varies every day,
# which dedupe cannot catch.
#
# 0.28 is measured, not guessed. Against the live 701-encoding gallery, greedy
# dedupe at this distance keeps ~150 of 561 training encodings while every
# held-out face still matches, and the WORST held-out match sits 0.212 below
# the 0.6 recognition threshold — the same margin as the undeduplicated gallery
# (0.204). It buys a ~73% reduction for no measurable loss.
#
# Deliberately far below the ~0.6 recognition threshold: this asks "is this
# redundant?", which is a much stricter question than "is this the same person?".
DUPLICATE_DISTANCE = 0.28

# Reached only by a subject dedupe cannot compress. Ten people at this cap is
# 2,500 comparisons per face per frame, which an older Intel Mac and a Pi can
# both carry. On the measured gallery dedupe alone stays far under it, so this
# is a true backstop rather than the thing doing the work.
MAX_ENCODINGS_PER_PERSON = 250


class FaceRecognitionManager:
    """
    Manages face recognition operations including training, recognition, and storage
    """

    def __init__(self, faces_folder: Optional[Path] = None,
                 encodings_file: str = "face_encodings.pkl",
                 enable_preprocessing: bool = True):
        """
        Initialize the face recognition manager

        Args:
            faces_folder: Directory containing person subdirectories with face images (uses PathManager if None)
            encodings_file: Path to save/load face encodings
            enable_preprocessing: Enable image preprocessing for better accuracy
        """
        # Use PathManager for faces directory
        self.faces_folder = Path(faces_folder) if faces_folder else paths.faces_dir
        # Store encodings file in the faces folder for better organization
        if os.path.isabs(encodings_file):
            self.encodings_file = encodings_file
        else:
            # Relative path - store in faces folder
            self.encodings_file = str(self.faces_folder / encodings_file)
        self.known_face_encodings = []
        self.known_face_names = []
        self.face_locations = []
        self.face_names = []
        self.detection_method = "hog"  # 'hog' for CPU, 'cnn' for GPU
        self.recognition_threshold = 0.6
        self.last_recognition_time = None
        self.enable_preprocessing = enable_preprocessing
        self.preprocessor = get_preprocessor() if enable_preprocessing else None
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
            f"FaceRecognitionManager initialized with {len(self.known_face_names)} known faces "
            f"(preprocessing: {'enabled' if enable_preprocessing else 'disabled'})"
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
        logger.info(f"Recognition threshold set to: {self.recognition_threshold}")
        # Save settings to persist across restarts
        self.save_encodings()

    def train_face_recognition(self) -> Dict:
        """
        Train the face recognition model by loading all images from the faces folder.

        Uses a global lock to prevent concurrent access that can cause memory corruption
        when running alongside OpenCV's MOG2 background subtractor.

        Returns:
            Dict with training statistics
        """
        global _training_in_progress

        if not FACE_RECOGNITION_AVAILABLE:
            logger.warning("face_recognition library not installed — training unavailable")
            return {"total_people": 0, "total_encodings": 0, "training_time": 0.0}

        logger.info("Starting face recognition training...")
        logger.info("🔒 Acquiring face recognition lock to prevent memory corruption...")

        # Acquire lock to prevent concurrent dlib operations that cause crashes
        with _face_recognition_lock:
            _training_in_progress = True
            logger.info("🔓 Lock acquired, beginning training...")
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
                        image = _face_recognition.load_image_file(image_path)
                        face_encodings = _encode_gallery_image(image)

                        if len(face_encodings) > 0:
                            # Use the first face found in the image
                            self.known_face_encodings.append(face_encodings[0])
                            self.known_face_names.append(person_name)
                            encodings_count += 1
                            logger.debug(f"Encoded face from: {image_path}")
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
            _training_in_progress = False
            return result

    def train_person(self, person_name: str) -> Dict:
        """
        Train face recognition for a specific person only.

        This is more efficient than full training when adding/updating a single person.
        It removes existing encodings for the person and re-encodes from their photos.

        Args:
            person_name: Name of the person to train

        Returns:
            Dict with training statistics for this person
        """
        global _training_in_progress

        if not FACE_RECOGNITION_AVAILABLE:
            logger.warning("face_recognition library not installed — training unavailable")
            return {
                "success": False,
                "message": "face_recognition library not installed",
                "person_name": person_name,
                "encodings_added": 0,
            }

        person_path = self.faces_folder / person_name

        if not person_path.exists() or not person_path.is_dir():
            logger.warning(f"Person folder not found: {person_path}")
            return {
                "success": False,
                "message": f"Person '{person_name}' not found",
                "person_name": person_name,
                "encodings_added": 0
            }

        logger.info(f"Training face recognition for person: {person_name}")
        logger.info("🔒 Acquiring face recognition lock...")

        with _face_recognition_lock:
            _training_in_progress = True
            start_time = datetime.now()

            # Remove existing encodings for this person
            indices_to_remove = [
                i for i, name in enumerate(self.known_face_names)
                if name == person_name
            ]

            removed_count = len(indices_to_remove)

            # Remove in reverse order to maintain indices
            for idx in reversed(indices_to_remove):
                del self.known_face_encodings[idx]
                del self.known_face_names[idx]

            if removed_count > 0:
                logger.info(f"Removed {removed_count} existing encodings for {person_name}")

            # Encode new photos for this person
            encodings_added = 0
            photos_processed = 0
            photos_failed = 0

            for image_file_path in person_path.iterdir():
                if not image_file_path.name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue

                photos_processed += 1

                try:
                    image = _face_recognition.load_image_file(image_file_path)
                    face_encodings = _encode_gallery_image(image)

                    if len(face_encodings) > 0:
                        self.known_face_encodings.append(face_encodings[0])
                        self.known_face_names.append(person_name)
                        encodings_added += 1
                        logger.debug(f"Encoded face from: {image_file_path}")
                    else:
                        photos_failed += 1
                        logger.warning(f"No face found in: {image_file_path}")

                except Exception as e:
                    photos_failed += 1
                    logger.error(f"Error processing {image_file_path}: {e}")

            # Save updated encodings
            self.save_encodings()

            training_time = (datetime.now() - start_time).total_seconds()

            # Update statistics
            self.statistics["total_encodings"] = len(self.known_face_encodings)
            self.statistics["total_people"] = len(set(self.known_face_names))

            result = {
                "success": True,
                "message": f"Trained {encodings_added} encodings for '{person_name}'",
                "person_name": person_name,
                "encodings_added": encodings_added,
                "encodings_removed": removed_count,
                "photos_processed": photos_processed,
                "photos_failed": photos_failed,
                "training_time": training_time
            }

            logger.info(f"Person training complete: {result}")
            _training_in_progress = False
            return result

    def _indices_for(self, person_name: str) -> list:
        return [i for i, n in enumerate(self.known_face_names) if n == person_name]

    def _is_redundant(self, candidate, indices: list) -> bool:
        """
        True when an encoding this person already has says the same thing.

        Redundancy, not identity: the threshold is far tighter than the one used
        to decide whether two faces are the same person.
        """
        if not indices:
            return False
        known = [self.known_face_encodings[i] for i in indices]
        return float(np.min(_face_recognition.face_distance(known, candidate))) < DUPLICATE_DISTANCE

    def _evict_to_cap(self, person_name: str) -> int:
        """
        Drop the most redundant encodings until this person is back under the cap.

        Not "drop the oldest". A single night-time capture is worth more than the
        fifty daytime ones that resemble each other, and age does not measure
        that. Each round removes whichever encoding sits closest to another of
        the same person — the one whose removal loses the least coverage of how
        they can look.

        The pairwise distances are computed ONCE and then masked. Rebuilding
        them per removal is the obvious implementation and is quadratic per
        removal on top of quadratic overall: measured at 6s to compact a
        701-encoding gallery but ~400s for 1500, which would exceed the 120s
        training timeout. That matters more than it appears — a timeout is
        recorded as a training failure, a failed training leaves trained_at
        null, and an untrained cluster keeps collecting faces. The slow version
        would have made a large gallery grow faster.
        """
        indices = self._indices_for(person_name)
        excess = len(indices) - MAX_ENCODINGS_PER_PERSON
        if excess <= 0:
            return 0

        encodings = np.asarray([self.known_face_encodings[i] for i in indices],
                               dtype=np.float64)
        distances = np.linalg.norm(
            encodings[:, None, :] - encodings[None, :, :], axis=-1)
        np.fill_diagonal(distances, np.inf)

        for _ in range(excess):
            # Smallest nearest-neighbour distance = the least distinctive
            # encoding this person has. A removed row is all-inf, so it can
            # neither be chosen again nor keep another encoding alive.
            victim = int(np.argmin(distances.min(axis=1)))
            distances[victim, :] = np.inf
            distances[:, victim] = np.inf

        surviving = set(np.flatnonzero(np.isfinite(distances).any(axis=1)).tolist())
        doomed = sorted((indices[i] for i in range(len(indices))
                         if i not in surviving), reverse=True)
        for i in doomed:
            del self.known_face_encodings[i]
            del self.known_face_names[i]
        return len(doomed)

    def train_from_cluster_export(
        self, person_name: str, new_photo_paths: list
    ) -> Dict:
        """
        Incremental training for cluster-exported photos only.

        Unlike train_face_recognition() (full retrain) or train_person()
        (per-person retrain), this method ONLY encodes the new photos and
        appends them to existing encodings.  O(new_photos) not O(all_photos).
        """
        global _training_in_progress

        if not FACE_RECOGNITION_AVAILABLE:
            return {"success": False, "message": "face_recognition not available"}

        if not new_photo_paths:
            return {
                "success": True,
                "source": "cluster_export",
                "person_name": person_name,
                "encodings_added": 0,
                "photos_failed": 0,
                "training_time": 0.0,
            }

        logger.info(
            f"Incremental cluster training for '{person_name}': "
            f"{len(new_photo_paths)} new photos"
        )

        with _face_recognition_lock:
            _training_in_progress = True
            start_time = datetime.now()
            encodings_added = 0
            photos_failed = 0
            encodings_skipped = 0

            for photo_path in new_photo_paths:
                try:
                    image = _face_recognition.load_image_file(photo_path)
                    face_encodings = _encode_gallery_image(image)

                    if face_encodings:
                        if self._is_redundant(face_encodings[0],
                                              self._indices_for(person_name)):
                            encodings_skipped += 1
                        else:
                            self.known_face_encodings.append(face_encodings[0])
                            self.known_face_names.append(person_name)
                            encodings_added += 1
                    else:
                        photos_failed += 1
                        logger.warning(f"No face in cluster export: {photo_path}")
                except Exception as e:
                    photos_failed += 1
                    logger.error(f"Error encoding cluster photo {photo_path}: {e}")

            encodings_evicted = self._evict_to_cap(person_name)

            self.save_encodings()
            self.statistics["total_encodings"] = len(self.known_face_encodings)
            self.statistics["total_people"] = len(set(self.known_face_names))

            if encodings_skipped or encodings_evicted:
                # Reported rather than silent: a gallery that stops growing
                # should be visibly a decision, not something that looks like
                # training quietly failing.
                logger.info(
                    "Gallery for '%s': +%d, %d redundant, %d evicted, %d held",
                    person_name, encodings_added, encodings_skipped,
                    encodings_evicted, len(self._indices_for(person_name)),
                )

            training_time = (datetime.now() - start_time).total_seconds()
            _training_in_progress = False

            result = {
                "success": True,
                "encodings_skipped_redundant": encodings_skipped,
                "encodings_evicted": encodings_evicted,
                "source": "cluster_export",
                "person_name": person_name,
                "encodings_added": encodings_added,
                "photos_failed": photos_failed,
                "training_time": training_time,
            }
            logger.info(f"Cluster training complete: {result}")
            return result

    def _encodings_json_path(self) -> str:
        """JSON path for the pickle-free encodings store (audit F-13)."""
        base, _ = os.path.splitext(self.encodings_file)
        return base + ".json"

    def save_encodings(self):
        """
        Save face encodings to a JSON file.

        JSON is used instead of pickle so that loading the store can never
        execute code, even if the data directory is tampered with (audit F-13).
        Encodings are 128-d float vectors and serialize cleanly as lists.
        """
        try:
            data = {
                "version": 2,
                "encodings": [
                    np.asarray(enc, dtype=np.float64).tolist()
                    for enc in self.known_face_encodings
                ],
                "names": list(self.known_face_names),
                "threshold": self.recognition_threshold,
                "method": self.detection_method,
            }
            json_path = self._encodings_json_path()
            tmp_path = json_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp_path, json_path)  # atomic write
            try:
                os.chmod(json_path, 0o600)
            except OSError:
                pass
            logger.info(f"Encodings saved to: {json_path}")
        except Exception as e:
            logger.error(f"Error saving encodings: {e}")

    def load_encodings(self):
        """
        Load face encodings from the JSON store.

        Legacy ``.pkl`` files are intentionally NOT deserialized: calling
        ``pickle.load`` on a writable data file is a code-execution vector
        (audit F-13). If only a legacy pickle exists it is ignored and the user
        must re-train faces to regenerate the JSON store.
        """
        json_path = self._encodings_json_path()
        if not os.path.exists(json_path):
            if os.path.exists(self.encodings_file):
                logger.warning(
                    "Found legacy pickle encodings at %s but refusing to load it "
                    "for security reasons. Re-train faces to regenerate %s.",
                    self.encodings_file,
                    json_path,
                )
            else:
                logger.info("No existing encodings file found")
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.known_face_encodings = [
                np.asarray(enc, dtype=np.float64) for enc in data.get("encodings", [])
            ]
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
        self, frame: np.ndarray,
        scale_mode: str = "auto",
        upsample_times: int = 1,
        min_face_size: int = 20
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        Detect and recognize faces in a video frame

        Args:
            frame: OpenCV frame (BGR format)
            scale_mode: Scaling strategy - "auto", "none", or float string like "0.5"
                - "auto": Adaptive scaling based on resolution (recommended)
                - "none": No scaling, use native resolution (slower but more accurate)
                - "0.5": Manual scale factor (0.25 to 1.0)
            upsample_times: Number of times to upsample image for face detection (0-2)
                - 0: Fastest, may miss small faces
                - 1: Default, good balance (recommended)
                - 2: Slowest, finds smaller faces
            min_face_size: Minimum face size in pixels to return (filters small false positives)

        Returns:
            Tuple of (annotated_frame, list of detected faces with metadata)
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return frame, []

        # Try to acquire lock without blocking - skip frame if training is in progress
        # This prevents SIGSEGV crashes from concurrent dlib operations
        if not _face_recognition_lock.acquire(blocking=False):
            logger.debug("Face recognition skipped - training in progress")
            return frame, []

        try:
            # Track if we have known faces to compare against
            has_known_faces = len(self.known_face_encodings) > 0

            # Apply preprocessing for better face recognition
            processed_frame = frame
            if self.enable_preprocessing and self.preprocessor:
                processed_frame = self.preprocessor.preprocess_for_face_recognition(frame)

            # Convert BGR to RGB for face_recognition
            rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)

            height, width = rgb_frame.shape[:2]

            # Determine scale factor based on mode
            if scale_mode == "none":
                # No scaling - use native resolution
                scale_factor = 1.0
            elif scale_mode == "auto":
                # Adaptive scaling based on input resolution
                # Goal: Scale to a size where faces are still detectable (~80px minimum)
                # while keeping processing time reasonable
                if width > 1920:
                    # 4K or higher: Scale down significantly for performance
                    scale_factor = 1280 / width
                elif width > 1280:
                    # HD (1080p): Moderate scaling
                    scale_factor = 960 / width
                elif width > 800:
                    # Medium resolution: Light scaling
                    scale_factor = min(1.0, 720 / width)
                else:
                    # Low resolution: No scaling to preserve face detail
                    scale_factor = 1.0
            else:
                # Manual scale factor (parse from string)
                try:
                    scale_factor = float(scale_mode)
                    scale_factor = max(0.1, min(1.0, scale_factor))
                except ValueError:
                    logger.warning(f"Invalid scale_mode '{scale_mode}', using auto")
                    scale_factor = 1.0

            # Apply scaling if needed
            if scale_factor < 1.0:
                small_frame = cv2.resize(rgb_frame, (0, 0), fx=scale_factor, fy=scale_factor)
            else:
                small_frame = rgb_frame

            # Detect faces using face_recognition library
            # number_of_times_to_upsample helps find smaller faces at cost of speed
            face_locations = _face_recognition.face_locations(
                small_frame,
                model=self.detection_method,
                number_of_times_to_upsample=upsample_times
            )

            # Get face encodings
            face_encodings = _face_recognition.face_encodings(
                small_frame, face_locations)

            detected_faces = []

            # Calculate inverse scale factor for scaling locations back to original size
            inverse_scale = 1.0 / scale_factor if scale_factor > 0 else 1.0

            # Process each detected face
            for (top, right, bottom, left), face_encoding in zip(
                face_locations, face_encodings
            ):
                # Scale back up face locations to original frame coordinates
                top = int(top * inverse_scale)
                right = int(right * inverse_scale)
                bottom = int(bottom * inverse_scale)
                left = int(left * inverse_scale)

                # Filter out faces smaller than minimum size
                face_height = bottom - top
                face_width = right - left
                if face_height < min_face_size or face_width < min_face_size:
                    logger.debug(f"Skipping small face: {face_width}x{face_height}px < {min_face_size}px minimum")
                    continue

                name = "Unknown"
                confidence = 0.0

                # Only compare with known faces if we have any
                if has_known_faces:
                    # Compare with known faces
                    matches = _face_recognition.compare_faces(
                        self.known_face_encodings,
                        face_encoding,
                        tolerance=self.recognition_threshold,
                    )

                    # Calculate face distances
                    face_distances = _face_recognition.face_distance(
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
                label = f"{name} ({confidence:.2f})" if name != "Unknown" else "Unknown"
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
                self.statistics["last_recognition"] = self.last_recognition_time.isoformat()
                self.statistics["recognitions_today"] += len(detected_faces)

            return frame, detected_faces
        finally:
            _face_recognition_lock.release()

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

    def delete_person(self, person_name: str, auto_train: bool = False) -> bool:
        """
        Delete a person and all their images

        Args:
            person_name: Name of the person to delete
            auto_train: If True, retrain the model after deletion (default False to prevent freezing)

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

            # Remove encodings for this person from memory (fast operation)
            indices_to_remove = [i for i, name in enumerate(self.known_face_names) if name == person_name]
            for i in sorted(indices_to_remove, reverse=True):
                del self.known_face_encodings[i]
                del self.known_face_names[i]
            
            # Update statistics
            self.statistics["total_people"] = len(set(self.known_face_names))
            self.statistics["total_encodings"] = len(self.known_face_encodings)
            
            # Save updated encodings
            self.save_encodings()
            
            # Optionally retrain model (can be slow, caller should use background task)
            if auto_train:
                self.train_face_recognition()
            
            return True
        except Exception as e:
            logger.error(f"Error deleting person: {e}")
            return False

    def list_people(self) -> List[Dict]:
        """
        Get list of all people with their photo counts
        This scans the filesystem to find all person folders, ensuring
        that people with existing photos are always included even if
        they're not in the encodings file yet.

        Returns:
            List of person dictionaries
        """
        people = []

        if not os.path.exists(self.faces_folder):
            return people

        for person_path in self.faces_folder.iterdir():
            # Skip files (like face_encodings.pkl)
            if not person_path.is_dir():
                continue
                
            # Skip hidden directories
            if person_path.name.startswith('.'):
                continue
                
            person_name = person_path.name

            # Count photos and get preview photo
            try:
                photo_files = [
                    f
                    for f in os.listdir(person_path)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ]
                photo_count = len(photo_files)
                
                # Get first photo for preview (sorted by name for consistency)
                preview_photo_url = None
                if photo_files:
                    photo_files.sort()
                    first_photo = photo_files[0]
                    # URL format: /faces/{person_name}/{filename}
                    preview_photo_url = f"/faces/{person_name}/{first_photo}"
            except (OSError, PermissionError) as e:
                logger.warning(f"Error reading photos from {person_path}: {e}")
                photo_count = 0
                preview_photo_url = None

            people.append({
                "name": person_name,
                "photo_count": photo_count,
                "path": str(person_path),
                "preview_photo_url": preview_photo_url
            })

        return sorted(people, key=lambda x: x["name"])

    def get_statistics(self) -> Dict:
        """Get face recognition statistics"""
        return self.statistics.copy()

    def is_available(self) -> bool:
        """
        Check if face recognition is available and ready.

        Returns True if face_recognition library is available, regardless of
        whether known faces are loaded. This allows the system to detect
        unknown faces for clustering.
        """
        return FACE_RECOGNITION_AVAILABLE


# Global instance
_face_manager: Optional[FaceRecognitionManager] = None


def reset_face_manager():
    """
    Reset the global face manager instance (useful for testing or path changes)
    """
    global _face_manager
    _face_manager = None
    logger.info("Face manager singleton reset")


def get_face_manager(faces_folder: str = None) -> FaceRecognitionManager:
    """
    Get or create the global face recognition manager instance

    Args:
        faces_folder: Directory containing person subdirectories with face images
                     If None, uses the default from PathManager (data/faces)

    Returns:
        Global FaceRecognitionManager instance
    """
    global _face_manager
    
    # Always use PathManager default if no folder specified
    if faces_folder is None:
        faces_folder = str(paths.faces_dir)
    
    # Resolve paths for comparison
    faces_folder_resolved = str(Path(faces_folder).resolve())
    
    if _face_manager is None:
        logger.info(f"Initializing FaceRecognitionManager with folder: {faces_folder_resolved}")
        _face_manager = FaceRecognitionManager(faces_folder=faces_folder)
    elif str(_face_manager.faces_folder.resolve()) != faces_folder_resolved:
        # Reinitialize if faces folder changed
        logger.info(
            f"Faces folder changed from {_face_manager.faces_folder} to {faces_folder_resolved}, reinitializing...")
        _face_manager = FaceRecognitionManager(faces_folder=faces_folder)
    return _face_manager


def is_training_in_progress() -> bool:
    """
    Check if face recognition training is currently in progress.
    Used by UI to display warning about skipped face detections.

    Returns:
        True if training is in progress, False otherwise
    """
    return _training_in_progress
