# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security


"""
Enhanced Video Recorder with Face Detection Tracking
REPLACES your existing recorder.py
"""

import cv2
import os
import json
import time
import json
from datetime import datetime
import asyncio
from backend.core.alert_manager import get_alert_manager

from typing import List, Dict, Optional


class Recorder:
    """
    Handles video recording to a file with face detection metadata
    """

    def __init__(self, output_dir="recordings", max_recording_duration=300):
        self.output_dir = output_dir
        self.is_recording = False
        self.writer = None
        self.filename = ""
        self.metadata_filename = ""
        # Maximum recording time in seconds (default: 5 minutes)
        self.max_recording_duration = max_recording_duration

        # NEW: Track face detections during recording
        self.detected_faces = []
        self.recording_start_time = None
        self.frame_count = 0

        # Create the output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def start(self, frame_width, frame_height, fps=20):
        """
        Starts a new recording session.
        """
        if self.is_recording:
            print("Already recording.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Try different codecs based on platform and availability
        # For macOS with AVFoundation, use MJPG or avc1
        codecs_to_try = [
            ("avc1", ".mp4"),  # H.264 for AVFoundation on macOS
            ("mp4v", ".mp4"),  # MPEG-4 fallback
            ("MJPG", ".avi"),  # Motion JPEG fallback
        ]

        self.writer = None
        for codec_name, ext in codecs_to_try:
            try:
                self.filename = os.path.join(
                    self.output_dir, f"motion_{timestamp}{ext}"
                )
                self.metadata_filename = os.path.join(
                    self.output_dir, f"motion_{timestamp}_metadata.json"
                )

                fourcc = cv2.VideoWriter_fourcc(*codec_name)
                self.writer = cv2.VideoWriter(
                    self.filename, fourcc, fps, (frame_width, frame_height)
                )

                if self.writer.isOpened():
                    print(
                        f"Successfully initialized video writer with codec '{codec_name}' for {
                            self.filename}")
                    break
                else:
                    # Clean up the writer object
                    self.writer.release()
                    self.writer = None
            except Exception as e:
                print(f"Failed to initialize with codec '{codec_name}': {e}")
                self.writer = None

        if not self.writer or not self.writer.isOpened():
            print(
                f"Error: Could not open video writer for {
                    self.filename} with any available codec")
            return

        self.is_recording = True
        self.recording_start_time = datetime.now()
        self.frame_count = 0
        self.detected_faces = []

        print(f"Started recording to {self.filename}")

        # NEW: Trigger recording started alert
        try:
            alert_manager = get_alert_manager()
            # Get camera_id from the calling context if available
            camera_id = getattr(self, "camera_id", "unknown")
            asyncio.create_task(
                alert_manager.trigger_recording_alert(
                    camera_id=camera_id,
                    recording_started=True,
                    event_data={"filename": self.filename},
                )
            )
        except Exception as e:
            print(f"Error triggering recording alert: {e}")

    def write(self, frame):
        """
        Writes a frame to the current recording.
        """
        if self.is_recording and self.writer:
            self.writer.write(frame)
            self.frame_count += 1

    def add_face_detection(self, face_data: Dict):
        """
        NEW: Add face detection data to the recording metadata

        Args:
            face_data: Dictionary containing face detection information
        """
        if self.is_recording:
            face_data["frame_number"] = self.frame_count
            face_data["timestamp"] = datetime.now().isoformat()
            self.detected_faces.append(face_data)

    def should_stop_recording(self):
        """
        Check if recording should stop due to maximum duration exceeded.

        Returns:
            bool: True if max duration exceeded, False otherwise
        """
        if not self.is_recording or not self.recording_start_time:
            return False

        duration = (datetime.now() - self.recording_start_time).total_seconds()
        if duration >= self.max_recording_duration:
            print(
                f"Maximum recording duration ({
                    self.max_recording_duration}s) reached. Stopping recording.")
            return True
        return False

    def stop(self):
        """
        Stops the current recording session and saves metadata.
        """
        if not self.is_recording:
            return

        self.is_recording = False

        if self.writer:
            self.writer.release()
            self.writer = None

            # Calculate recording duration
            duration = (
                datetime.now() -
                self.recording_start_time).total_seconds()

            # Get file size
            file_size = (
                os.path.getsize(
                    self.filename) if os.path.exists(
                    self.filename) else 0)

            # NEW: Save metadata
            self._save_metadata(duration, file_size)

            print(f"Stopped recording. Video saved to {self.filename}")
            print(
                f"Duration: {
                    duration:.2f}s, Frames: {
                    self.frame_count}, Faces detected: {
                    len(
                        self.detected_faces)}")

            # NEW: Trigger recording stopped alert
            try:
                alert_manager = get_alert_manager()
                camera_id = getattr(self, "camera_id", "unknown")
                asyncio.create_task(
                    alert_manager.trigger_recording_alert(
                        camera_id=camera_id,
                        recording_started=False,
                        event_data={
                            "filename": self.filename,
                            "duration": duration,
                            "faces_detected": len(self.detected_faces),
                        },
                    )
                )
            except Exception as e:
                print(f"Error triggering recording alert: {e}")

        # Reset tracking variables
        self.filename = ""
        self.metadata_filename = ""
        self.detected_faces = []
        self.recording_start_time = None
        self.frame_count = 0

    def _save_metadata(self, duration, file_size):
        """
        Saves recording metadata to a JSON file.
        """
        if not hasattr(
                self,
                "metadata_filename") or not self.metadata_filename:
            return

        metadata = {
            "filename": os.path.basename(self.filename),
            "full_path": self.filename,
            "start_time": self.recording_start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": duration,
            "frame_count": self.frame_count,
            "file_size_bytes": file_size,
            "faces_detected": len(self.detected_faces),
            "detected_faces": self.detected_faces,
        }

        try:
            with open(self.metadata_filename, "w") as f:
                json.dump(metadata, f, indent=2)
            print(f"Metadata saved to {self.metadata_filename}")
        except Exception as e:
            print(f"Error saving metadata: {e}")

    def add_detected_face(self, face_data):
        """
        Add detected face information to the recording metadata.
        """
        if self.is_recording:
            timestamp = datetime.now().isoformat()
            face_entry = {
                "timestamp": timestamp,
                "frame_number": self.frame_count,
                **face_data,
            }
            self.detected_faces.append(face_entry)

    def _save_metadata(self, duration: float, file_size: int):
        """
        NEW: Save recording metadata to JSON file
        """
        try:
            # Aggregate face detection data
            unique_people = set()
            known_faces_count = 0
            unknown_faces_count = 0

            for face in self.detected_faces:
                person_name = face.get("name", "Unknown")
                unique_people.add(person_name)

                if person_name == "Unknown":
                    unknown_faces_count += 1
                else:
                    known_faces_count += 1

            metadata = {
                "recording": {
                    "filename": os.path.basename(self.filename),
                    "started_at": self.recording_start_time.isoformat(),
                    "ended_at": datetime.now().isoformat(),
                    "duration_seconds": duration,
                    "frame_count": self.frame_count,
                    "file_size_bytes": file_size,
                },
                "face_detections": {
                    "total_detections": len(self.detected_faces),
                    "unique_people": list(unique_people),
                    "known_faces": known_faces_count,
                    "unknown_faces": unknown_faces_count,
                    "detections": self.detected_faces,
                },
            }

            with open(self.metadata_filename, "w") as f:
                json.dump(metadata, f, indent=2)

            print(f"Metadata saved to {self.metadata_filename}")

        except Exception as e:
            print(f"Error saving metadata: {e}")

    def get_current_recording_info(self) -> Optional[Dict]:
        """
        NEW: Get information about the current recording
        """
        if not self.is_recording:
            return None

        duration = (datetime.now() - self.recording_start_time).total_seconds()
        unique_people = set(face.get("name", "Unknown")
                            for face in self.detected_faces)

        return {
            "filename": os.path.basename(self.filename),
            "duration_seconds": duration,
            "frame_count": self.frame_count,
            "faces_detected": len(self.detected_faces),
            "unique_people": len(unique_people),
        }
