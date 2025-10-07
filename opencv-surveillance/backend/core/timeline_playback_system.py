# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Timeline & Playback System
Event timeline, video playback, and clip management

This module provides a complete timeline interface for browsing events,
playing back recordings, exporting clips, and managing video storage.
"""

import cv2
import logging
from typing import List, Dict, Optional, Tuple, Generator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import json
import numpy as np
from enum import Enum
import threading
from queue import Queue
import subprocess

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of timeline events"""
    MOTION = "motion"
    FACE_DETECTED = "face_detected"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    CAMERA_ONLINE = "camera_online"
    CAMERA_OFFLINE = "camera_offline"
    AUDIO_DETECTED = "audio_detected"
    OBJECT_DETECTED = "object_detected"
    MANUAL_TRIGGER = "manual_trigger"


@dataclass
class TimelineEvent:
    """Timeline event entry"""
    id: str
    camera_id: str
    event_type: EventType
    timestamp: datetime
    duration: Optional[float] = None  # seconds
    data: Dict = field(default_factory=dict)
    thumbnail_path: Optional[str] = None
    video_path: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'camera_id': self.camera_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'duration': self.duration,
            'data': self.data,
            'thumbnail_path': self.thumbnail_path,
            'video_path': self.video_path
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'TimelineEvent':
        """Create from dictionary"""
        return TimelineEvent(
            id=data['id'],
            camera_id=data['camera_id'],
            event_type=EventType(data['event_type']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            duration=data.get('duration'),
            data=data.get('data', {}),
            thumbnail_path=data.get('thumbnail_path'),
            video_path=data.get('video_path')
        )


class VideoPlayer:
    """
    Video playback engine
    
    Handles video file playback with seeking, speed control, and frame extraction
    """
    
    def __init__(self, video_path: str):
        """
        Initialize video player
        
        Args:
            video_path: Path to video file
        """
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        # Video properties
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration = self.frame_count / self.fps if self.fps > 0 else 0
        
        # Playback state
        self.current_frame = 0
        self.playing = False
        self.playback_speed = 1.0
        
        logger.info(f"Video loaded: {self.frame_count} frames, {self.fps} FPS, {self.duration:.2f}s")
    
    def get_frame(self, frame_number: Optional[int] = None) -> Optional[np.ndarray]:
        """
        Get specific frame or current frame
        
        Args:
            frame_number: Frame number to retrieve (None for current)
            
        Returns:
            Frame as numpy array or None
        """
        if frame_number is not None:
            self.seek_frame(frame_number)
        
        ret, frame = self.cap.read()
        
        if ret:
            self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            return frame
        
        return None
    
    def seek_frame(self, frame_number: int):
        """Seek to specific frame"""
        frame_number = max(0, min(frame_number, self.frame_count - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        self.current_frame = frame_number
    
    def seek_time(self, seconds: float):
        """Seek to specific time"""
        frame_number = int(seconds * self.fps)
        self.seek_frame(frame_number)
    
    def get_timestamp(self) -> float:
        """Get current timestamp in seconds"""
        return self.current_frame / self.fps if self.fps > 0 else 0
    
    def next_frame(self) -> Optional[np.ndarray]:
        """Get next frame"""
        return self.get_frame()
    
    def previous_frame(self) -> Optional[np.ndarray]:
        """Get previous frame"""
        target_frame = max(0, self.current_frame - 2)
        return self.get_frame(target_frame)
    
    def set_playback_speed(self, speed: float):
        """Set playback speed multiplier"""
        self.playback_speed = max(0.125, min(4.0, speed))
    
    def extract_clip(
        self,
        output_path: str,
        start_time: float,
        end_time: float
    ) -> bool:
        """
        Extract video clip
        
        Args:
            output_path: Output video path
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            True if successful
        """
        try:
            # Use FFmpeg for efficient clip extraction
            cmd = [
                'ffmpeg',
                '-i', self.video_path,
                '-ss', str(start_time),
                '-to', str(end_time),
                '-c', 'copy',
                '-y',
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Extracted clip: {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error extracting clip: {e}")
            return False
    
    def extract_thumbnail(
        self,
        output_path: str,
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Extract thumbnail from video
        
        Args:
            output_path: Output image path
            timestamp: Time in seconds (None for current position)
            
        Returns:
            True if successful
        """
        try:
            if timestamp is not None:
                self.seek_time(timestamp)
            
            frame = self.get_frame()
            
            if frame is not None:
                cv2.imwrite(output_path, frame)
                logger.info(f"Thumbnail saved: {output_path}")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error extracting thumbnail: {e}")
            return False
    
    def get_frames_generator(
        self,
        start_frame: int = 0,
        end_frame: Optional[int] = None
    ) -> Generator[Tuple[int, np.ndarray], None, None]:
        """
        Generator for frame iteration
        
        Args:
            start_frame: Starting frame number
            end_frame: Ending frame number (None for end)
            
        Yields:
            Tuple of (frame_number, frame)
        """
        self.seek_frame(start_frame)
        end = end_frame or self.frame_count
        
        for frame_num in range(start_frame, end):
            frame = self.get_frame()
            
            if frame is None:
                break
            
            yield (frame_num, frame)
    
    def close(self):
        """Release video resources"""
        if self.cap:
            self.cap.release()
            self.cap = None


class TimelineDatabase:
    """
    Timeline event database
    
    Stores and queries timeline events with efficient date-based indexing
    """
    
    def __init__(self, database_path: str = "data/timeline/events.json"):
        """Initialize timeline database"""
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.events: List[TimelineEvent] = []
        self._load_database()
        
        # Index for fast lookups
        self._index_by_camera: Dict[str, List[TimelineEvent]] = {}
        self._index_by_date: Dict[str, List[TimelineEvent]] = {}
        self._rebuild_indices()
        
        logger.info(f"Timeline database loaded with {len(self.events)} events")
    
    def _load_database(self):
        """Load events from disk"""
        try:
            if self.database_path.exists():
                with open(self.database_path, 'r') as f:
                    data = json.load(f)
                    self.events = [
                        TimelineEvent.from_dict(event_data)
                        for event_data in data.get('events', [])
                    ]
        except Exception as e:
            logger.error(f"Error loading timeline database: {e}")
    
    def _save_database(self):
        """Save events to disk"""
        try:
            data = {
                'events': [event.to_dict() for event in self.events],
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self.database_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving timeline database: {e}")
    
    def _rebuild_indices(self):
        """Rebuild search indices"""
        self._index_by_camera.clear()
        self._index_by_date.clear()
        
        for event in self.events:
            # Camera index
            if event.camera_id not in self._index_by_camera:
                self._index_by_camera[event.camera_id] = []
            self._index_by_camera[event.camera_id].append(event)
            
            # Date index
            date_key = event.timestamp.strftime('%Y-%m-%d')
            if date_key not in self._index_by_date:
                self._index_by_date[date_key] = []
            self._index_by_date[date_key].append(event)
    
    def add_event(self, event: TimelineEvent):
        """Add event to timeline"""
        self.events.append(event)
        
        # Update indices
        if event.camera_id not in self._index_by_camera:
            self._index_by_camera[event.camera_id] = []
        self._index_by_camera[event.camera_id].append(event)
        
        date_key = event.timestamp.strftime('%Y-%m-%d')
        if date_key not in self._index_by_date:
            self._index_by_date[date_key] = []
        self._index_by_date[date_key].append(event)
        
        self._save_database()
    
    def query_events(
        self,
        camera_id: Optional[str] = None,
        event_types: Optional[List[EventType]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[TimelineEvent]:
        """
        Query events with filters
        
        Args:
            camera_id: Filter by camera
            event_types: Filter by event types
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of results
            
        Returns:
            List of matching events
        """
        # Start with all events or camera-filtered events
        if camera_id:
            results = self._index_by_camera.get(camera_id, []).copy()
        else:
            results = self.events.copy()
        
        # Filter by event type
        if event_types:
            results = [e for e in results if e.event_type in event_types]
        
        # Filter by time range
        if start_time:
            results = [e for e in results if e.timestamp >= start_time]
        if end_time:
            results = [e for e in results if e.timestamp <= end_time]
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda e: e.timestamp, reverse=True)
        
        # Apply limit
        if limit:
            results = results[:limit]
        
        return results
    
    def get_events_by_date(self, date: datetime) -> List[TimelineEvent]:
        """Get all events for a specific date"""
        date_key = date.strftime('%Y-%m-%d')
        return self._index_by_date.get(date_key, [])
    
    def get_event_dates(self) -> List[datetime]:
        """Get list of all dates with events"""
        return [
            datetime.strptime(date_key, '%Y-%m-%d')
            for date_key in sorted(self._index_by_date.keys(), reverse=True)
        ]
    
    def delete_old_events(self, days: int = 30) -> int:
        """
        Delete events older than specified days
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of events deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        original_count = len(self.events)
        self.events = [e for e in self.events if e.timestamp >= cutoff_date]
        deleted_count = original_count - len(self.events)
        
        if deleted_count > 0:
            self._rebuild_indices()
            self._save_database()
            logger.info(f"Deleted {deleted_count} old events")
        
        return deleted_count


class PlaybackManager:
    """
    Manages video playback sessions
    
    Handles multiple concurrent playback sessions and clip exports
    """
    
    def __init__(
        self,
        recordings_dir: str = "data/recordings",
        thumbnails_dir: str = "data/thumbnails",
        clips_dir: str = "data/clips"
    ):
        """Initialize playback manager"""
        self.recordings_dir = Path(recordings_dir)
        self.thumbnails_dir = Path(thumbnails_dir)
        self.clips_dir = Path(clips_dir)
        
        # Create directories
        for directory in [self.recordings_dir, self.thumbnails_dir, self.clips_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Active players
        self.players: Dict[str, VideoPlayer] = {}
        
        logger.info("Playback manager initialized")
    
    def create_player(self, session_id: str, video_path: str) -> Optional[VideoPlayer]:
        """
        Create video player
        
        Args:
            session_id: Unique session identifier
            video_path: Path to video file
            
        Returns:
            VideoPlayer instance or None
        """
        try:
            player = VideoPlayer(video_path)
            self.players[session_id] = player
            return player
        except Exception as e:
            logger.error(f"Error creating player: {e}")
            return None
    
    def get_player(self, session_id: str) -> Optional[VideoPlayer]:
        """Get existing player"""
        return self.players.get(session_id)
    
    def close_player(self, session_id: str):
        """Close player session"""
        if session_id in self.players:
            self.players[session_id].close()
            del self.players[session_id]
    
    def generate_thumbnail(
        self,
        video_path: str,
        timestamp: float = 0.0
    ) -> Optional[str]:
        """
        Generate thumbnail for video
        
        Args:
            video_path: Path to video file
            timestamp: Time position for thumbnail
            
        Returns:
            Path to thumbnail or None
        """
        try:
            # Create unique thumbnail name
            video_name = Path(video_path).stem
            thumbnail_name = f"{video_name}_{int(timestamp)}.jpg"
            thumbnail_path = self.thumbnails_dir / thumbnail_name
            
            # Check if already exists
            if thumbnail_path.exists():
                return str(thumbnail_path)
            
            # Generate thumbnail
            player = VideoPlayer(video_path)
            success = player.extract_thumbnail(str(thumbnail_path), timestamp)
            player.close()
            
            if success:
                return str(thumbnail_path)
            
            return None
        
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return None
    
    def export_clip(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Export video clip
        
        Args:
            video_path: Source video path
            start_time: Start time in seconds
            end_time: End time in seconds
            output_name: Custom output name
            
        Returns:
            Path to exported clip or None
        """
        try:
            # Generate output path
            if output_name:
                clip_path = self.clips_dir / output_name
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                clip_path = self.clips_dir / f"clip_{timestamp}.mp4"
            
            # Extract clip
            player = VideoPlayer(video_path)
            success = player.extract_clip(str(clip_path), start_time, end_time)
            player.close()
            
            if success:
                return str(clip_path)
            
            return None
        
        except Exception as e:
            logger.error(f"Error exporting clip: {e}")
            return None
    
    def get_recordings(
        self,
        camera_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        List available recordings
        
        Args:
            camera_id: Filter by camera
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of recording metadata
        """
        recordings = []
        
        for video_file in self.recordings_dir.glob("*.mp4"):
            # Parse filename for metadata
            # Expected format: camera_id_YYYYMMDD_HHMMSS.mp4
            parts = video_file.stem.split('_')
            
            if len(parts) >= 3:
                file_camera_id = parts[0]
                
                # Filter by camera
                if camera_id and file_camera_id != camera_id:
                    continue
                
                try:
                    # Parse date
                    date_str = f"{parts[1]}_{parts[2]}"
                    file_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                    
                    # Filter by date range
                    if start_date and file_date < start_date:
                        continue
                    if end_date and file_date > end_date:
                        continue
                    
                    # Get video info
                    player = VideoPlayer(str(video_file))
                    
                    recordings.append({
                        'path': str(video_file),
                        'camera_id': file_camera_id,
                        'timestamp': file_date.isoformat(),
                        'duration': player.duration,
                        'size': video_file.stat().st_size,
                        'resolution': f"{player.width}x{player.height}",
                        'fps': player.fps
                    })
                    
                    player.close()
                
                except Exception as e:
                    logger.error(f"Error processing recording {video_file}: {e}")
        
        # Sort by timestamp (newest first)
        recordings.sort(key=lambda r: r['timestamp'], reverse=True)
        
        return recordings


# Example FastAPI integration
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()
timeline_db = TimelineDatabase()
playback_mgr = PlaybackManager()


class EventQuery(BaseModel):
    camera_id: Optional[str] = None
    event_types: Optional[List[str]] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: Optional[int] = 100


@app.get("/api/timeline/events")
async def get_timeline_events(
    camera_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
):
    """Get timeline events"""
    start_time = datetime.fromisoformat(start_date) if start_date else None
    end_time = datetime.fromisoformat(end_date) if end_date else None
    
    events = timeline_db.query_events(
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )
    
    return {'events': [e.to_dict() for e in events]}


@app.get("/api/timeline/dates")
async def get_event_dates():
    """Get list of dates with events"""
    dates = timeline_db.get_event_dates()
    return {'dates': [d.strftime('%Y-%m-%d') for d in dates]}


@app.get("/api/playback/recordings")
async def list_recordings(
    camera_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """List available recordings"""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    
    recordings = playback_mgr.get_recordings(
        camera_id=camera_id,
        start_date=start,
        end_date=end
    )
    
    return {'recordings': recordings}


@app.post("/api/playback/export")
async def export_clip(
    video_path: str,
    start_time: float,
    end_time: float,
    output_name: Optional[str] = None
):
    """Export video clip"""
    clip_path = playback_mgr.export_clip(
        video_path,
        start_time,
        end_time,
        output_name
    )
    
    if clip_path:
        return {'clip_path': clip_path}
    
    raise HTTPException(status_code=500, detail="Failed to export clip")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)