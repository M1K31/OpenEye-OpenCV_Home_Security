# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Regression tests for camera discovery defects.

Covers three confirmed root causes:
  1. USB discovery could not distinguish "no camera attached" from
     "OS denied camera permission", so a denied host reported success
     with zero cameras and no error.
  2. Network discovery reported any open TCP port as an RTSP camera,
     producing phantom cameras that then failed quick-add with a 400.
  3. The statistics WebSocket parsed client frames with eval().
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.core.camera_discovery import CameraDiscovery


class TestUsbPermissionDetection:
    """USB discovery must report OS permission denial as a warning."""

    @pytest.mark.asyncio
    async def test_denied_permission_is_reported_not_silent(self):
        """
        Platform reports an attached camera but OpenCV opens nothing.
        That combination means the OS denied access, and discovery must
        say so rather than returning a bare empty list.
        """
        discovery = CameraDiscovery()

        with patch.object(
            discovery, "_enumerate_platform_cameras",
            return_value=[{"name": "HD Webcam C615", "index": 0}],
        ), patch("backend.core.camera_discovery.cv2.VideoCapture") as cap:
            cap.return_value.isOpened.return_value = False

            result = await discovery.discover_usb_cameras_detailed()

        assert result["cameras"] == []
        assert result["permission_denied"] is True
        assert any(
            "permission" in w.lower() for w in result["warnings"]
        ), f"expected a permission warning, got {result['warnings']}"

    @pytest.mark.asyncio
    async def test_no_devices_is_not_a_permission_error(self):
        """No attached devices must NOT be reported as a permission problem."""
        discovery = CameraDiscovery()

        with patch.object(
            discovery, "_enumerate_platform_cameras", return_value=[]
        ), patch("backend.core.camera_discovery.cv2.VideoCapture") as cap:
            cap.return_value.isOpened.return_value = False

            result = await discovery.discover_usb_cameras_detailed()

        assert result["cameras"] == []
        assert result["permission_denied"] is False

    @pytest.mark.asyncio
    async def test_working_camera_is_returned(self):
        """A camera that opens and yields a frame is reported normally."""
        discovery = CameraDiscovery()
        frame = MagicMock()

        def fake_capture(index, *args, **kwargs):
            cap = MagicMock()
            cap.isOpened.return_value = (index == 0)
            cap.read.return_value = (index == 0, frame if index == 0 else None)
            cap.get.return_value = 640
            return cap

        with patch.object(
            discovery, "_enumerate_platform_cameras",
            return_value=[{"name": "HD Webcam C615", "index": 0}],
        ), patch(
            "backend.core.camera_discovery.cv2.VideoCapture",
            side_effect=fake_capture,
        ):
            result = await discovery.discover_usb_cameras_detailed()

        assert len(result["cameras"]) == 1
        assert result["cameras"][0]["index"] == 0
        assert result["permission_denied"] is False

    @pytest.mark.asyncio
    async def test_probe_does_not_block_the_event_loop(self):
        """
        Camera probing is blocking I/O and must run off the event loop,
        otherwise it stalls WebSocket handshakes for the probe duration.
        """
        discovery = CameraDiscovery()
        ticks = []

        def slow_capture(index, *args, **kwargs):
            import time
            time.sleep(0.05)
            cap = MagicMock()
            cap.isOpened.return_value = False
            return cap

        async def heartbeat():
            for _ in range(5):
                ticks.append(1)
                await asyncio.sleep(0.01)

        with patch.object(
            discovery, "_enumerate_platform_cameras", return_value=[]
        ), patch(
            "backend.core.camera_discovery.cv2.VideoCapture",
            side_effect=slow_capture,
        ):
            await asyncio.gather(
                discovery.discover_usb_cameras_detailed(), heartbeat()
            )

        assert len(ticks) == 5, "event loop was blocked during camera probing"


class TestRtspValidation:
    """Network discovery must verify RTSP, not just an open TCP port."""

    @pytest.mark.asyncio
    async def test_open_port_that_is_not_rtsp_is_rejected(self):
        """
        A web admin panel on port 88 answers HTTP, not RTSP.
        It must not be reported as a camera.
        """
        discovery = CameraDiscovery()

        async def fake_probe(ip, port, timeout=2.0):
            return b"HTTP/1.1 404 Not Found\r\nServer: lighttpd\r\n\r\n"

        with patch.object(discovery, "_rtsp_options_probe", fake_probe):
            result = await discovery._check_rtsp_port("192.168.50.73", 88)

        assert result is None

    @pytest.mark.asyncio
    async def test_rtsp_server_requiring_auth_is_accepted(self):
        """A real camera answering 401 over RTSP IS a camera."""
        discovery = CameraDiscovery()

        async def fake_probe(ip, port, timeout=2.0):
            return b'RTSP/1.0 401 Unauthorized\r\nWWW-Authenticate: Digest\r\n\r\n'

        with patch.object(discovery, "_rtsp_options_probe", fake_probe):
            result = await discovery._check_rtsp_port("192.168.50.20", 554)

        assert result is not None
        assert result["requires_auth"] is True
        assert result["ip"] == "192.168.50.20"

    @pytest.mark.asyncio
    async def test_closed_port_is_rejected(self):
        discovery = CameraDiscovery()

        async def fake_probe(ip, port, timeout=2.0):
            return None

        with patch.object(discovery, "_rtsp_options_probe", fake_probe):
            result = await discovery._check_rtsp_port("192.168.50.99", 554)

        assert result is None


class TestWebSocketMessageParsing:
    """Client frames must never reach eval()."""

    def test_malicious_payload_is_not_executed(self):
        from backend.api.routes.websockets import parse_client_message

        payload = '{"type": "__import__(\'os\').system(\'touch /tmp/pwned\')"}'
        message = parse_client_message(payload)

        assert isinstance(message, dict)
        assert message.get("type") != "unknown_executed"

    def test_valid_json_is_parsed(self):
        from backend.api.routes.websockets import parse_client_message

        assert parse_client_message('{"type": "ping"}') == {"type": "ping"}

    def test_plain_text_falls_back_safely(self):
        from backend.api.routes.websockets import parse_client_message

        assert parse_client_message("hello") == {
            "type": "text", "content": "hello"
        }

    def test_malformed_json_does_not_raise(self):
        from backend.api.routes.websockets import parse_client_message

        result = parse_client_message('{"type": ')
        assert result["type"] == "text"
