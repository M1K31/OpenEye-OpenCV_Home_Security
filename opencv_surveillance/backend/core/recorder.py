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
import threading
from datetime import datetime
from backend.core.timeutil import utcnow
import asyncio
from backend.core.alert_manager import get_alert_manager

from typing import List, Dict, Optional


def _schedule_coroutine(coro) -> bool:
    """
    Schedule a coroutine on the app's main event loop from a camera thread.

    The Recorder runs inside a per-camera worker thread with no event loop, so
    asyncio.create_task() raised "no running event loop" and the alert coroutine
    was never awaited (audit runtime finding). Hand it to the loop captured at
    FastAPI startup instead. Never raises; drops the alert if the loop is gone.
    """
    try:
        from backend.core.notification_dispatch import get_app_loop
        loop = get_app_loop()
        if loop is None or loop.is_closed() or not loop.is_running():
            coro.close()
            return False
        asyncio.run_coroutine_threadsafe(coro, loop)
        return True
    except Exception:
        try:
            coro.close()
        except Exception:
            pass
        return False


class Recorder:
    """
    Handles video recording to a file with face detection metadata
    """

    def __init__(self, output_dir="recordings", max_recording_duration=300):
        self.output_dir = output_dir
        self.is_recording = False
        self.writer = None
        # Serialize all access to self.writer. The background processor thread
        # calls write() while the main thread can call stop()/start() — releasing
        # the FFmpeg VideoWriter on one thread while another is mid-write() is a
        # use-after-free that SIGSEGVs inside libavcodec. RLock so nested calls
        # on the same thread (start() releasing a stale writer) don't deadlock.
        self._writer_lock = threading.RLock()
        self.filename = ""
        # Which codec actually opened, so callers and metadata can tell whether a
        # given file is browser-playable rather than guessing from the extension
        # (mp4v and avc1 both produce .mp4, and only one of them plays).
        self.codec_in_use = None
        self.metadata_filename = ""
        # Maximum recording time in seconds (default: 5 minutes)
        self.max_recording_duration = max_recording_duration

        # NEW: Track face detections during recording
        self.detected_faces = []
        self.recording_start_time = None
        self.frame_count = 0
        # Motion events observed during this recording, linked to the DB row on stop.
        self.associated_motion_event_ids = []

        # Create the output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def start(self, frame_width, frame_height, fps=20, camera_id="unknown"):
        """
        Starts a new recording session.

        Args:
            frame_width: Width of video frames
            frame_height: Height of video frames
            fps: Frames per second (default: 20)
            camera_id: Camera identifier for filename (default: "unknown")
        """
        if self.is_recording:
            print("Already recording.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Codec order is a trade between PLAYABILITY and STABILITY, and both sides
        # of it have bitten this project.
        #
        # Playability: mp4v is MPEG-4 Part 2 (Simple Profile). No browser can play
        # it — not Chrome, not Safari, not Firefox — so with mp4v first, every
        # recording was unplayable in the Events page and could only be watched by
        # downloading it into VLC or QuickTime. Confirmed by ffprobe on a real
        # recording: codec_name=mpeg4, profile=Simple Profile, codec_tag=mp4v.
        # <video> needs H.264, VP9 or AV1.
        #
        # Stability: avc1 was moved to LAST precisely because in-process libx264
        # could hit an encoder error and SEGFAULT the backend under sustained
        # recording on macOS — a native crash Python cannot catch or log. That is
        # why the order looked backwards.
        #
        # H.264 now goes first so recordings are watchable in the browser, with
        # mp4v immediately behind it: if the H.264 writer cannot be opened we fall
        # straight back and recording still happens. What this does NOT protect
        # against is the historical crash, which occurred during sustained
        # writeFrame rather than at open time — no amount of open-time checking
        # sees that coming.
        #
        # If recording starts crashing the backend again, this is the first thing
        # to suspect, and the fix needs no code change:
        #     OPENEYE_VIDEO_CODEC=mp4v
        # restores the previous behaviour immediately.
        codecs_to_try = [
            ("avc1", ".mp4"),  # H.264 — the only one browsers can play
            ("mp4v", ".mp4"),  # MPEG-4 Part 2 — robust, but not browser-playable
            ("MJPG", ".avi"),  # Motion JPEG — very robust last resort
        ]
        _preferred = os.getenv("OPENEYE_VIDEO_CODEC", "").strip()
        if _preferred:
            codecs_to_try.sort(key=lambda c: 0 if c[0] == _preferred else 1)

        self.writer = None
        for codec_name, ext in codecs_to_try:
            try:
                self.filename = os.path.join(
                    self.output_dir, f"{camera_id}_motion_{timestamp}{ext}"
                )
                self.metadata_filename = os.path.join(
                    self.output_dir, f"{camera_id}_motion_{timestamp}_metadata.json"
                )

                fourcc = cv2.VideoWriter_fourcc(*codec_name)
                self.writer = cv2.VideoWriter(
                    self.filename, fourcc, fps, (frame_width, frame_height)
                )

                if self.writer.isOpened():
                    self.codec_in_use = codec_name
                    # Say plainly when a recording will not be watchable in the
                    # browser, rather than leaving someone to discover it by
                    # clicking play on a black rectangle.
                    if codec_name == "avc1":
                        print(f"Successfully initialized video writer with codec "
                              f"'{codec_name}' (H.264, browser-playable) for {self.filename}")
                    else:
                        print(f"Successfully initialized video writer with codec "
                              f"'{codec_name}' for {self.filename} — NOTE: this codec is "
                              f"not playable in a browser; the Events page will offer "
                              f"download only")
                    break
                else:
                    # Clean up the writer object
                    self.writer.release()
                    self.writer = None
            except Exception as e:
                print(f"Failed to initialize with codec '{codec_name}': {e}")
                self.writer = None

        if not self.writer or not self.writer.isOpened():
            print(f"Error: Could not open video writer for {self.filename} with any available codec")
            return

        # Everything this recording needs is set BEFORE is_recording is raised.
        #
        # The order used to be the other way round, which published the recorder
        # as running one statement before it had a start time. Anything reading
        # the recorder in that window saw is_recording=True with
        # recording_start_time=None and raised
        #
        #     unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'
        #
        # A one-statement window sounds harmless; the streaming loop reads at
        # 30 FPS, and it landed four times in one afternoon.
        self.recording_start_time = utcnow()
        self.frame_count = 0
        self.detected_faces = []
        self.associated_motion_event_ids = []
        self.is_recording = True

        print(f"Started recording to {self.filename}")

        # NEW: Trigger recording started alert
        try:
            alert_manager = get_alert_manager()
            # Get camera_id from the calling context if available
            camera_id = getattr(self, "camera_id", "unknown")
            _schedule_coroutine(
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
        # Hold the lock across the whole write so stop()/release() can't free the
        # writer between the None-check and the native write() call.
        with self._writer_lock:
            if self.is_recording and self.writer:
                self.writer.write(frame)
                self.frame_count += 1

    def add_motion_event_id(self, motion_event_id: int):
        """
        Track a motion event ID associated with this recording.

        Parity with FFmpegRecorder.add_motion_event_id — the cv2 Recorder was
        missing this method, so camera_manager's call raised AttributeError on
        every motion event (audit runtime finding). IDs are linked to the
        recording row when recording stops.
        """
        if self.is_recording and motion_event_id:
            if motion_event_id not in self.associated_motion_event_ids:
                self.associated_motion_event_ids.append(motion_event_id)

    def add_face_detection(self, face_data: Dict):
        """
        NEW: Add face detection data to the recording metadata

        Args:
            face_data: Dictionary containing face detection information
        """
        if self.is_recording:
            face_data["frame_number"] = self.frame_count
            face_data["timestamp"] = utcnow().isoformat()
            self.detected_faces.append(face_data)

    def should_stop_recording(self):
        """
        Check if recording should stop due to maximum duration exceeded.

        Returns:
            bool: True if max duration exceeded, False otherwise
        """
        if not self.is_recording or not self.recording_start_time:
            return False

        duration = (utcnow() - self.recording_start_time).total_seconds()
        if duration >= self.max_recording_duration:
            print(f"Maximum recording duration ({self.max_recording_duration}s) reached. Stopping recording.")
            return True
        return False

    def stop(self):
        """
        Stops the current recording session and saves metadata.
        """
        if not self.is_recording:
            return

        # Flip is_recording and release the writer under the lock so an in-flight
        # write() on the background thread finishes (or no-ops) before release —
        # releasing mid-write SIGSEGVs inside libavcodec.
        with self._writer_lock:
            self.is_recording = False
            writer = self.writer
            self.writer = None
        if writer:
            writer.release()

            # Guarded as well as ordered. stop() can be reached from the camera
            # thread and from shutdown, and a recording with no start time is a
            # recording of nothing — worth zero, not worth an exception that
            # loses the file's metadata entirely.
            duration = (
                (utcnow() - self.recording_start_time).total_seconds()
                if self.recording_start_time else 0.0
            )

            # Get file size
            file_size = (
                os.path.getsize(
                    self.filename) if os.path.exists(
                    self.filename) else 0)

            # NEW: Save metadata
            self._save_metadata(duration, file_size)

            print(f"Stopped recording. Video saved to {self.filename}")
            print(f"Duration: {duration:.2f}s, Frames: {self.frame_count}, Faces detected: {len(self.detected_faces)}")

            # NEW: Trigger recording stopped alert
            try:
                alert_manager = get_alert_manager()
                camera_id = getattr(self, "camera_id", "unknown")
                _schedule_coroutine(
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

    def add_detected_face(self, face_data):
        """
        Add detected face information to the recording metadata.
        """
        if self.is_recording:
            timestamp = utcnow().isoformat()
            face_entry = {
                "timestamp": timestamp,
                "frame_number": self.frame_count,
                **face_data,
            }
            self.detected_faces.append(face_entry)

    def _save_metadata(self, duration: float, file_size: int):
        """
        NEW: Save recording metadata to JSON file and database
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
                    "ended_at": utcnow().isoformat(),
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

            # Save to JSON file
            with open(self.metadata_filename, "w") as f:
                json.dump(metadata, f, indent=2)

            print(f"Metadata saved to {self.metadata_filename}")

            # NEW: Save to database
            try:
                from backend.database.utils import get_db_context
                from backend.database import crud
                from backend.core.paths import paths

                # FIXED: Use context manager to prevent session leak (v3.6.0.1)
                with get_db_context() as db:
                    # Get relative path for database storage
                    relative_path = paths.get_relative_path(self.filename)

                    camera_id = getattr(self, "camera_id", "unknown")

                    recording_data = {
                        "camera_id": camera_id,
                        "recording_path": relative_path,
                        "started_at": self.recording_start_time,
                        "ended_at": utcnow(),
                        "duration_seconds": duration,
                        "motion_detected": True,  # Always true if we're recording
                        "faces_detected": len(self.detected_faces),
                        "known_faces_detected": known_faces_count,
                        "file_size_bytes": file_size,
                        "frame_count": self.frame_count,
                    }

                    db_event = crud.create_recording_event(db, recording_data)
                    print(f"✅ Recording event created in database: ID={db_event.id}")

                    # Link the motion events observed during this clip to the row.
                    if self.associated_motion_event_ids:
                        from backend.database.models import MotionDetectionEvent
                        linked = db.query(MotionDetectionEvent).filter(
                            MotionDetectionEvent.id.in_(self.associated_motion_event_ids)
                        ).update(
                            {"recording_id": db_event.id, "recording_path": relative_path},
                            synchronize_session=False,
                        )
                        db.commit()
                        print(f"🔗 Linked {linked} motion events to recording ID={db_event.id}")

            except Exception as db_error:
                print(f"⚠️ Failed to save recording to database: {db_error}")
                # Don't fail the entire operation if database save fails

        except Exception as e:
            print(f"Error saving metadata: {e}")

    def get_current_recording_info(self) -> Optional[Dict]:
        """
        NEW: Get information about the current recording
        """
        if not self.is_recording or not self.recording_start_time:
            return None

        duration = (utcnow() - self.recording_start_time).total_seconds()
        unique_people = set(face.get("name", "Unknown")
                            for face in self.detected_faces)

        return {
            "filename": os.path.basename(self.filename),
            "duration_seconds": duration,
            "frame_count": self.frame_count,
            "faces_detected": len(self.detected_faces),
            "unique_people": len(unique_people),
        }
