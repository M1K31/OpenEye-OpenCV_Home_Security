# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Ecosystem Integration API Routes
Enables integration with MagicMirror, mobile apps, and other ecosystem participants
"""

from ipaddress import ip_address as parse_ip, ip_network
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import secrets
import hashlib
import json
import logging
import os
import asyncio
import httpx

from ecosystem_auth.tokens import sign_payload
from ecosystem_auth.middleware import require_ecosystem_auth

from backend.database.session import get_db, engine
from backend.database import models
from backend.api.schemas import ecosystem as eco_schema
from backend.api.schemas import user as user_schema
from backend.core.paths import paths

router = APIRouter()
logger = logging.getLogger(__name__)

# Track startup time for uptime calculation
_startup_time = datetime.utcnow()

# Active WebSocket connections for ecosystem events
_ecosystem_websockets: List[WebSocket] = []


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_uptime_seconds() -> int:
    """Get seconds since server startup"""
    return int((datetime.utcnow() - _startup_time).total_seconds())


def generate_ecosystem_token() -> str:
    """Generate a secure ecosystem token"""
    return secrets.token_hex(32)


def generate_dedupe_key(notification: dict) -> str:
    """Generate deduplication key from notification content"""
    content = f"{notification.get('type')}:{notification.get('source')}:{notification.get('title')}"
    return hashlib.sha256(content.encode()).hexdigest()


_BLOCKED_NETWORKS = [
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("169.254.0.0/16"),
    ip_network("127.0.0.0/8"),
    ip_network("0.0.0.0/8"),
]


def _is_safe_url(url: str) -> bool:
    """Return False if *url* resolves to a private/loopback address (SSRF guard)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        addr = parse_ip(host)
        return not any(addr in net for net in _BLOCKED_NETWORKS)
    except (ValueError, TypeError):
        # If hostname is not an IP literal, allow it (DNS resolution would
        # need async check; this covers the most common SSRF vectors).
        return True


async def broadcast_to_ecosystem(event: dict):
    """Broadcast event to all connected ecosystem WebSockets"""
    disconnected = []
    for ws in _ecosystem_websockets:
        try:
            await ws.send_json(event)
        except Exception:
            disconnected.append(ws)
    
    # Clean up disconnected sockets
    for ws in disconnected:
        if ws in _ecosystem_websockets:
            _ecosystem_websockets.remove(ws)


async def send_webhook(connection: models.EcosystemConnection, event: dict, db: Session):
    """Send event to companion app via webhook"""
    if not connection.webhook_url:
        return
    
    try:
        # Sign the payload
        signature = sign_payload(event, connection.local_token)
        event["signature"] = signature

        headers = {"Content-Type": "application/json"}
        if connection.remote_token:
            headers["Authorization"] = f"Bearer {connection.remote_token}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(connection.webhook_url, json=event, headers=headers)
            if resp.status_code == 200:
                logger.debug(f"Webhook sent to {connection.app_name}")
            else:
                logger.warning(f"Webhook to {connection.app_name} returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Failed to send webhook to {connection.app_name}: {e}")


# ============================================================================
# ECOSYSTEM CONNECTION
# ============================================================================


