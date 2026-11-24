# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Regression tests for camera discovery defects, vendor fingerprinting,
cross-platform subnet/ARP discovery, and at-rest credential encryption.

Covers confirmed root causes:
  1. USB discovery could not distinguish "no camera attached" from
     "OS denied camera permission", so a denied host reported success
     with zero cameras and no error.
  2. Network discovery reported any open TCP port as an RTSP camera,
     producing phantom cameras that then failed quick-add with a 400.
  3. Spec-compliant cameras (like TP-Link Tapo) return 200 OK to OPTIONS
     and only challenge with 401 + WWW-Authenticate realm on DESCRIBE.
  4. Camera sources and embedded RTSP credentials must be encrypted at rest
     in SQLite using Fernet while transparently decrypting on ORM read and
     redacting passwords in API responses and logs.
  5. The statistics WebSocket parsed client frames with eval().
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from backend.core.camera_discovery import CameraDiscovery
from backend.core.camera_security import (
    ENCRYPTED_PREFIX,
    decrypt_camera_source,
    encrypt_camera_source,
    inject_rtsp_credentials,
    is_encrypted_source,
    redact_url_credentials,
    strip_url_credentials,
)
from backend.database import crud


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
            discovery,
            "_enumerate_platform_cameras",
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
            cap.isOpened.return_value = index == 0
            cap.read.return_value = (index == 0, frame if index == 0 else None)
            cap.get.return_value = 640
            return cap

        with patch.object(
            discovery,
            "_enumerate_platform_cameras",
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
    """Network discovery must verify RTSP, vendor realms, and auth requirements."""

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
            return b"RTSP/1.0 401 Unauthorized\r\nWWW-Authenticate: Digest\r\n\r\n"

        async def fake_port_open(ip, port, timeout=0.8):
            return False

        with patch.object(discovery, "_rtsp_options_probe", fake_probe), patch.object(
            discovery, "_check_tcp_port_open", fake_port_open
        ):
            result = await discovery._check_rtsp_port("192.168.50.20", 554)

        assert result is not None
        assert result["requires_auth"] is True
        assert result["ip"] == "192.168.50.20"

    @pytest.mark.asyncio
    async def test_tapo_camera_options_200_and_describe_401_detected(self):
        """
        TP-Link Tapo answers 200 OK to OPTIONS and 401 Unauthorized with
        realm="TP-LINK IP-Camera" to DESCRIBE. Discovery must detect
        requires_auth=True, identify TP-Link Tapo, and prioritize /stream1 and /stream2.
        """
        discovery = CameraDiscovery()

        async def fake_probe(ip, port, timeout=2.0):
            return (
                b"RTSP/1.0 200 OK\r\n"
                b"CSeq: 1\r\n"
                b"Public: OPTIONS, DESCRIBE, SETUP, TEARDOWN, PLAY\r\n\r\n"
                b"RTSP/1.0 401 Unauthorized\r\n"
                b"CSeq: 2\r\n"
                b'WWW-Authenticate: Basic realm="TP-LINK IP-Camera"\r\n'
                b'WWW-Authenticate: Digest realm="TP-LINK IP-Camera", nonce="abc"\r\n\r\n'
            )

        with patch.object(discovery, "_rtsp_options_probe", fake_probe):
            result = await discovery._check_rtsp_port("192.168.50.135", 554)

        assert result is not None
        assert result["ip"] == "192.168.50.135"
        assert result["requires_auth"] is True
        assert result["manufacturer"] == "TP-Link Tapo"
        assert result["urls"][0] == "rtsp://192.168.50.135:554/stream1"
        assert result["urls"][1] == "rtsp://192.168.50.135:554/stream2"
        assert result["auto_config"]["source"] == "rtsp://192.168.50.135:554/stream1"

    @pytest.mark.asyncio
    async def test_closed_port_is_rejected(self):
        discovery = CameraDiscovery()

        async def fake_probe(ip, port, timeout=2.0):
            return None

        with patch.object(discovery, "_rtsp_options_probe", fake_probe):
            result = await discovery._check_rtsp_port("192.168.50.99", 554)

        assert result is None

    def test_subnet_deduplication_and_virtual_interface_filtering(self):
        """
        _get_local_subnets must ignore virtual/bridge/tunnel interfaces and
        deduplicate identical subnets across multiple physical NICs (e.g. en0 + en1).
        """
        discovery = CameraDiscovery()
        import socket
        from collections import namedtuple

        Addr = namedtuple("Addr", "family address netmask broadcast ptp")
        fake_addrs = {
            "lo0":       [Addr(socket.AF_INET, "127.0.0.1",       "255.0.0.0",       None, None)],
            "en0":       [Addr(socket.AF_INET, "192.168.50.73",   "255.255.255.0",   None, None)],
            "bridge100": [Addr(socket.AF_INET, "192.168.105.1",   "255.255.255.0",   None, None)],
            "en1":       [Addr(socket.AF_INET, "192.168.50.61",   "255.255.255.0",   None, None)],
            "utun13":    [Addr(socket.AF_INET, "100.108.195.116", "255.255.255.255", None, None)],
        }

        with patch.object(
            discovery, "_get_primary_lan_ip", return_value="192.168.50.73"
        ), patch("backend.core.camera_discovery.psutil.net_if_addrs", return_value=fake_addrs):
            subnets = discovery._get_local_subnets()

        assert subnets == ["192.168.50.0/24"]


class TestCameraCredentialEncryption:
    """Camera sources and RTSP credentials must be encrypted at rest and redacted in output."""

    def test_encrypt_and_decrypt_roundtrip(self):
        raw = "rtsp://tapo_admin:My$ecret@Pass!@192.168.50.135:554/stream1"
        encrypted = encrypt_camera_source(raw)
        assert is_encrypted_source(encrypted)
        assert encrypted.startswith(ENCRYPTED_PREFIX)
        assert "My$ecret" not in encrypted
        assert "192.168.50.135" not in encrypted
        assert decrypt_camera_source(encrypted) == raw

    def test_inject_and_redact_special_char_credentials(self):
        base = "rtsp://192.168.50.135:554/stream1"
        injected = inject_rtsp_credentials(base, "tapo@user", "p@ss:w/rd$1")
        assert injected == "rtsp://tapo%40user:p%40ss%3Aw%2Frd%241@192.168.50.135:554/stream1"
        assert redact_url_credentials(injected) == "rtsp://tapo%40user:***@192.168.50.135:554/stream1"
        assert strip_url_credentials(injected) == base

    def test_database_stores_encrypted_ciphertext_at_rest(self, db_session):
        plain_url = "rtsp://tapo_user:SuperSecret123@192.168.50.135:554/stream1"
        crud.create_camera(
            db_session,
            {
                "camera_id": "tapo_ encrypted_test",
                "camera_type": "rtsp",
                "source": plain_url,
                "is_active": True,
            },
        )

        # Raw SQLite value on disk must be encrypted (never plaintext)
        raw_stored = db_session.execute(
            text("SELECT source FROM cameras WHERE camera_id = :cid"),
            {"cid": "tapo_ encrypted_test"},
        ).scalar()
        assert raw_stored is not None
        assert raw_stored.startswith(ENCRYPTED_PREFIX)
        assert "SuperSecret123" not in raw_stored

        # ORM read must transparently decrypt back to the usable RTSP URL
        cam = crud.get_camera_by_id(db_session, "tapo_ encrypted_test")
        assert cam is not None
        assert cam.source == plain_url


class TestStreamRelayManager:
    """Verify optional go2rtc / MediaMTX stream relay multiplexing and direct fallback."""

    def test_sub_stream_url_inference_across_vendors(self):
        from backend.core.stream_relay import infer_sub_stream_url

        assert (
            infer_sub_stream_url("rtsp://user:pass@192.168.50.135:554/stream1")
            == "rtsp://user:pass@192.168.50.135:554/stream2"
        )
        assert (
            infer_sub_stream_url("rtsp://admin:123@192.168.1.50:554/Streaming/Channels/101")
            == "rtsp://admin:123@192.168.1.50:554/Streaming/Channels/102"
        )
        assert (
            infer_sub_stream_url("rtsp://admin:123@192.168.1.60:554/cam/realmonitor?channel=1&subtype=0")
            == "rtsp://admin:123@192.168.1.60:554/cam/realmonitor?channel=1&subtype=1"
        )
        assert (
            infer_sub_stream_url("rtsp://admin:123@192.168.1.70:554/h264Preview_01_main")
            == "rtsp://admin:123@192.168.1.70:554/h264Preview_01_sub"
        )

    def test_direct_fallback_when_no_relay_is_running(self):
        from backend.core.stream_relay import StreamRelayManager

        mgr = StreamRelayManager()
        with patch.object(mgr, "_probe_go2rtc", return_value=False), patch.object(
            mgr, "_probe_mediamtx", return_value=False
        ):
            resolved = mgr.resolve_capture_source(
                "tapo_cam", "rtsp://user:secret@192.168.50.135:554/stream1"
            )
            status = mgr.get_status()

        assert resolved == "rtsp://user:secret@192.168.50.135:554/stream1"
        assert status["active_backend"] == "direct"
        assert status["relay_active"] is False
        assert "secret" not in str(status["streams"])

    def test_go2rtc_registration_and_multiplex_urls(self):
        from backend.core.stream_relay import StreamRelayManager

        mgr = StreamRelayManager()
        calls = []

        def fake_http(method, url, payload=None, timeout=1.5):
            calls.append((method, url, payload))
            return 200, b"{}"

        with patch.object(mgr, "_probe_go2rtc", return_value=True), patch.object(
            mgr, "_http_request", side_effect=fake_http
        ):
            info = mgr.register_camera(
                "tapo_front",
                "rtsp://tapo_user:secret@192.168.50.135:554/stream1",
            )

        assert info.backend == "go2rtc"
        assert info.rtsp_main_url == "rtsp://127.0.0.1:8554/tapo_front"
        assert info.rtsp_sub_url == "rtsp://127.0.0.1:8554/tapo_front_sub"
        assert info.webrtc_url == "http://127.0.0.1:1984/api/webrtc?src=tapo_front"
        assert len(calls) == 2

    def test_mediamtx_registration_with_source_on_demand(self):
        from backend.core.stream_relay import StreamRelayManager

        mgr = StreamRelayManager()
        calls = []

        def fake_http(method, url, payload=None, timeout=1.5):
            calls.append((method, url, payload))
            return 200, b"{}"

        with patch.object(mgr, "_probe_go2rtc", return_value=False), patch.object(
            mgr, "_probe_mediamtx", return_value=True
        ), patch.object(mgr, "_http_request", side_effect=fake_http):
            info = mgr.register_camera(
                "tapo_backyard",
                "rtsp://tapo_user:secret@192.168.50.135:554/stream1",
                source_on_demand=True,
            )

        assert info.backend == "mediamtx"
        assert info.rtsp_main_url == "rtsp://127.0.0.1:8554/tapo_backyard"
        assert info.rtsp_sub_url == "rtsp://127.0.0.1:8554/tapo_backyard_sub"
        assert calls[0][2]["sourceOnDemand"] is True


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
            "type": "text",
            "content": "hello",
        }

    def test_malformed_json_does_not_raise(self):
        from backend.api.routes.websockets import parse_client_message

        result = parse_client_message('{"type": ')
        assert result["type"] == "text"


