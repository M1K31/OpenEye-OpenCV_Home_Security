"""
OpenEye WebSocket API Routes
Copyright (c) 2025 M1K31

WebSocket endpoints for real-time statistics and event streaming.
"""

import uuid
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from backend.core.websocket_manager import ws_manager
from backend.core.auth import get_current_active_user, SECRET_KEY, ALGORITHM
from backend.database.session import get_db
from backend.database.models import User
from backend.api.schemas import user as user_schema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websockets"])


def verify_token(token: str, db: Session) -> Optional[User]:
    """
    Verify JWT token and return user.
    
    Args:
        token: JWT token string
        db: Database session
        
    Returns:
        User object if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        
        # Get user from database
        user = db.query(User).filter(User.username == username).first()
        return user
    except JWTError:
        return None


async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Authenticate WebSocket connection using JWT token.
    
    Args:
        websocket: FastAPI WebSocket instance
        token: JWT token from query parameter
        db: Database session
        
    Returns:
        User object if authenticated, None otherwise
    """
    if not token:
        logger.warning("WebSocket connection attempted without token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return None
    
    try:
        # Verify token and get user
        user = verify_token(token, db)
        if not user:
            raise Exception("Invalid token")
        return user
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return None


@router.websocket("/statistics")
async def websocket_statistics_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time statistics streaming.
    
    Query Parameters:
        token: JWT authentication token
        
    Message Types Sent to Client:
        - statistics_update: Periodic statistics updates
        - camera_event: Camera-related events (motion, recording, etc.)
        - alert: System alerts and notifications
        - connection_status: Connection health check
        
    Message Types Received from Client:
        - ping: Keep-alive ping
        - subscribe: Subscribe to specific event types
        - unsubscribe: Unsubscribe from event types
        
    Example Connection (JavaScript):
        const token = localStorage.getItem('token');
        const ws = new WebSocket(`ws://localhost:8000/api/ws/statistics?token=${token}`);
        
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'statistics_update') {
                updateDashboard(message.data);
            }
        };
    """
    # Authenticate the connection
    user = await authenticate_websocket(websocket, token, db)
    if not user:
        return
    
    # Generate unique connection ID
    connection_id = str(uuid.uuid4())
    
    # Attempt to connect
    connected = await ws_manager.connect(
        websocket=websocket,
        user_id=user.id,
        username=user.username,
        connection_id=connection_id
    )
    
    if not connected:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Rate limit exceeded"
        )
        return
    
    try:
        # Send welcome message
        await ws_manager.send_personal_message(
            {
                "type": "connection_status",
                "status": "connected",
                "connection_id": connection_id,
                "user": {
                    "id": user.id,
                    "username": user.username
                },
                "message": "WebSocket connection established successfully"
            },
            connection_id
        )
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive message from client (with timeout for keepalive)
                data = await websocket.receive_text()
                
                # Parse message
                try:
                    message = eval(data) if data.startswith('{') else {"type": "text", "content": data}
                except:
                    message = {"type": "text", "content": data}
                
                # Handle different message types
                message_type = message.get("type", "unknown")
                
                if message_type == "ping":
                    # Respond to ping with pong
                    await ws_manager.send_personal_message(
                        {"type": "pong", "timestamp": message.get("timestamp")},
                        connection_id
                    )
                    logger.debug(f"Ping-pong from {user.username}")
                
                elif message_type == "subscribe":
                    # Handle subscription (future feature)
                    event_types = message.get("event_types", [])
                    logger.info(f"User {user.username} subscribed to: {event_types}")
                    await ws_manager.send_personal_message(
                        {
                            "type": "subscription_confirmed",
                            "event_types": event_types
                        },
                        connection_id
                    )
                
                elif message_type == "unsubscribe":
                    # Handle unsubscription (future feature)
                    event_types = message.get("event_types", [])
                    logger.info(f"User {user.username} unsubscribed from: {event_types}")
                    await ws_manager.send_personal_message(
                        {
                            "type": "unsubscription_confirmed",
                            "event_types": event_types
                        },
                        connection_id
                    )
                
                else:
                    logger.debug(f"Unknown message type from {user.username}: {message_type}")
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnect signal from {user.username}")
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message from {user.username}: {e}")
                # Don't break on message handling errors, continue listening
                
    except Exception as e:
        logger.error(f"WebSocket connection error for {user.username}: {e}")
    finally:
        # Clean up connection
        await ws_manager.disconnect(connection_id)
        logger.info(f"WebSocket cleanup completed for {user.username}")


@router.get("/status")
async def websocket_status(current_user: User = Depends(get_current_active_user)):
    """
    Get WebSocket connection statistics.
    
    Returns:
        Connection statistics including total connections, users, and per-user counts
        
    Note: Requires authentication via bearer token in Authorization header
    """
    stats = ws_manager.get_statistics()
    return {
        "status": "operational",
        "statistics": stats,
        "user_connections": ws_manager.get_user_connection_count(current_user.id)
    }