@router.post("/ecosystem/connect", response_model=eco_schema.EcosystemConnectResponse)
async def connect_ecosystem_app(
    request: eco_schema.EcosystemConnectRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Connect a companion app (MagicMirror, mobile app, etc.) to OpenEye.
    
    This establishes a secure connection with token exchange for authenticated communication.
    The companion app provides its callback URL and token, and OpenEye returns a token for the
    companion to use when calling OpenEye APIs.
    
    v3.11.1: Multi-device support
    - device_id: Unique identifier for this device (auto-generated if not provided)
    - device_name: Human-friendly name (e.g., "Kitchen Mirror")
    - location: Where the device is located (kitchen, living_room, etc.)
    - associated_users: Users associated with this device (for routing notifications)
    - subscribed_cameras: Cameras this device wants to receive events from
    - notification_preferences: Per-device notification settings
    
    v3.11.2: Enhanced security
    - Rate limiting on connection attempts
    - IP tracking and validation
    - Device fingerprinting
    """
    from backend.core.ecosystem_security import (
        check_rate_limit, record_auth_attempt, 
        generate_device_fingerprint, hash_token
    )
    
    # Get client IP
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    # Check rate limiting
    is_allowed, wait_time = check_rate_limit(client_ip)
    if not is_allowed:
        record_auth_attempt(client_ip, success=False)
        raise HTTPException(
            status_code=429,
            detail=f"Too many connection attempts. Please wait {wait_time} seconds.",
            headers={"Retry-After": str(wait_time)}
        )
    
    # SSRF guard: reject private/loopback callback hosts (C-3 fix)
    if request.host and not _is_safe_url(request.host):
        raise HTTPException(
            status_code=400,
            detail="Callback host resolves to a private or loopback address",
        )

    device_name = request.device_name or f"{request.app} at {request.host}"
    logger.info(f"Ecosystem connect request from {device_name} ({request.app} v{request.version}) IP: {client_ip}")
    
    # Generate secure token for this connection
    ecosystem_token = generate_ecosystem_token()
    
    # Generate device_id if not provided
    device_id = request.device_id
    if not device_id:
        import uuid
        device_id = f"{request.app}_{uuid.uuid4().hex[:8]}"
    
    # Get server host for webhook URL - dynamically determine from request
    from backend.core.config import resolve_service_port
    openeye_port = str(resolve_service_port())
    server_host = os.getenv("OPENEYE_HOST", f"http://{http_request.headers.get('host', f'{http_request.client.host}:{openeye_port}')}")
    
    # Check if this device is already connected (by device_id or app+host)
    existing = db.query(models.EcosystemConnection).filter(
        (models.EcosystemConnection.device_id == device_id) |
        ((models.EcosystemConnection.app_name == request.app) & 
         (models.EcosystemConnection.host == request.host))
    ).first()
    
    if existing:
        # Update existing connection
        existing.app_version = request.version
        existing.remote_token = request.token
        existing.local_token = ecosystem_token
        existing.capabilities = json.dumps(request.capabilities)
        existing.last_seen = datetime.utcnow()
        existing.is_active = True
        existing.ip_address = http_request.client.host if http_request.client else None
        existing.device_id = device_id
        existing.device_name = request.device_name or existing.device_name
        existing.location = request.location or existing.location
        
        # Update subscriptions if provided
        if request.associated_users is not None:
            existing.associated_users = json.dumps(request.associated_users)
        if request.subscribed_cameras is not None:
            existing.subscribed_cameras = json.dumps(request.subscribed_cameras)
        if request.notification_preferences is not None:
            existing.notification_preferences = json.dumps(request.notification_preferences)
        
        db.commit()
        logger.info(f"Updated existing ecosystem connection for {device_name}")
    else:
        # Create new connection
        connection = models.EcosystemConnection(
            app_name=request.app,
            app_version=request.version,
            host=request.host,
            remote_token=request.token,
            local_token=ecosystem_token,
            capabilities=json.dumps(request.capabilities),
            webhook_url=f"{request.host}/api/ecosystem/webhook" if request.host else None,
            ip_address=http_request.client.host if http_request.client else None,
            device_id=device_id,
            device_name=request.device_name,
            location=request.location,
            associated_users=json.dumps(request.associated_users) if request.associated_users else None,
            subscribed_cameras=json.dumps(request.subscribed_cameras) if request.subscribed_cameras else None,
            notification_preferences=json.dumps(request.notification_preferences) if request.notification_preferences else "{}"
        )
        db.add(connection)
        db.commit()
        logger.info(f"Created new ecosystem connection for {device_name} (device_id: {device_id})")
    
    return eco_schema.EcosystemConnectResponse(
        success=True,
        token=ecosystem_token,
        expires_in=86400,  # 24 hours
        capabilities=["notifications", "users", "integrations", "cameras", "events", "faces", "recordings"],
        webhook_url=f"{server_host}/api/ecosystem/webhook"
    )


async def get_auth_user(db: Session = Depends(get_db)):
    """Lazy auth dependency to avoid circular import"""
    from backend.core.auth import get_current_active_user
    from fastapi import Depends as dep
    return await get_current_active_user()


@router.get("/ecosystem/status", response_model=eco_schema.EcosystemStatusResponse)
async def get_ecosystem_status(
    db: Session = Depends(get_db)
):
    """Get status of all ecosystem connections"""
    connections = db.query(models.EcosystemConnection).all()
    
    connection_infos = []
    for conn in connections:
        try:
            capabilities = json.loads(conn.capabilities) if conn.capabilities else []
        except (json.JSONDecodeError, TypeError, ValueError):
            capabilities = []
        
        connection_infos.append(eco_schema.EcosystemConnectionInfo(
            id=conn.id,
            app_name=conn.app_name,
            app_version=conn.app_version,
            host=conn.host,
            capabilities=capabilities,
            connected_at=conn.connected_at,
            last_seen=conn.last_seen,
            is_active=conn.is_active
        ))
    
    active_count = sum(1 for c in connections if c.is_active)
    
    return eco_schema.EcosystemStatusResponse(
        connected_apps=connection_infos,
        total_connections=len(connections),
        active_connections=active_count
    )


@router.delete("/ecosystem/disconnect/{app_name}")
async def disconnect_ecosystem_app(
    app_name: str,
    device_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Disconnect an ecosystem app.
    
    If device_id is provided, disconnects only that specific device.
    Otherwise, disconnects all devices for the app.
    """
    query = db.query(models.EcosystemConnection).filter(
        models.EcosystemConnection.app_name == app_name
    )
    
    if device_id:
        query = query.filter(models.EcosystemConnection.device_id == device_id)
    
    connections = query.all()
    
    if not connections:
        raise HTTPException(status_code=404, detail=f"Connection for {app_name} not found")
    
    for conn in connections:
        conn.is_active = False
    db.commit()
    
    return {"success": True, "message": f"Disconnected {len(connections)} device(s) for {app_name}"}


@router.patch("/ecosystem/device/{device_id}/subscriptions")
async def update_device_subscriptions(
    device_id: str,
    associated_users: Optional[List[str]] = None,
    subscribed_cameras: Optional[List[str]] = None,
    notification_preferences: Optional[Dict[str, bool]] = None,
    location: Optional[str] = None,
    device_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Update subscriptions and preferences for a connected device.
    
    This allows fine-grained control over which events a device receives:
    - associated_users: Only receive face events for these users
    - subscribed_cameras: Only receive events from these cameras
    - notification_preferences: Enable/disable specific notification types
    - location: Update device location
    - device_name: Update human-friendly name
    """
    connection = db.query(models.EcosystemConnection).filter(
        models.EcosystemConnection.device_id == device_id
    ).first()
    
    if not connection:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    if associated_users is not None:
        connection.associated_users = json.dumps(associated_users)
    
    if subscribed_cameras is not None:
        connection.subscribed_cameras = json.dumps(subscribed_cameras)
    
    if notification_preferences is not None:
        # Merge with existing preferences
        existing = {}
        if connection.notification_preferences:
            try:
                existing = json.loads(connection.notification_preferences)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        existing.update(notification_preferences)
        connection.notification_preferences = json.dumps(existing)
    
    if location is not None:
        connection.location = location
    
    if device_name is not None:
        connection.device_name = device_name
    
    db.commit()
    
    return {
        "success": True,
        "device_id": device_id,
        "device_name": connection.device_name,
        "location": connection.location,
        "associated_users": json.loads(connection.associated_users) if connection.associated_users else None,
        "subscribed_cameras": json.loads(connection.subscribed_cameras) if connection.subscribed_cameras else None,
        "notification_preferences": json.loads(connection.notification_preferences) if connection.notification_preferences else {}
    }


@router.get("/ecosystem/devices")
async def list_ecosystem_devices(
    db: Session = Depends(get_db)
):
    """
    List all connected ecosystem devices with their subscriptions.
    
    Useful for managing which devices receive which notifications.
    """
    connections = db.query(models.EcosystemConnection).filter(
        models.EcosystemConnection.is_active == True
    ).order_by(models.EcosystemConnection.priority.desc()).all()
    
    devices = []
    for conn in connections:
        devices.append({
            "device_id": conn.device_id,
            "device_name": conn.device_name,
            "app_name": conn.app_name,
            "location": conn.location,
            "host": conn.host,
            "associated_users": json.loads(conn.associated_users) if conn.associated_users else None,
            "subscribed_cameras": json.loads(conn.subscribed_cameras) if conn.subscribed_cameras else None,
            "notification_preferences": json.loads(conn.notification_preferences) if conn.notification_preferences else {},
            "priority": conn.priority,
            "last_seen": conn.last_seen.isoformat() if conn.last_seen else None
        })
    
    return {
        "success": True,
        "devices": devices,
        "total": len(devices)
    }


@router.get("/ecosystem/security")
async def get_ecosystem_security_status(
    _auth: dict = Depends(require_ecosystem_auth),
):
    """
    Get ecosystem security status.
    
    Returns information about:
    - Rate limiting status
    - Blocked IPs
    - Security recommendations
    - Token configuration
    
    **Admin only** - should be protected by authentication in production.
    """
    from backend.core.ecosystem_security import get_security_status
    
    status = get_security_status()
    return {
        "success": True,
        **status
    }


@router.post("/ecosystem/security/unblock")
async def unblock_ip(
    ip_address: str,
    _auth: dict = Depends(require_ecosystem_auth),
    db: Session = Depends(get_db),
):
    """
    Manually unblock an IP address.
    
    **Admin only** - use with caution.
    """
    from backend.core.ecosystem_security import _blocked_ips, _auth_attempts
    
    if ip_address in _blocked_ips:
        del _blocked_ips[ip_address]
    if ip_address in _auth_attempts:
        del _auth_attempts[ip_address]
    
    logger.info(f"Manually unblocked IP: {ip_address}")
    
    return {
        "success": True,
        "message": f"IP {ip_address} has been unblocked"
    }


# ============================================================================
# ECOSYSTEM WEBSOCKET (Real-time events)
# ============================================================================


@router.websocket("/ecosystem/events")
async def ecosystem_events_websocket(websocket: WebSocket):
    """
    WebSocket for real-time event streaming to ecosystem apps.

    **Authentication (H-1 fix):** Token is sent in the *first message*
    after the connection is accepted, not in the query string.  This
    prevents token leakage via server access-logs, Referer headers, and
    browser history.

    Handshake protocol::

        1. Client connects: ``ws://openeye:8000/api/ecosystem/events``
        2. Server accepts the raw WebSocket.
        3. Client sends: ``{"type": "auth", "token": "<ecosystem-token>"}``
        4. Server validates within 10 s or closes with 4001.
        5. Server replies: ``{"type": "auth_ok"}``
        6. Normal event streaming begins.

    Events are sent as JSON::

        {"event": "motion_detected", "camera_id": "front_door",
         "timestamp": "2025-12-13T14:30:00Z", "data": {...}}
    """
    from backend.database.session import SessionLocal

    await websocket.accept()

    # ── Phase 1: first-message authentication ──────────────────────────
    db = SessionLocal()
    connection = None
    try:
        try:
            auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        except (asyncio.TimeoutError, Exception):
            await websocket.close(code=4001, reason="Auth timeout")
            return

        if auth_msg.get("type") != "auth" or not auth_msg.get("token"):
            await websocket.close(code=4001, reason="Expected auth message")
            return

        token = auth_msg["token"]
        connection = db.query(models.EcosystemConnection).filter(
            models.EcosystemConnection.local_token == token,
            models.EcosystemConnection.is_active == True
        ).first()

        if not connection:
            await websocket.close(code=4001, reason="Invalid token")
            return

        connection.last_seen = datetime.utcnow()
        db.commit()

        await websocket.send_json({"type": "auth_ok"})
        _ecosystem_websockets.append(websocket)
        logger.info(f"Ecosystem WebSocket connected: {connection.app_name}")

        # ── Phase 2: normal event loop ─────────────────────────────────
        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=60)

                    if data.get("event") == "user_present":
                        logger.info(f"User presence detected from {connection.app_name}")

                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "ping"})

        except WebSocketDisconnect:
            logger.info(f"Ecosystem WebSocket disconnected: {connection.app_name}")
        except Exception as e:
            logger.warning(f"Ecosystem WebSocket error ({connection.app_name}): {e}")
        finally:
            if websocket in _ecosystem_websockets:
                _ecosystem_websockets.remove(websocket)
            try:
                await websocket.close()
            except Exception:
                pass
    finally:
        db.close()


# ============================================================================
# NOTIFICATIONS
# ============================================================================


@router.post("/notifications/", response_model=eco_schema.NotificationResponse)
async def receive_notification(
    notification: eco_schema.NotificationRequest,
    db: Session = Depends(get_db)
):
    """
    Receive notification from a companion app.
    
    Handles deduplication and delivery routing.
    """
    logger.info(f"Received notification from {notification.source}: {notification.type}")
    
    # Check for duplicates
    dedupe_key = notification.dedupe_key or generate_dedupe_key(notification.model_dump())
    
    existing = db.query(models.NotificationDedup).filter(
        models.NotificationDedup.dedupe_key == dedupe_key,
        models.NotificationDedup.expires_at > datetime.utcnow()
    ).first()
    
    if existing:
        return eco_schema.NotificationResponse(
            success=True,
            deduplicated=True,
            delivered_via=[]
        )
    
    # Store dedupe record
    dedup = models.NotificationDedup(
        dedupe_key=dedupe_key,
        source=notification.source,
        notification_type=notification.type,
        expires_at=datetime.utcnow() + timedelta(seconds=30)
    )
    db.add(dedup)
    db.commit()
    
    # TODO: Route notification to configured delivery methods
    # For now, just log it
    delivered_via = []
    
    notification_id = f"notif_{secrets.token_hex(8)}"
    
    return eco_schema.NotificationResponse(
        success=True,
        notification_id=notification_id,
        delivered_via=delivered_via,
        deduplicated=False
    )


@router.get("/notifications/settings", response_model=eco_schema.NotificationSettings)
async def get_notification_settings():
    """Get notification preferences for ecosystem"""
    # TODO: Load from database
    return eco_schema.NotificationSettings()


# ============================================================================
# WEBHOOK RECEIVER
# ============================================================================


@router.post("/ecosystem/webhook")
async def receive_webhook(
    request: Request,
    auth: dict = Depends(require_ecosystem_auth),
    db: Session = Depends(get_db),
):
    """
    Receive webhook events from companion apps.

    Companion apps can send events to this endpoint for processing by OpenEye.
    Requires HMAC signature or Bearer token authentication.
    """
    try:
        # Use the already-parsed payload from HMAC auth when available
        payload = auth.get("payload") if auth.get("auth_method") == "hmac" else await request.json()

        source = payload.get("source", "unknown")
        event_type = payload.get("event_type", "unknown")
        
        logger.info(f"Webhook received from {source}: {event_type}")
        
        # Process based on event type
        if event_type == "user_present":
            # User presence detected on MagicMirror
            logger.info(f"User presence from {source}: {payload.get('data', {})}")
        
        return {"success": True, "message": "Webhook processed"}
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# ECOSYSTEM CAMERA STREAMING (For MagicMirror/Mobile integration)
# ============================================================================


@router.get("/ecosystem/cameras")
async def list_cameras_for_ecosystem(
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    List available cameras for ecosystem apps.

    Returns camera information suitable for MagicMirror or mobile app display.
    Includes stream URLs and current status.
    """
    # Verify ecosystem token (required)
    connection = db.query(models.EcosystemConnection).filter(
        models.EcosystemConnection.local_token == token,
        models.EcosystemConnection.is_active == True
    ).first()
    if not connection:
        raise HTTPException(status_code=401, detail="Invalid ecosystem token")
    
    from backend.core.camera_manager import manager as camera_manager
    
    cameras = db.query(models.Camera).filter(models.Camera.is_active == True).all()
    
    camera_list = []
    for cam in cameras:
        camera_instance = camera_manager.get_camera(cam.camera_id)
        is_running = camera_instance is not None and camera_instance.is_running if camera_instance else False
        
        camera_list.append({
            "camera_id": cam.camera_id,
            "name": getattr(cam, 'name', cam.camera_id),
            "is_running": is_running,
            "stream_url": f"/api/cameras/{cam.camera_id}/stream",
            "snapshot_url": f"/api/cameras/{cam.camera_id}/snapshot",
            "ecosystem_stream_url": f"/api/ecosystem/stream/{cam.camera_id}",
            "motion_detection_enabled": cam.motion_detection_enabled,
            "face_detection_enabled": cam.face_detection_enabled,
            "recording_enabled": cam.recording_enabled
        })
    
    return {
        "success": True,
        "cameras": camera_list,
        "total": len(camera_list)
    }


@router.get("/ecosystem/stream/{camera_id}")
async def ecosystem_camera_stream(
    camera_id: str,
    token: str = Query(...),
    quality: str = Query("medium"),  # low, medium, high
    fps: int = Query(15),  # Target FPS
    db: Session = Depends(get_db)
):
    """
    Stream camera video for ecosystem apps with quality options.

    Designed for MagicMirror and mobile app integration with bandwidth-conscious options.

    **Quality Options:**
    - low: 320x240, JPEG quality 60 (for slow connections)
    - medium: 640x480, JPEG quality 75 (default, balanced)
    - high: Full resolution, JPEG quality 85 (for local network)

    **FPS:** Target frames per second (5-30, default 15)
    """
    import cv2
    from fastapi.responses import StreamingResponse

    # Verify ecosystem token (required)
    connection = db.query(models.EcosystemConnection).filter(
        models.EcosystemConnection.local_token == token,
        models.EcosystemConnection.is_active == True
    ).first()
    if not connection:
        raise HTTPException(status_code=401, detail="Invalid ecosystem token")
    connection.last_seen = datetime.utcnow()
    db.commit()
    
    from backend.core.camera_manager import manager as camera_manager
    
    db_camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera_id
    ).first()
    
    if not db_camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")
    
    camera_instance = camera_manager.get_camera(camera_id)
    if not camera_instance or not camera_instance.is_running:
        raise HTTPException(status_code=503, detail=f"Camera '{camera_id}' is not running")
    
    # Quality settings
    quality_settings = {
        "low": {"size": (320, 240), "jpeg_quality": 60},
        "medium": {"size": (640, 480), "jpeg_quality": 75},
        "high": {"size": None, "jpeg_quality": 85}  # None = original size
    }
    
    settings = quality_settings.get(quality, quality_settings["medium"])
    fps = max(5, min(30, fps))  # Clamp FPS to 5-30
    frame_delay = 1.0 / fps
    
    async def generate_ecosystem_frames():
        """Generate frames with quality/size options for ecosystem streaming."""
        try:
            while True:
                frame, _ = camera_instance.get_frame()
                if frame is None:
                    await asyncio.sleep(0.1)
                    continue
                
                # Resize if needed
                if settings["size"]:
                    frame = cv2.resize(frame, settings["size"], interpolation=cv2.INTER_AREA)
                
                # Encode as JPEG
                ret, buffer = cv2.imencode(
                    ".jpg", frame, 
                    [cv2.IMWRITE_JPEG_QUALITY, settings["jpeg_quality"]]
                )
                
                if not ret:
                    await asyncio.sleep(frame_delay)
                    continue
                
                frame_bytes = buffer.tobytes()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )
                
                await asyncio.sleep(frame_delay)
        except Exception as e:
            logger.error(f"Ecosystem stream error for {camera_id}: {e}")
    
    return StreamingResponse(
        generate_ecosystem_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/ecosystem/snapshot/{camera_id}")
async def ecosystem_camera_snapshot(
    camera_id: str,
    token: str = Query(...),
    quality: str = Query("medium"),
    db: Session = Depends(get_db)
):
    """
    Get a single snapshot from a camera for ecosystem apps.

    Returns a JPEG image with configurable quality.
    """
    import cv2
    from fastapi.responses import Response

    # Verify ecosystem token (required)
    connection = db.query(models.EcosystemConnection).filter(
        models.EcosystemConnection.local_token == token,
        models.EcosystemConnection.is_active == True
    ).first()
    if not connection:
        raise HTTPException(status_code=401, detail="Invalid ecosystem token")
    connection.last_seen = datetime.utcnow()
    db.commit()
    
    from backend.core.camera_manager import manager as camera_manager
    
    db_camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera_id
    ).first()
    
    if not db_camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")
    
    camera_instance = camera_manager.get_camera(camera_id)
    if not camera_instance or not camera_instance.is_running:
        raise HTTPException(status_code=503, detail=f"Camera '{camera_id}' is not running")
    
    frame, _ = camera_instance.get_frame()
    if frame is None:
        raise HTTPException(status_code=500, detail="Failed to capture frame")
    
    # Quality settings
    quality_settings = {
        "low": {"size": (320, 240), "jpeg_quality": 60},
        "medium": {"size": (640, 480), "jpeg_quality": 75},
        "high": {"size": None, "jpeg_quality": 90}
    }
    
    settings = quality_settings.get(quality, quality_settings["medium"])
    
    # Resize if needed
    if settings["size"]:
        frame = cv2.resize(frame, settings["size"], interpolation=cv2.INTER_AREA)
    
    # Encode as JPEG
    ret, buffer = cv2.imencode(
        ".jpg", frame,
        [cv2.IMWRITE_JPEG_QUALITY, settings["jpeg_quality"]]
    )
    
    if not ret:
        raise HTTPException(status_code=500, detail="Failed to encode frame")
    
    return Response(
        content=buffer.tobytes(),
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Camera-Id": camera_id,
            "X-Timestamp": datetime.utcnow().isoformat()
        }
    )