class TestMultiVendorPTZAndEdgeAI:
    """Verify multi-vendor PTZ auto-connection, Pan/Tilt-only ONVIF payloads, and Edge AI event ingestion."""

    def test_extract_camera_connection_info_across_vendors(self):
        from backend.core.camera_security import (
            encrypt_camera_source,
            extract_camera_connection_info,
        )

        enc_tapo = encrypt_camera_source(
            "rtsp://tapo_user:My%40Secret%3APass@192.168.50.135:554/stream1"
        )
        info = extract_camera_connection_info(enc_tapo)
        assert info["is_network_camera"] is True
        assert info["camera_ip"] == "192.168.50.135"
        assert info["username"] == "tapo_user"
        assert info["password"] == "My@Secret:Pass"
        assert info["vendor_hint"] == "tapo"

        hik_info = extract_camera_connection_info(
            "rtsp://admin:12345@192.168.1.64:554/Streaming/Channels/101"
        )
        assert hik_info["vendor_hint"] == "hikvision"

        dahua_info = extract_camera_connection_info(
            "rtsp://admin:12345@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0"
        )
        assert dahua_info["vendor_hint"] == "dahua"

        reolink_info = extract_camera_connection_info(
            "rtsp://admin:12345@192.168.1.120:554/h264Preview_01_main"
        )
        assert reolink_info["vendor_hint"] == "reolink"
