"""
OpenEye Statistics Broadcasting Service
Copyright (c) 2025 M1K31

Background service that periodically broadcasts statistics via WebSocket.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from backend.core.websocket_manager import broadcast_statistics_update
from backend.core.camera_manager import manager as camera_manager
from backend.core.face_recognition import get_face_manager

logger = logging.getLogger(__name__)


class StatisticsBroadcaster:
    """
    Background service that collects and broadcasts statistics.
    """
    
    def __init__(self, interval: int = 5):
        """
        Initialize the statistics broadcaster.
        
        Args:
            interval: Broadcast interval in seconds (default: 5)
        """
        self.interval = interval
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the broadcasting service."""
        if self.is_running:
            logger.warning("Statistics broadcaster already running")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._broadcast_loop())
        logger.info(f"Statistics broadcaster started (interval: {self.interval}s)")
        
    async def stop(self):
        """Stop the broadcasting service."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Statistics broadcaster stopped")
        
    async def _broadcast_loop(self):
        """Main broadcast loop."""
        while self.is_running:
            try:
                # Collect statistics
                statistics = await self._collect_statistics()
                
                # Broadcast to all connected WebSocket clients
                await broadcast_statistics_update(statistics)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error broadcasting statistics: {e}")
            
            # Wait for next interval
            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
    
    async def _collect_statistics(self) -> dict:
        """
        Collect statistics from all sources.
        
        Returns:
            Dictionary containing all statistics
        """
        try:
            # Get face recognition statistics
            face_manager = get_face_manager()
            face_stats = face_manager.get_statistics()
            
            # Get camera statistics
            camera_stats = {
                "total_cameras": len(camera_manager.cameras),
                "active_cameras": sum(1 for cam in camera_manager.cameras.values() if cam.is_running),
                "recording_cameras": sum(1 for cam in camera_manager.cameras.values() 
                                        if hasattr(cam, 'recorder') and cam.recorder.is_recording)
            }
            
            # Combine all statistics
            return {
                "face_recognition": {
                    "total_people": face_stats.get("total_people", 0),
                    "recognitions_today": face_stats.get("recognitions_today", 0),
                    "last_recognition": face_stats.get("last_recognition"),
                    "unknown_faces_today": face_stats.get("unknown_faces_today", 0)
                },
                "cameras": camera_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error collecting statistics: {e}")
            return {
                "error": "Failed to collect statistics",
                "timestamp": datetime.utcnow().isoformat()
            }


# Global singleton instance
_broadcaster: Optional[StatisticsBroadcaster] = None


def get_broadcaster() -> StatisticsBroadcaster:
    """Get the global statistics broadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = StatisticsBroadcaster(interval=5)
    return _broadcaster