# ============================================================================
# SYSTEM STATUS (Voice Command: "Security status")
# ============================================================================


@router.get("/status", response_model=eco_schema.SystemStatusResponse)
async def get_system_status(db: Session = Depends(get_db)):
    """
    Get comprehensive system status.
    
    Used by voice command "Security status" from MagicMirror.
    Returns camera status, face recognition stats, storage info, and last event.
    """
    # Lazy imports to avoid circular dependencies
    from backend.core.camera_manager import manager as camera_manager
    from backend.core.face_recognition import get_face_manager
    
    # Get camera statistics
    cameras = db.query(models.Camera).all()
    online_count = sum(1 for c in cameras if c.is_active)
    recording_count = 0
    motion_detected_count = 0
    
    # Check active cameras in camera manager
    for cam in cameras:
        camera_instance = camera_manager.get_camera(cam.camera_id)
        if camera_instance:
            if hasattr(camera_instance, 'is_recording') and camera_instance.is_recording:
                recording_count += 1
    
    # Get face recognition statistics
    face_manager = get_face_manager()
    people = face_manager.list_people()
    enrolled_count = len(people)
    
    # Count recognitions today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    recognitions_today = db.query(models.FaceDetectionEvent).filter(
        models.FaceDetectionEvent.detected_at >= today_start
    ).count()
    
    # Get storage statistics
    import shutil
    total, used, free = shutil.disk_usage(str(paths.data_dir))
    total_gb = total / (1024 ** 3)
    used_gb = used / (1024 ** 3)
    percent_used = (used / total) * 100 if total > 0 else 0
    
    # Get last event
    last_event = None
    last_motion = db.query(models.MotionDetectionEvent).order_by(
        models.MotionDetectionEvent.detected_at.desc()
    ).first()
    
    if last_motion:
        last_event = eco_schema.LastEventInfo(
            type="motion_detected",
            camera_id=last_motion.camera_id,
            timestamp=last_motion.detected_at
        )
    
    return eco_schema.SystemStatusResponse(
        cameras=eco_schema.CameraStatusSummary(
            total=len(cameras),
            online=online_count,
            recording=recording_count,
            motion_detected=motion_detected_count
        ),
        faces=eco_schema.FaceStatusSummary(
            enrolled=enrolled_count,
            recognized_today=recognitions_today
        ),
        storage=eco_schema.StorageStatusSummary(
            used_gb=round(used_gb, 2),
            total_gb=round(total_gb, 2),
            percent_used=round(percent_used, 2)
        ),
        uptime_seconds=get_uptime_seconds(),
        last_event=last_event
    )


