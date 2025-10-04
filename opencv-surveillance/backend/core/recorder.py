# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye.


"""
Enhanced Video Recorder with Face Detection Tracking
REPLACES your existing recorder.py
"""

import cv2
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional

class Recorder:
    """
    Handles video recording to a file with face detection metadata
    """
    def __init__(self, output_dir="recordings"):
        self.output_dir = output_dir
        self.is_recording = False
        self.writer = None
        self.filename = ""
        self.metadata_filename = ""
        
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
        self.filename = os.path.join(self.output_dir, f"motion_{timestamp}.mp4")
        self.metadata_filename = os.path.join(self.output_dir, f"motion_{timestamp}_metadata.json")

        # Using 'mp4v' codec for MP4 files.
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(self.filename, fourcc, fps, (frame_width, frame_height))

        if not self.writer.isOpened():
            print(f"Error: Could not open video writer for {self.filename}")
            return

        self.is_recording = True
        self.recording_start_time = datetime.now()
        self.frame_count = 0
        self.detected_faces = []
        
        print(f"Started recording to {self.filename}")

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
            face_data['frame_number'] = self.frame_count
            face_data['timestamp'] = datetime.now().isoformat()
            self.detected_faces.append(face_data)

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
            duration = (datetime.now() - self.recording_start_time).total_seconds()
            
            # Get file size
            file_size = os.path.getsize(self.filename) if os.path.exists(self.filename) else 0
            
            # NEW: Save metadata
            self._save_metadata(duration, file_size)
            
            print(f"Stopped recording. Video saved to {self.filename}")
            print(f"Duration: {duration:.2f}s, Frames: {self.frame_count}, Faces detected: {len(self.detected_faces)}")
        
        # Reset tracking variables
        self.filename = ""
        self.metadata_filename = ""
        self.detected_faces = []
        self.recording_start_time = None
        self.frame_count = 0

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
                person_name = face.get('name', 'Unknown')
                unique_people.add(person_name)
                
                if person_name == 'Unknown':
                    unknown_faces_count += 1
                else:
                    known_faces_count += 1
            
            metadata = {
                'recording': {
                    'filename': os.path.basename(self.filename),
                    'started_at': self.recording_start_time.isoformat(),
                    'ended_at': datetime.now().isoformat(),
                    'duration_seconds': duration,
                    'frame_count': self.frame_count,
                    'file_size_bytes': file_size
                },
                'face_detections': {
                    'total_detections': len(self.detected_faces),
                    'unique_people': list(unique_people),
                    'known_faces': known_faces_count,
                    'unknown_faces': unknown_faces_count,
                    'detections': self.detected_faces
                }
            }
            
            with open(self.metadata_filename, 'w') as f:
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
        unique_people = set(face.get('name', 'Unknown') for face in self.detected_faces)
        
        return {
            'filename': os.path.basename(self.filename),
            'duration_seconds': duration,
            'frame_count': self.frame_count,
            'faces_detected': len(self.detected_faces),
            'unique_people': len(unique_people)
        }