"""
OpenEye WebSocket API Routes
Copyright (c) 2025 M1K31

WebSocket endpoints for real-time statistics and event streaming.
"""

import json
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
# PyJWT rather than python-jose (audit P2-2). python-jose verified every token
# in this application and is effectively unmaintained, with published advisories
# for algorithm confusion (CVE-2024-33663) and a decompression denial of service
# (CVE-2024-33664). PyJWT was already a declared dependency with no importers.
#
# PyJWTError is aliased to JWTError so existing `except JWTError:` clauses keep
# working and the change stays confined to the import. The call surface is
# identical: encode(payload, key, algorithm=...) and
# decode(token, key, algorithms=[...]).
import jwt
from jwt import PyJWTError as JWTError

from backend.core.websocket_manager import ws_manager
from backend.core.auth import get_current_active_user, SECRET_KEY, ALGORITHM
from backend.database.session import get_db, SessionLocal
from backend.database.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websockets"])


def parse_client_message(data: str) -> dict:
    """
    Parse an inbound WebSocket frame.

    Frames arrive from the network and are never trusted as code. Anything
    that is not a well-formed JSON object is treated as plain text.
    """
    if data.startswith("{"):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass
    return {"type": "text", "content": data}


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
) -> Optional[User]:
    """
    Authenticate WebSocket connection using JWT token.

    Args:
        websocket: FastAPI WebSocket instance
        token: JWT token from query parameter

    Returns:
        User object if authenticated, None otherwise
    """
    if not token:
        logger.warning("WebSocket connection attempted without token")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required"
        )
        return None

    try:
        # FIXED: Use context manager to prevent session leak (v3.6.0.1)
        from backend.database.utils import get_db_context
        with get_db_context() as db:
            # Verify token and get user
            user = verify_token(token, db)
            if not user:
                raise Exception("Invalid token")
            return user
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
        )
        return None


@router.websocket("/statistics")
async def websocket_statistics_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
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
    user = await authenticate_websocket(websocket, token)
    if not user:
        return

    # Generate unique connection ID
    connection_id = str(uuid.uuid4())

    # Attempt to connect
    connected = await ws_manager.connect(
        websocket=websocket,
        user_id=user.id,
        username=user.username,
        connection_id=connection_id,
    )

    if not connected:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Rate limit exceeded"
        )
        return

    try:
        # Send welcome message
        await ws_manager.send_personal_message(
            {
                "type": "connection_status",
                "status": "connected",
                "connection_id": connection_id,
                "user": {"id": user.id, "username": user.username},
                "message": "WebSocket connection established successfully",
            },
            connection_id,
        )

        # Keep connection alive and handle incoming messages.
        # consecutive_errors guards against a dead socket: see the handler below.
        consecutive_errors = 0
        while True:
            try:
                # Receive message from client (with timeout for keepalive)
                data = await websocket.receive_text()

                # Parse message
                message = parse_client_message(data)

                # Handle different message types
                message_type = message.get("type", "unknown")

                if message_type == "ping":
                    # Respond to ping with pong
                    await ws_manager.send_personal_message(
                        {"type": "pong", "timestamp": message.get("timestamp")},
                        connection_id,
                    )
                    logger.debug(f"Ping-pong from {user.username}")

                elif message_type == "subscribe":
                    # Handle subscription (future feature)
                    event_types = message.get("event_types", [])
                    logger.info(f"User {user.username} subscribed to: {event_types}")
                    await ws_manager.send_personal_message(
                        {"type": "subscription_confirmed", "event_types": event_types},
                        connection_id,
                    )

                elif message_type == "unsubscribe":
                    # Handle unsubscription (future feature)
                    event_types = message.get("event_types", [])
                    logger.info(f"User {user.username} unsubscribed from: {event_types}")
                    await ws_manager.send_personal_message(
                        {
                            "type": "unsubscription_confirmed",
                            "event_types": event_types,
                        },
                        connection_id,
                    )

                else:
                    logger.debug(f"Unknown message type from {user.username}: {message_type}")

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnect signal from {user.username}")
                break
            except Exception as e:
                # Continuing is right for a bad MESSAGE, but fatal for a dead SOCKET:
                # once the peer is gone (or the socket was never accepted),
                # receive_text() raises the same error immediately on every pass, so
                # "continue listening" became a tight infinite loop. Observed in the
                # wild: ~24 million identical log lines, the asyncio event loop
                # starved, and every HTTP request timing out while the port stayed
                # open. Break on the errors that mean the connection is unusable, and
                # cap consecutive failures as a backstop for anything unforeseen.
                msg = str(e).lower()
                if (
                    isinstance(e, RuntimeError)
                    or "not connected" in msg
                    or "accept" in msg
                    or "close" in msg
                    or "disconnect" in msg
                ):
                    logger.info(
                        f"WebSocket for {user.username} is no longer usable ({e}); "
                        "closing listener."
                    )
                    break

                consecutive_errors += 1
                logger.error(
                    f"Error handling WebSocket message from {user.username}: {e} "
                    f"(consecutive={consecutive_errors})"
                )
                if consecutive_errors >= 5:
                    logger.error(
                        f"Too many consecutive WebSocket errors for {user.username}; "
                        "closing listener to avoid a hot loop."
                    )
                    break
            else:
                consecutive_errors = 0

    except Exception as e:
        logger.error(f"WebSocket connection error for {user.username}: {e}")
    finally:
        # Clean up connection
        await ws_manager.disconnect(connection_id)
        logger.info(f"WebSocket cleanup completed for {user.username}")


@router.get("/status")
async def websocket_status(
        current_user: User = Depends(get_current_active_user)):
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
        "user_connections": ws_manager.get_user_connection_count(
            current_user.id),
    }
