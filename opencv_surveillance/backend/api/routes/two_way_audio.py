# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

from fastapi import APIRouter, Depends, Query, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional
from backend.core.auth import get_current_active_user
from backend.api.routes.websockets import authenticate_websocket
import logging

try:
    from backend.core.two_way_audio_system import audio_manager
    AUDIO_AVAILABLE = True
except ImportError:
    audio_manager = None
    AUDIO_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/test")
async def index(current_user = Depends(get_current_active_user)):
    """Serve test page for two-way audio"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Two-Way Audio Test</title>
    </head>
    <body>
        <h1>Two-Way Audio Communication</h1>
        <button id='start'>Start Audio</button>
        <button id='stop'>Stop Audio</button>
        <div id='status'></div>
        <script>
            const ws = new WebSocket('ws://localhost:8000/api/audio/ws/camera_1');
            let pc = null;
            document.getElementById('start').onclick = async () => {
                pc = new RTCPeerConnection({
                    iceServers: [{urls: 'stun:stun.l.google.com:19302'}]
                });
                const stream = await navigator.mediaDevices.getUserMedia({audio: true});
                stream.getTracks().forEach(track => pc.addTrack(track, stream));
                pc.ontrack = event => {
                    const audio = new Audio();
                    audio.srcObject = event.streams[0];
                    audio.play();
                };
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                ws.send(JSON.stringify({type: 'offer', sdp: offer.sdp}));
            };
            ws.onmessage = async (event) => {
                const message = JSON.parse(event.data);
                if (message.type === 'answer') {
                    await pc.setRemoteDescription({type: 'answer', sdp: message.sdp});
                }
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

@router.get("/devices")
def list_audio_devices(current_user = Depends(get_current_active_user)):
    """List available audio input/output devices"""
    if not AUDIO_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"error": "Two-way audio unavailable — sounddevice/aiortc not installed"},
        )
    return audio_manager.list_audio_devices()

@router.websocket("/ws/{camera_id}")
async def websocket_audio_stream(
    websocket: WebSocket,
    camera_id: str,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for two-way audio streaming

    Args:
        websocket: FastAPI WebSocket instance
        camera_id: ID of the camera to stream audio from/to

    WebRTC signaling flow:
        1. Client sends offer (SDP)
        2. Server responds with answer (SDP)
        3. ICE candidates are exchanged
        4. Audio stream established
    """
    # Authenticate BEFORE accepting: an unauthenticated peer must never reach the
    # audio pipeline. authenticate_websocket closes the socket with a policy-violation
    # code when the token is missing or invalid.
    user = await authenticate_websocket(websocket, token)
    if not user:
        return

    await websocket.accept()
    if not AUDIO_AVAILABLE:
        await websocket.send_json({"error": "Two-way audio unavailable — sounddevice/aiortc not installed"})
        await websocket.close(code=1011, reason="Audio dependencies not installed")
        return
    session = await audio_manager.create_session(camera_id)
    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "offer":
                answer = await session.create_answer(data)
                await websocket.send_json(answer)
            elif data["type"] == "answer":
                await session.set_remote_description(data)
    except Exception as e:
        logger.error(f"WebSocket audio error for camera {camera_id}: {e}")
    finally:
        await audio_manager.close_session(camera_id)