@router.get("/statistics")
def get_ecosystem_statistics(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    db: Session = Depends(get_db)
):
    """
    Get event statistics for MagicMirror dashboard.

    Returns motion, face, and recording counts per camera for the specified time range.
    Used by the openeye-events MagicMirror module.

    Args:
        hours: Number of hours to look back (default 24, max 168)

    Returns:
        Total event counts and per-camera breakdown
    """
    from datetime import timedelta
    from sqlalchemy import func

    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    # Get all cameras
    cameras = db.query(models.Camera).all()

    # Grouped counts in 3 queries instead of 3×N (M-2 fix)
    motion_counts = dict(
        db.query(
            models.MotionDetectionEvent.camera_id,
            func.count(models.MotionDetectionEvent.id),
        )
        .filter(models.MotionDetectionEvent.detected_at >= cutoff_time)
        .group_by(models.MotionDetectionEvent.camera_id)
        .all()
    )

    face_counts = dict(
        db.query(
            models.FaceDetectionEvent.camera_id,
            func.count(models.FaceDetectionEvent.id),
        )
        .filter(models.FaceDetectionEvent.detected_at >= cutoff_time)
        .group_by(models.FaceDetectionEvent.camera_id)
        .all()
    )

    recording_counts = dict(
        db.query(
            models.RecordingEvent.camera_id,
            func.count(models.RecordingEvent.id),
        )
        .filter(models.RecordingEvent.started_at >= cutoff_time)
        .group_by(models.RecordingEvent.camera_id)
        .all()
    )

    total_motion = sum(motion_counts.values())
    total_faces = sum(face_counts.values())
    total_recordings = sum(recording_counts.values())

    camera_stats = []
    for camera in cameras:
        mc = motion_counts.get(camera.camera_id, 0)
        fc = face_counts.get(camera.camera_id, 0)
        rc = recording_counts.get(camera.camera_id, 0)
        camera_stats.append({
            "camera_id": camera.camera_id,
            "camera_name": getattr(camera, "name", None) or camera.camera_id,
            "is_active": camera.is_active,
            "motion_events": mc,
            "face_events": fc,
            "recordings": rc,
        })

    # Sort by total activity
    camera_stats.sort(
        key=lambda x: x["motion_events"] + x["face_events"] + x["recordings"],
        reverse=True,
    )

    return {
        "motion_events": total_motion,
        "face_events": total_faces,
        "recordings": total_recordings,
        "cameras": camera_stats,
        "hours": hours,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# EVENT BROADCASTING (Called by other modules)
# ============================================================================


def should_route_event_to_device(connection, event_type: str, data: dict) -> bool:
    """
    Determine if an event should be routed to a specific device.
    
    v3.11.1: Smart routing based on device subscriptions
    
    Args:
        connection: EcosystemConnection model instance
        event_type: Type of event (motion_detected, face_recognized, etc.)
        data: Event data containing camera_id, person_name, etc.
        
    Returns:
        bool: True if this device should receive the event
    """
    # Check camera subscription
    camera_id = data.get("camera_id")
    if camera_id and connection.subscribed_cameras:
        try:
            subscribed = json.loads(connection.subscribed_cameras)
            if subscribed and camera_id not in subscribed:
                logger.debug(f"Event filtered: camera {camera_id} not in {connection.device_name}'s subscriptions")
                return False
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    # Check user association for face recognition events
    if event_type in ["face_recognized", "face_detected", "person_detected"]:
        person_name = data.get("person_name")
        if person_name and connection.associated_users:
            try:
                associated = json.loads(connection.associated_users)
                # If device has associated users and this person isn't one of them,
                # still send unknown faces but filter known faces to associated users
                if associated and person_name != "Unknown" and person_name.lower() not in [u.lower() for u in associated]:
                    logger.debug(f"Event filtered: person {person_name} not associated with {connection.device_name}")
                    return False
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    
    # Check notification preferences
    if connection.notification_preferences:
        try:
            prefs = json.loads(connection.notification_preferences)
            
            # Map event types to preference keys
            pref_key_map = {
                "motion_detected": "motion",
                "face_recognized": "face_known",
                "face_detected": "face",
                "unknown_face": "face_unknown",
                "person_detected": "person",
                "recording_started": "recording",
                "doorbell": "doorbell",
                "alarm": "alarm"
            }
            
            pref_key = pref_key_map.get(event_type, event_type)
            if pref_key in prefs and not prefs[pref_key]:
                logger.debug(f"Event filtered: {event_type} disabled in {connection.device_name}'s preferences")
                return False
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    return True


async def broadcast_ecosystem_event(
    event_type: str, 
    data: dict, 
    db: Session = None,
    target_users: List[str] = None,
    target_cameras: List[str] = None,
    priority_only: bool = False
):
    """
    Broadcast an event to ecosystem connections with smart routing.
    
    v3.11.1: Enhanced with multi-device/multi-user support
    
    Args:
        event_type: Type of event (motion_detected, face_recognized, etc.)
        data: Event data (must include camera_id for camera filtering)
        db: Database session for querying connections
        target_users: Optional list of specific users to target
        target_cameras: Optional list of cameras (overrides data.camera_id)
        priority_only: If True, only send to high-priority devices
        
    Called by other modules when events occur (motion, face detection, etc.)
    """
    event = {
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data
    }
    
    # Send to WebSocket clients (these are direct connections, send all events)
    await broadcast_to_ecosystem(event)
    
    # Send webhooks to connected apps with smart routing
    if db:
        query = db.query(models.EcosystemConnection).filter(
            models.EcosystemConnection.is_active == True,
            models.EcosystemConnection.webhook_url != None
        )
        
        if priority_only:
            query = query.filter(models.EcosystemConnection.priority > 0)
        
        # Order by priority (higher first)
        connections = query.order_by(models.EcosystemConnection.priority.desc()).all()
        
        sent_count = 0
        filtered_count = 0
        
        for conn in connections:
            # Apply smart routing
            if not should_route_event_to_device(conn, event_type, data):
                filtered_count += 1
                continue
            
            try:
                await send_webhook(conn, event.copy(), db)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send webhook to {conn.device_name or conn.app_name}: {e}")
        
        if filtered_count > 0:
            logger.debug(f"Event {event_type}: sent to {sent_count} devices, filtered for {filtered_count} devices")
        
        # Also send to user-specific push tokens based on UserPreferences
        await _send_user_push_notifications(db, event_type, data, target_users)


async def _send_user_push_notifications(
    db: Session,
    event_type: str,
    data: dict,
    target_users: List[str] = None
):
    """
    Send push notifications to users based on their preferences.
    
    v3.11.1: Routes notifications to users based on:
    - Their notification type preferences
    - Their camera access permissions
    - Their face associations
    - Quiet hours settings
    """
    from backend.database.models import User, UserPreferences
    
    # Get all users with push tokens
    query = db.query(User, UserPreferences).outerjoin(
        UserPreferences, User.id == UserPreferences.user_id
    ).filter(
        User.is_active == True,
        UserPreferences.push_token != None
    )
    
    # Filter to target users if specified
    if target_users:
        query = query.filter(User.username.in_(target_users))
    
    users_with_prefs = query.all()
    
    for user, prefs in users_with_prefs:
        if not prefs or not prefs.push_token:
            continue
        
        # Check if this user should receive this event
        if not _should_notify_user(user, prefs, event_type, data):
            continue
        
        # Send push notification
        await _send_push_notification(
            token=prefs.push_token,
            platform=prefs.push_platform,
            title=_get_notification_title(event_type),
            body=_get_notification_body(event_type, data),
            data=data
        )


def _should_notify_user(user, prefs, event_type: str, data: dict) -> bool:
    """
    Check if a user should receive a notification based on their preferences.
    """
    # Check notification types
    if prefs.notification_types:
        try:
            types = json.loads(prefs.notification_types)
            type_map = {
                "motion_detected": "motion",
                "face_recognized": "face_known",
                "face_detected": "face_unknown",
                "unknown_face": "face_unknown",
                "doorbell": "doorbell",
                "alarm": "alarm",
                "system_alert": "system"
            }
            pref_key = type_map.get(event_type, event_type)
            if pref_key in types and not types[pref_key]:
                return False
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    # Check camera access
    camera_id = data.get("camera_id")
    if camera_id and prefs.camera_access:
        try:
            allowed_cameras = json.loads(prefs.camera_access)
            if allowed_cameras and camera_id not in allowed_cameras:
                return False
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    # Check face associations for face events
    if event_type in ["face_recognized", "person_detected"]:
        person_name = data.get("person_name")
        if person_name and prefs.face_associations:
            try:
                associations = json.loads(prefs.face_associations)
                # If user has face associations, only notify for those faces
                if associations and person_name.lower() not in [f.lower() for f in associations]:
                    return False
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    
    # Check quiet hours
    if prefs.quiet_hours:
        try:
            quiet = json.loads(prefs.quiet_hours)
            if quiet.get("enabled"):
                from datetime import datetime
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                start = quiet.get("start", "22:00")
                end = quiet.get("end", "07:00")
                
                # Handle overnight quiet hours
                if start > end:
                    # Quiet hours span midnight
                    if current_time >= start or current_time < end:
                        return False
                else:
                    # Same day quiet hours
                    if start <= current_time < end:
                        return False
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    return True


def _get_notification_title(event_type: str) -> str:
    """Get notification title for event type."""
    titles = {
        "motion_detected": "Motion Detected",
        "face_recognized": "Person Recognized",
        "face_detected": "Face Detected",
        "unknown_face": "Unknown Person",
        "person_detected": "Person Detected",
        "doorbell": "Doorbell Ring",
        "alarm": "Security Alarm",
        "recording_started": "Recording Started",
        "system_alert": "System Alert"
    }
    return titles.get(event_type, "OpenEye Alert")


def _get_notification_body(event_type: str, data: dict) -> str:
    """Get notification body for event type."""
    camera = data.get("camera_name") or data.get("camera_id", "Unknown camera")
    person = data.get("person_name", "Unknown")
    
    if event_type == "motion_detected":
        return f"Motion detected on {camera}"
    elif event_type == "face_recognized":
        return f"{person} seen on {camera}"
    elif event_type in ["face_detected", "unknown_face"]:
        return f"Unknown person on {camera}"
    elif event_type == "doorbell":
        return f"Someone at the door ({camera})"
    elif event_type == "alarm":
        return f"Alarm triggered: {data.get('reason', 'Check cameras')}"
    else:
        return f"Event on {camera}"


async def _send_push_notification(
    token: str,
    platform: str,
    title: str,
    body: str,
    data: dict
):
    """
    Send push notification to a device.
    
    Note: This is a placeholder. Actual implementation requires:
    - APNs for iOS (apple-push-notification)
    - FCM for Android (firebase-admin)
    """
    logger.info(f"Push notification ({platform}): {title} - {body}")
    
    # TODO: Implement actual push notification sending
    # For iOS: Use APNs with token
    # For Android: Use FCM with device token
    
    # Example FCM implementation (requires firebase-admin):
    # if platform == "android":
    #     import firebase_admin
    #     from firebase_admin import messaging
    #     message = messaging.Message(
    #         notification=messaging.Notification(title=title, body=body),
    #         data={"event_data": json.dumps(data)},
    #         token=token
    #     )
    #     messaging.send(message)
    
    # Example APNs implementation (requires aioapns):
    # if platform == "ios":
    #     from aioapns import APNs, NotificationRequest
    #     apns = APNs(...)
    #     request = NotificationRequest(device_token=token, message={"aps": {"alert": {"title": title, "body": body}}})
    #     await apns.send(request)


# ============================================================================
# MOBILE APP ENDPOINTS
# ============================================================================


@router.post("/devices/register", response_model=eco_schema.DeviceRegisterResponse)
async def register_mobile_device(
    request: eco_schema.DeviceRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a mobile device for push notifications.
    
    Stores device token for APNs (iOS) or FCM (Android) push notifications.
    """
    import uuid
    
    device_id = str(uuid.uuid4())
    
    # Check if device already registered (by token)
    existing = db.query(models.MobileDevice).filter(
        models.MobileDevice.device_token == request.device_token
    ).first()
    
    if existing:
        # Update existing device
        existing.platform = request.platform
        existing.app_version = request.app_version
        existing.notification_preferences = json.dumps(request.notification_preferences)
        existing.last_active = datetime.utcnow()
        existing.is_active = True
        db.commit()
        device_id = existing.device_id
    else:
        # Create new device registration
        device = models.MobileDevice(
            device_id=device_id,
            platform=request.platform,
            device_token=request.device_token,
            app_version=request.app_version,
            user_id=request.user_id,
            notification_preferences=json.dumps(request.notification_preferences)
        )
        db.add(device)
        db.commit()
    
    return eco_schema.DeviceRegisterResponse(
        success=True,
        device_id=device_id,
        registered_at=datetime.utcnow()
    )


@router.get("/cameras/{camera_id}/stream/mobile", response_model=eco_schema.MobileStreamResponse)
async def get_mobile_stream(
    camera_id: str,
    quality: str = "medium",
    format: str = "mjpeg",
    db: Session = Depends(get_db)
):
    """
    Get mobile-optimized stream URL for a camera.
    
    Returns a stream URL with quality settings appropriate for mobile devices.
    """
    # Verify camera exists
    camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera_id
    ).first()
    
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")
    
    # Generate stream URL - use configured host or detect from request context
    from backend.core.config import resolve_service_port
    openeye_port = str(resolve_service_port())
    server_host = os.getenv("OPENEYE_HOST", f"http://localhost:{openeye_port}")
    stream_url = f"{server_host}/api/cameras/{camera_id}/stream"
    
    if quality == "low":
        stream_url += "?quality=low"
    elif quality == "high":
        stream_url += "?quality=high"
    
    return eco_schema.MobileStreamResponse(
        success=True,
        stream_url=stream_url,
        format=format,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )


@router.get("/cameras/{camera_id}/thumbnail", response_model=eco_schema.ThumbnailResponse)
async def get_camera_thumbnail(
    camera_id: str,
    db: Session = Depends(get_db)
):
    """
    Get cached thumbnail for a camera.
    
    Returns a thumbnail URL for camera preview in mobile app lists.
    """
    camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera_id
    ).first()
    
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")
    
    # Check for cached thumbnail
    thumbnail_path = paths.thumbnails_dir / f"{camera_id}_latest.jpg"
    
    if thumbnail_path.exists():
        return eco_schema.ThumbnailResponse(
            success=True,
            thumbnail_url=f"/data/thumbnails/{camera_id}_latest.jpg",
            captured_at=datetime.fromtimestamp(thumbnail_path.stat().st_mtime),
            camera_online=camera.is_active
        )
    
    # Generate thumbnail on-the-fly
    from backend.core.camera_manager import manager as camera_manager
    active_camera = camera_manager.get_camera(camera_id)
    if active_camera:
        import cv2
        frame, _ = active_camera.get_frame()
        if frame is not None:
            # Resize for thumbnail
            thumbnail = cv2.resize(frame, (320, 240))
            cv2.imwrite(str(thumbnail_path), thumbnail)
            
            return eco_schema.ThumbnailResponse(
                success=True,
                thumbnail_url=f"/data/thumbnails/{camera_id}_latest.jpg",
                captured_at=datetime.utcnow(),
                camera_online=True
            )
    
    raise HTTPException(status_code=503, detail="Camera offline or unavailable")


@router.get("/events/timeline", response_model=eco_schema.TimelineResponse)
async def get_events_timeline(
    page: int = 1,
    per_page: int = 20,
    camera_id: Optional[str] = None,
    event_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Get paginated event timeline for mobile apps.
    
    Returns events with pagination metadata for infinite scroll.
    """
    # Build query
    query = db.query(models.MotionDetectionEvent)
    
    if camera_id:
        query = query.filter(models.MotionDetectionEvent.camera_id == camera_id)
    
    if start_date:
        query = query.filter(models.MotionDetectionEvent.detected_at >= start_date)
    
    if end_date:
        query = query.filter(models.MotionDetectionEvent.detected_at <= end_date)
    
    # Get total count
    total_items = query.count()
    
    # Apply pagination
    query = query.order_by(models.MotionDetectionEvent.detected_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    events = query.all()
    
    # Get camera names
    cameras = {c.camera_id: c for c in db.query(models.Camera).all()}
    
    timeline_events = []
    for event in events:
        camera = cameras.get(event.camera_id)
        camera_name = camera.camera_id if camera else event.camera_id
        
        timeline_events.append(eco_schema.TimelineEvent(
            id=str(event.id),
            type="motion_detected",
            camera_id=event.camera_id,
            camera_name=camera_name,
            timestamp=event.detected_at,
            thumbnail_url=f"/api/snapshots/{event.snapshot_path.split('/')[-1]}" if event.snapshot_path else None,
            clip_available=event.recording_path is not None,
            clip_duration_seconds=None
        ))
    
    # Calculate pagination
    total_pages = (total_items + per_page - 1) // per_page
    
    return eco_schema.TimelineResponse(
        success=True,
        events=timeline_events,
        pagination=eco_schema.PaginationInfo(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )


# ============================================================================
# FACE SEARCH FOR VOICE COMMANDS (MagicMirror Integration)
# ============================================================================


@router.get("/faces/search")
async def search_face_detections(
    person_name: Optional[str] = Query(None, description="Person name to search for"),
    date: Optional[str] = Query(None, description="Specific date (YYYY-MM-DD) or relative (today, yesterday)"),
    start_date: Optional[datetime] = Query(None, description="Start of date range"),
    end_date: Optional[datetime] = Query(None, description="End of date range"),
    camera_id: Optional[str] = Query(None, description="Filter by camera"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
    include_unknown: bool = Query(False, description="Include unknown faces in results"),
    db: Session = Depends(get_db)
):
    """
    Search face detection history for MagicMirror voice commands.

    Supports natural language date queries like:
    - "search for Mikel Jr on December 24th" → person_name=Mikel Jr, date=2024-12-24
    - "when was John seen today" → person_name=John, date=today
    - "show faces from yesterday" → date=yesterday

    **Parameters:**
    - person_name: Name of person to search for (partial match supported)
    - date: Single date - supports YYYY-MM-DD, "today", "yesterday"
    - start_date / end_date: Date range for more specific queries
    - camera_id: Filter to specific camera
    - limit: Max number of results (default 50)
    - include_unknown: Include "Unknown" faces (default False)

    **Response includes:**
    - List of detection events with timestamps, cameras, confidence
    - Summary statistics (total count, cameras seen on)
    - Natural language response for voice assistants
    """
    from datetime import date as date_type

    # Parse date parameter
    query_start = None
    query_end = None

    if date:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        if date.lower() == "today":
            query_start = today
            query_end = today + timedelta(days=1)
        elif date.lower() == "yesterday":
            query_start = today - timedelta(days=1)
            query_end = today
        else:
            # Try to parse as date
            try:
                parsed_date = datetime.strptime(date, "%Y-%m-%d")
                query_start = parsed_date
                query_end = parsed_date + timedelta(days=1)
            except ValueError:
                # Try other formats
                for fmt in ["%m/%d/%Y", "%d-%m-%Y", "%B %d", "%B %d, %Y", "%b %d", "%b %d, %Y"]:
                    try:
                        parsed_date = datetime.strptime(date, fmt)
                        # If no year specified, assume current year
                        if parsed_date.year == 1900:
                            parsed_date = parsed_date.replace(year=datetime.utcnow().year)
                        query_start = parsed_date
                        query_end = parsed_date + timedelta(days=1)
                        break
                    except ValueError:
                        continue

    # Use explicit start/end dates if provided
    if start_date:
        query_start = start_date
    if end_date:
        query_end = end_date

    # Build query
    query = db.query(models.FaceDetectionEvent)

    # Filter by person name (case-insensitive partial match)
    if person_name:
        # Escape SQL LIKE wildcards to prevent injection (M-4 fix)
        safe_name = person_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(
            models.FaceDetectionEvent.person_name.ilike(f"%{safe_name}%")
        )

    # Exclude unknown faces unless requested
    if not include_unknown:
        query = query.filter(models.FaceDetectionEvent.person_name != "Unknown")

    # Date filters
    if query_start:
        query = query.filter(models.FaceDetectionEvent.detected_at >= query_start)
    if query_end:
        query = query.filter(models.FaceDetectionEvent.detected_at < query_end)

    # Camera filter
    if camera_id:
        query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)

    # Order by most recent first
    query = query.order_by(models.FaceDetectionEvent.detected_at.desc())

    # Get total count before limiting
    total_count = query.count()

    # Apply limit
    events = query.limit(limit).all()

    # Build response
    detections = []
    cameras_seen = set()
    persons_found = set()

    for event in events:
        cameras_seen.add(event.camera_id)
        persons_found.add(event.person_name)

        # Normalize snapshot path
        snapshot_path = event.snapshot_path or ''
        if snapshot_path.startswith('data/snapshots/'):
            snapshot_path = snapshot_path.replace('data/snapshots/', '')

        detections.append({
            "id": event.id,
            "person_name": event.person_name,
            "camera_id": event.camera_id,
            "detected_at": event.detected_at.isoformat(),
            "confidence": event.confidence,
            "snapshot_url": f"/data/snapshots/{snapshot_path}" if snapshot_path else None
        })

    # Generate natural language response for voice assistants
    voice_response = _generate_voice_response(
        person_name=person_name,
        date=date,
        total_count=total_count,
        detections=detections,
        cameras_seen=list(cameras_seen),
        query_start=query_start,
        query_end=query_end
    )

    return {
        "success": True,
        "query": {
            "person_name": person_name,
            "date": date,
            "start_date": query_start.isoformat() if query_start else None,
            "end_date": query_end.isoformat() if query_end else None,
            "camera_id": camera_id
        },
        "results": {
            "total_count": total_count,
            "returned_count": len(detections),
            "cameras_seen": list(cameras_seen),
            "persons_found": list(persons_found),
            "detections": detections
        },
        "voice_response": voice_response
    }


def _generate_voice_response(
    person_name: Optional[str],
    date: Optional[str],
    total_count: int,
    detections: list,
    cameras_seen: list,
    query_start: Optional[datetime],
    query_end: Optional[datetime]
) -> str:
    """Generate natural language response for voice assistants."""
    if total_count == 0:
        if person_name and date:
            return f"I didn't find any sightings of {person_name} on {date}."
        elif person_name:
            return f"I didn't find any recent sightings of {person_name}."
        elif date:
            return f"No face detections were recorded on {date}."
        else:
            return "No face detections found matching your search."

    # Build response
    if person_name:
        if total_count == 1:
            event = detections[0]
            time_str = datetime.fromisoformat(event["detected_at"]).strftime("%I:%M %p")
            return f"{person_name} was seen once on {event['camera_id']} at {time_str}."
        else:
            cameras_str = ", ".join(cameras_seen[:3])
            if len(cameras_seen) > 3:
                cameras_str += f" and {len(cameras_seen) - 3} more"

            if date:
                return f"I found {total_count} sightings of {person_name} on {date}. They were seen on {cameras_str}."
            else:
                # Get time range
                first_time = datetime.fromisoformat(detections[-1]["detected_at"]).strftime("%I:%M %p")
                last_time = datetime.fromisoformat(detections[0]["detected_at"]).strftime("%I:%M %p")
                return f"I found {total_count} sightings of {person_name}, from {first_time} to {last_time}. They were seen on {cameras_str}."
    else:
        # General search
        persons = list(set(d["person_name"] for d in detections))
        if len(persons) == 1:
            return f"I found {total_count} detections of {persons[0]} during that time."
        elif len(persons) <= 3:
            return f"I found {total_count} detections of {', '.join(persons)} during that time."
        else:
            return f"I found {total_count} face detections of {len(persons)} different people during that time."


@router.get("/recordings/{recording_id}/play", response_model=eco_schema.RecordingPlaybackResponse)
async def get_recording_playback(
    recording_id: int,
    db: Session = Depends(get_db)
):
    """
    Get playback URL for a recording.
    
    Returns URLs for streaming and downloading recordings.
    """
    recording = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.id == recording_id
    ).first()
    
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    from backend.core.config import resolve_service_port
    openeye_port = str(resolve_service_port())
    server_host = os.getenv("OPENEYE_HOST", f"http://localhost:{openeye_port}")
    
    # Calculate resolution from first few frames if not stored
    resolution = "1920x1080"  # Default
    
    return eco_schema.RecordingPlaybackResponse(
        success=True,
        playback_url=f"{server_host}/api/recordings/{recording_id}/stream",
        format="mp4",
        duration_seconds=recording.duration_seconds or 0,
        resolution=resolution,
        file_size_bytes=recording.file_size_bytes or 0,
        download_url=f"{server_host}/api/recordings/{recording_id}/download"
    )

