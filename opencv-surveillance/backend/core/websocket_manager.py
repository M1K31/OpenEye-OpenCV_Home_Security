"""
OpenEye WebSocket Connection Manager
Copyright (c) 2025 M1K31

Manages WebSocket connections for real-time statistics updates.
Provides connection lifecycle management, authentication, and event broadcasting.
"""

import asyncio
import logging
from typing import Dict, Set, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import json

logger = logging.getLogger(__name__)


class WebSocketConnection:
    """Represents a single WebSocket connection with metadata."""
    
    def __init__(self, websocket: WebSocket, user_id: int, username: str):
        self.websocket = websocket
        self.user_id = user_id
        self.username = username
        self.connected_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.message_count = 0
        
    async def send_json(self, data: dict):
        """Send JSON data through the WebSocket."""
        try:
            await self.websocket.send_json(data)
            self.last_activity = datetime.utcnow()
            self.message_count += 1
        except Exception as e:
            logger.error(f"Error sending message to user {self.username}: {e}")
            raise


class WebSocketConnectionManager:
    """
    Manages all active WebSocket connections.
    
    Features:
    - Connection lifecycle management (connect, disconnect, cleanup)
    - User-based connection tracking
    - Broadcast to all connections or specific users
    - Rate limiting (max connections per user)
    - Automatic cleanup of stale connections
    """
    
    def __init__(self, max_connections_per_user: int = 5):
        self.active_connections: Dict[str, WebSocketConnection] = {}
        self.user_connections: Dict[int, Set[str]] = {}
        self.max_connections_per_user = max_connections_per_user
        self._lock = asyncio.Lock()
        
    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        username: str,
        connection_id: str
    ) -> bool:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: FastAPI WebSocket instance
            user_id: Database user ID
            username: Username for logging
            connection_id: Unique connection identifier
            
        Returns:
            bool: True if connection accepted, False if rate limited
        """
        async with self._lock:
            # Check rate limiting
            user_connection_count = len(self.user_connections.get(user_id, set()))
            if user_connection_count >= self.max_connections_per_user:
                logger.warning(
                    f"User {username} (ID: {user_id}) exceeded max connections "
                    f"({self.max_connections_per_user})"
                )
                return False
            
            # Accept the connection
            await websocket.accept()
            
            # Create connection object
            connection = WebSocketConnection(websocket, user_id, username)
            self.active_connections[connection_id] = connection
            
            # Track by user
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
            
            logger.info(
                f"WebSocket connected: {username} (ID: {user_id}, "
                f"Connection: {connection_id}, Total: {len(self.active_connections)})"
            )
            return True
    
    async def disconnect(self, connection_id: str):
        """
        Remove a WebSocket connection.
        
        Args:
            connection_id: Unique connection identifier
        """
        async with self._lock:
            if connection_id in self.active_connections:
                connection = self.active_connections[connection_id]
                user_id = connection.user_id
                username = connection.username
                
                # Remove from tracking
                del self.active_connections[connection_id]
                if user_id in self.user_connections:
                    self.user_connections[user_id].discard(connection_id)
                    if not self.user_connections[user_id]:
                        del self.user_connections[user_id]
                
                logger.info(
                    f"WebSocket disconnected: {username} (ID: {user_id}, "
                    f"Connection: {connection_id}, Total: {len(self.active_connections)})"
                )
    
    async def send_personal_message(self, message: dict, connection_id: str):
        """
        Send a message to a specific connection.
        
        Args:
            message: Dictionary to send as JSON
            connection_id: Target connection identifier
        """
        if connection_id in self.active_connections:
            connection = self.active_connections[connection_id]
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send personal message: {e}")
                await self.disconnect(connection_id)
    
    async def broadcast(self, message: dict, exclude_connection_id: Optional[str] = None):
        """
        Broadcast a message to all active connections.
        
        Args:
            message: Dictionary to send as JSON
            exclude_connection_id: Optional connection to exclude from broadcast
        """
        disconnected = []
        
        for connection_id, connection in self.active_connections.items():
            if connection_id == exclude_connection_id:
                continue
                
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(
                    f"Failed to broadcast to {connection.username}: {e}"
                )
                disconnected.append(connection_id)
        
        # Clean up failed connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    async def broadcast_to_user(self, message: dict, user_id: int):
        """
        Broadcast a message to all connections for a specific user.
        
        Args:
            message: Dictionary to send as JSON
            user_id: Target user ID
        """
        if user_id not in self.user_connections:
            return
        
        disconnected = []
        
        for connection_id in self.user_connections[user_id]:
            if connection_id in self.active_connections:
                connection = self.active_connections[connection_id]
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(
                        f"Failed to send to {connection.username}: {e}"
                    )
                    disconnected.append(connection_id)
        
        # Clean up failed connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.active_connections)
    
    def get_user_connection_count(self, user_id: int) -> int:
        """Get number of active connections for a specific user."""
        return len(self.user_connections.get(user_id, set()))
    
    def get_statistics(self) -> dict:
        """Get connection statistics."""
        return {
            "total_connections": len(self.active_connections),
            "total_users": len(self.user_connections),
            "connections_by_user": {
                user_id: len(conn_ids)
                for user_id, conn_ids in self.user_connections.items()
            }
        }


# Global singleton instance
ws_manager = WebSocketConnectionManager(max_connections_per_user=5)


async def broadcast_statistics_update(statistics: dict):
    """
    Broadcast statistics update to all connected clients.
    
    Args:
        statistics: Statistics dictionary to broadcast
    """
    message = {
        "type": "statistics_update",
        "timestamp": datetime.utcnow().isoformat(),
        "data": statistics
    }
    await ws_manager.broadcast(message)


async def broadcast_camera_event(camera_id: int, event_type: str, event_data: dict):
    """
    Broadcast camera event to all connected clients.
    
    Args:
        camera_id: Camera identifier
        event_type: Event type (motion_detected, recording_started, etc.)
        event_data: Event details
    """
    message = {
        "type": "camera_event",
        "timestamp": datetime.utcnow().isoformat(),
        "camera_id": camera_id,
        "event_type": event_type,
        "data": event_data
    }
    await ws_manager.broadcast(message)


async def broadcast_alert(alert_type: str, alert_data: dict):
    """
    Broadcast system alert to all connected clients.
    
    Args:
        alert_type: Alert type (error, warning, info)
        alert_data: Alert details
    """
    message = {
        "type": "alert",
        "timestamp": datetime.utcnow().isoformat(),
        "alert_type": alert_type,
        "data": alert_data
    }
    await ws_manager.broadcast(message)
