# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye.
import cv2
import os
import time
import json
from datetime import datetime
import asyncio
from backend.core.alert_manager import get_alert_manager


class Recorder:
    """
    Handles video recording to a file.
    """
    def __init__(self, output_dir="recordings"):
        self.output_dir = output_dir
        self.is_recording = False
        self.writer = None
        self.filename = ""

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
        
        # NEW: Trigger recording started alert
        try:
            alert_manager = get_alert_manager()
            # Get camera_id from the calling context if available
            camera_id = getattr(self, 'camera_id', 'unknown')
            asyncio.create_task(alert_manager.trigger_recording_alert(
                camera_id=camera_id,
                recording_started=True,
                event_data={'filename': self.filename}
            ))
        except Exception as e:
            print(f"Error triggering recording alert: {e}")

    def write(self, frame):
        """
        Writes a frame to the current recording.
        """
        if self.is_recording and self.writer:
            self.writer.write(frame)
            self.frame_count += 1

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
            
            # NEW: Trigger recording stopped alert
            try:
                alert_manager = get_alert_manager()
                camera_id = getattr(self, 'camera_id', 'unknown')
                asyncio.create_task(alert_manager.trigger_recording_alert(
                    camera_id=camera_id,
                    recording_started=False,
                    event_data={
                        'filename': self.filename,
                        'duration': duration,
                        'faces_detected': len(self.detected_faces)
                    }
                ))
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
        if not hasattr(self, 'metadata_filename') or not self.metadata_filename:
            return
            
        metadata = {
            'filename': os.path.basename(self.filename),
            'full_path': self.filename,
            'start_time': self.recording_start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'duration_seconds': duration,
            'frame_count': self.frame_count,
            'file_size_bytes': file_size,
            'faces_detected': len(self.detected_faces),
            'detected_faces': self.detected_faces
        }
        
        try:
            with open(self.metadata_filename, 'w') as f:
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
                'timestamp': timestamp,
                'frame_number': self.frame_count,
                **face_data
            }
            self.detected_faces.append(face_entry)