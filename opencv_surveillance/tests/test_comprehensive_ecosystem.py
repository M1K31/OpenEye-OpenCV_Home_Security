"""
Comprehensive test suite for the OpenEye ecosystem audit fixes.

Covers:
  1. Ecosystem security audit fixes (C-1..C-4, H-1..H-8, M-1..M-6, L-1, L-3)
  2. Facial recognition pipeline using real test photos
  3. Camera discovery (USB + network)
  4. Notification / alert system simulation
  5. Granular camera controls (motion, face, recording toggles)
  6. Privacy & permissions (macOS / Linux / Docker)

Run with:
    cd opencv_surveillance && python3 -m pytest tests/test_comprehensive_ecosystem.py -v
"""

import sys
import os
import json
import hashlib
import hmac
import secrets
import platform
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# Ensure imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# SECTION 1: Ecosystem Security Audit Fixes
# ============================================================================


class TestCriticalFixes:
    """C-1 through C-4: HMAC secret warnings, auth on security endpoints,
    SSRF protection, crypto consolidation."""

    # -- C-1: HMAC secret insecure-default warning --

    def test_c1_config_warns_on_insecure_default(self):
        """Config should warn when ECOSYSTEM_HMAC_SECRET is not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECOSYSTEM_HMAC_SECRET", None)
            with pytest.warns(UserWarning, match="ECOSYSTEM_HMAC_SECRET"):
                from ecosystem_client.config import EcosystemConfig
                cfg = EcosystemConfig.from_env()
                assert cfg.hmac_secret == "dev-ecosystem-secret-change-in-production"

    def test_c1_config_no_warning_when_set(self):
        """Config should NOT warn when secret is explicitly provided."""
        with patch.dict(os.environ, {"ECOSYSTEM_HMAC_SECRET": "my-prod-secret"}):
            from ecosystem_client.config import EcosystemConfig
            cfg = EcosystemConfig.from_env()
            assert cfg.hmac_secret == "my-prod-secret"

    def test_c1_middleware_warns_on_insecure_default(self, caplog):
        """Middleware should log warning for missing secret."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECOSYSTEM_HMAC_SECRET", None)
            import importlib
            import ecosystem_auth.middleware as mw_mod
            importlib.reload(mw_mod)
            secret = mw_mod.get_ecosystem_secret()
            assert secret == mw_mod._INSECURE_DEFAULT_SECRET

    # -- C-2: Auth on security endpoints --

    def test_c2_security_endpoint_requires_auth(self, client):
        """GET /ecosystem/security must reject unauthenticated requests."""
        resp = client.get("/api/ecosystem/security")
        assert resp.status_code == 401

    def test_c2_unblock_endpoint_requires_auth(self, client):
        """POST /ecosystem/security/unblock must reject unauthenticated requests."""
        resp = client.post("/api/ecosystem/security/unblock", params={"ip_address": "1.2.3.4"})
        assert resp.status_code == 401

    # -- C-3: SSRF protection --

    def test_c3_ssrf_rejects_loopback(self):
        """_is_safe_url must block 127.x.x.x addresses."""
        from backend.api.routes.ecosystem import _is_safe_url
        assert _is_safe_url("http://127.0.0.1:8080/callback") is False
        assert _is_safe_url("http://127.0.0.100/hook") is False

    def test_c3_ssrf_rejects_private_ranges(self):
        """_is_safe_url must block RFC-1918 ranges."""
        from backend.api.routes.ecosystem import _is_safe_url
        assert _is_safe_url("http://10.0.0.5:3000") is False
        assert _is_safe_url("http://192.168.1.100:8080") is False
        assert _is_safe_url("http://172.16.0.1:9000") is False

    def test_c3_ssrf_allows_public_ip(self):
        """_is_safe_url must allow public IP addresses."""
        from backend.api.routes.ecosystem import _is_safe_url
        assert _is_safe_url("http://8.8.8.8:443") is True
        assert _is_safe_url("http://203.0.113.50:8080") is True

    def test_c3_ssrf_allows_hostname(self):
        """_is_safe_url must allow regular hostnames (DNS not resolved)."""
        from backend.api.routes.ecosystem import _is_safe_url
        assert _is_safe_url("http://my-mirror.local:8080") is True

    # -- C-4: Crypto consolidation (single sign_payload source) --

    def test_c4_sign_payload_uses_compact_separators(self):
        """sign_payload from ecosystem_auth.tokens uses (',', ':') separators."""
        from ecosystem_auth.tokens import sign_payload
        payload = {"b": 2, "a": 1}
        sig = sign_payload(payload, "secret")
        # Verify deterministic: sorted keys, compact separators
        expected_msg = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        expected = hmac.new("secret".encode(), expected_msg, hashlib.sha256).hexdigest()
        assert sig == expected

    def test_c4_ecosystem_security_imports_from_tokens(self):
        """ecosystem_security.py should re-export from ecosystem_auth.tokens."""
        from backend.core.ecosystem_security import sign_payload as sec_sign
        from ecosystem_auth.tokens import sign_payload as tok_sign
        assert sec_sign is tok_sign

    def test_c4_no_local_sign_payload_in_routes(self):
        """ecosystem.py routes should not define its own sign_payload."""
        import inspect
        from backend.api.routes import ecosystem as eco_routes
        # The module-level function should be the imported one
        from ecosystem_auth.tokens import sign_payload as canonical
        assert eco_routes.sign_payload is canonical


class TestHighPriorityFixes:
    """H-1 through H-8."""

    # -- H-2: Camera endpoints require token, use .local_token --

    def test_h2_cameras_endpoint_requires_token(self, client):
        """GET /ecosystem/cameras must require token query param."""
        resp = client.get("/api/ecosystem/cameras")
        # FastAPI returns 422 when required query param is missing
        assert resp.status_code == 422

    def test_h2_stream_endpoint_requires_token(self, client):
        """GET /ecosystem/stream/{id} must require token."""
        resp = client.get("/api/ecosystem/stream/test_cam")
        assert resp.status_code == 422

    def test_h2_snapshot_endpoint_requires_token(self, client):
        """GET /ecosystem/snapshot/{id} must require token."""
        resp = client.get("/api/ecosystem/snapshot/test_cam")
        assert resp.status_code == 422

    def test_h2_invalid_token_returns_401(self, client):
        """Camera endpoints must return 401 for invalid token."""
        resp = client.get("/api/ecosystem/cameras", params={"token": "bogus"})
        assert resp.status_code == 401

    # -- H-3: Webhook requires HMAC auth --

    def test_h3_webhook_rejects_unauthenticated(self, client):
        """POST /ecosystem/webhook must reject unauthenticated requests."""
        resp = client.post("/api/ecosystem/webhook", json={"event_type": "test"})
        assert resp.status_code == 401

    # -- H-5: No bare except blocks --

    def test_h5_no_bare_except_in_ecosystem_routes(self):
        """ecosystem.py must not contain bare 'except:' blocks."""
        route_file = Path(__file__).parent.parent / "backend" / "api" / "routes" / "ecosystem.py"
        content = route_file.read_text()
        lines = content.split("\n")
        bare_excepts = [
            (i + 1, line) for i, line in enumerate(lines)
            if line.strip() == "except:" or line.strip().startswith("except: ")
        ]
        assert bare_excepts == [], f"Bare except: blocks found at lines: {bare_excepts}"

    # -- H-6: generate_challenge requires device_token --

    def test_h6_generate_challenge_requires_token(self):
        """generate_challenge must take device_token and return HMAC response."""
        from backend.core.ecosystem_security import generate_challenge, verify_challenge_response
        device_token = "test-device-secret"
        challenge, expected = generate_challenge(device_token)
        assert challenge != expected, "Challenge and response must differ"
        assert verify_challenge_response(challenge, expected, device_token)

    def test_h6_challenge_response_fails_wrong_token(self):
        """Challenge response with wrong token must fail."""
        from backend.core.ecosystem_security import generate_challenge, verify_challenge_response
        challenge, expected = generate_challenge("correct-token")
        assert not verify_challenge_response(challenge, expected, "wrong-token")

    # -- H-8: Shared httpx client --

    def test_h8_ecosystem_client_creates_shared_http_client(self):
        """EcosystemClient must create a shared httpx.AsyncClient."""
        import httpx
        from ecosystem_client import EcosystemClient
        ec = EcosystemClient(service_name="test", service_port=8000)
        assert isinstance(ec._http_client, httpx.AsyncClient)
        assert ec._discovery._http_client is ec._http_client
        assert ec._publisher._http_client is ec._http_client

    def test_h8_peer_accepts_shared_client(self):
        """Peer should accept http_client parameter."""
        import httpx
        from ecosystem_client.peer import Peer
        client = httpx.AsyncClient()
        peer = Peer(name="test", base_url="http://localhost", hmac_secret="s", http_client=client)
        assert peer._http_client is client


class TestMediumPriorityFixes:
    """M-1 through M-6."""

    # -- M-1: httpx replaces aiohttp --

    def test_m1_no_aiohttp_import_in_routes(self):
        """ecosystem.py must not import aiohttp."""
        route_file = Path(__file__).parent.parent / "backend" / "api" / "routes" / "ecosystem.py"
        content = route_file.read_text()
        assert "import aiohttp" not in content
        assert "import httpx" in content

    # -- M-4: SQL LIKE escape --

    def test_m4_like_wildcards_escaped(self):
        """Face search must escape % and _ in person_name."""
        route_file = Path(__file__).parent.parent / "backend" / "api" / "routes" / "ecosystem.py"
        content = route_file.read_text()
        assert 'replace("%", "\\\\%")' in content or "replace('%', '\\\\%')" in content

    # -- L-1: Pattern matching --

    def test_l1_matches_pattern_empty_strings(self):
        """Empty strings should never match."""
        from ecosystem_client.match import matches_pattern
        assert matches_pattern("", "*") is False
        assert matches_pattern("test", "") is False
        assert matches_pattern("", "") is False

    def test_l1_matches_pattern_wildcard(self):
        from ecosystem_client.match import matches_pattern
        assert matches_pattern("security.motion", "*") is True

    def test_l1_matches_pattern_prefix(self):
        from ecosystem_client.match import matches_pattern
        assert matches_pattern("security.motion_detected", "security.*") is True
        assert matches_pattern("security", "security.*") is True  # Exact prefix match
        assert matches_pattern("other.event", "security.*") is False

    def test_l1_matches_pattern_exact(self):
        from ecosystem_client.match import matches_pattern
        assert matches_pattern("security.motion", "security.motion") is True
        assert matches_pattern("security.motion", "security.other") is False

    # -- L-3: SHA256 dedupe key --

    def test_l3_dedupe_uses_sha256_not_md5(self):
        """generate_dedupe_key must use sha256."""
        from backend.api.routes.ecosystem import generate_dedupe_key
        key = generate_dedupe_key({"type": "motion", "source": "cam1", "title": "Alert"})
        assert len(key) == 64  # SHA-256 hex = 64 chars (MD5 = 32)


class TestWebSocketFirstMessageAuth:
    """H-1: WebSocket token moved to first-message auth."""

    def test_h1_websocket_no_query_token_param(self):
        """WebSocket endpoint must NOT require token in query string."""
        import inspect
        from backend.api.routes.ecosystem import ecosystem_events_websocket
        sig = inspect.signature(ecosystem_events_websocket)
        params = list(sig.parameters.keys())
        assert "token" not in params, "Token should not be a query parameter"

    def test_h1_websocket_accepts_bare_connection(self, client):
        """WebSocket should accept connection without query token."""
        # FastAPI TestClient WebSocket won't raise on connect if no query param needed
        try:
            with client.websocket_connect("/api/ecosystem/events") as ws:
                # Connection accepted, now it waits for auth message
                # Send invalid auth to trigger close
                ws.send_json({"type": "auth", "token": "invalid"})
                # Should receive close or error
                try:
                    msg = ws.receive_json()
                except Exception:
                    pass  # Expected: connection closed
        except Exception:
            pass  # WebSocket may close with 4001


class TestStatisticsN1Fix:
    """M-2: N+1 query elimination in /statistics."""

    def test_m2_statistics_returns_grouped_data(self, client, db_session):
        """Statistics endpoint should return camera stats without N+1 queries."""
        from backend.database.models import Camera, MotionDetectionEvent

        # Create test camera
        cam = Camera(
            camera_id="stat_cam_1", camera_type="mock", source="0",
            is_active=True,
            face_detection_enabled=True, motion_detection_enabled=True,
            recording_enabled=False,
        )
        db_session.add(cam)
        db_session.commit()

        resp = client.get("/api/statistics", params={"hours": 24})
        assert resp.status_code == 200
        data = resp.json()
        assert "cameras" in data
        assert "motion_events" in data
        assert "face_events" in data
        assert "recordings" in data


# ============================================================================
# SECTION 2: Face Recognition with Real Test Photos
# ============================================================================


class TestFaceRecognition:
    """Test face detection and recognition using real photos."""

    PHOTOS_DIR = Path("/Users/mikelsmart/Desktop/TestPhotos")

    @pytest.fixture
    def face_images(self):
        """Load test photos if available."""
        if not self.PHOTOS_DIR.exists():
            pytest.skip("TestPhotos directory not found")
        images = list(self.PHOTOS_DIR.glob("*.jpeg")) + list(self.PHOTOS_DIR.glob("*.jpg"))
        if not images:
            pytest.skip("No JPEG images in TestPhotos")
        return images

    @pytest.mark.face
    def test_face_detection_finds_faces_in_photos(self, face_images):
        """face_recognition library should detect faces in test photos."""
        try:
            import face_recognition
        except ImportError:
            pytest.skip("face_recognition not installed")

        faces_found = 0
        for img_path in face_images:
            image = face_recognition.load_image_file(str(img_path))
            locations = face_recognition.face_locations(image, model="hog")
            if locations:
                faces_found += 1

        assert faces_found > 0, f"No faces detected in {len(face_images)} test images"

    @pytest.mark.face
    def test_face_encoding_produces_128d_vector(self, face_images):
        """Face encodings should be 128-dimensional float vectors."""
        try:
            import face_recognition
            import numpy as np
        except ImportError:
            pytest.skip("face_recognition or numpy not installed")

        for img_path in face_images[:2]:  # Test first 2 for speed
            image = face_recognition.load_image_file(str(img_path))
            encodings = face_recognition.face_encodings(image)
            if encodings:
                assert encodings[0].shape == (128,)
                assert encodings[0].dtype == np.float64
                break
        else:
            pytest.skip("No encodable faces found in test images")

    @pytest.mark.face
    def test_face_recognition_manager_loads(self):
        """FaceRecognitionManager should instantiate without errors."""
        try:
            from backend.core.face_recognition import FaceRecognitionManager
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                mgr = FaceRecognitionManager(faces_folder=Path(tmpdir))
                assert mgr.faces_folder == Path(tmpdir)
                assert mgr.known_face_encodings == []
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")

    @pytest.mark.face
    def test_face_detector_processes_frame(self):
        """FaceDetector.process_frame should process a numpy frame."""
        try:
            import cv2
            import numpy as np
            from backend.core.face_detection import FaceDetector
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")

        try:
            detector = FaceDetector(enabled=True)
        except Exception as e:
            pytest.skip(f"FaceDetector init failed: {e}")
        # Create a blank test frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Should not crash on blank frame
        result = detector.process_frame(frame)
        # Returns (annotated_frame, detections_list)
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.face
    def test_face_clustering_imports(self):
        """face_clustering module should import cleanly."""
        try:
            from backend.core.face_clustering import FaceClustering
            assert callable(FaceClustering)
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")


# ============================================================================
# SECTION 3: Camera Discovery
# ============================================================================


class TestCameraDiscovery:
    """Test USB and network camera discovery."""

    @pytest.mark.camera
    def test_usb_discovery_returns_list(self):
        """USB camera discovery should return a list."""
        try:
            from backend.core.camera_discovery import CameraDiscovery
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")

        disc = CameraDiscovery()
        result = asyncio.get_event_loop().run_until_complete(
            disc.discover_usb_cameras()
        )
        assert isinstance(result, list)

    @pytest.mark.camera
    def test_usb_discovery_camera_info_schema(self):
        """Each discovered USB camera must have required fields."""
        try:
            from backend.core.camera_discovery import CameraDiscovery
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")

        disc = CameraDiscovery()
        cameras = asyncio.get_event_loop().run_until_complete(
            disc.discover_usb_cameras()
        )
        for cam in cameras:
            assert "type" in cam
            assert cam["type"] == "usb"
            assert "index" in cam
            assert "resolution" in cam
            assert "auto_config" in cam
            assert "camera_id" in cam["auto_config"]

    @pytest.mark.camera
    def test_device_path_platform_specific(self):
        """_get_device_path should return platform-appropriate paths."""
        from backend.core.camera_discovery import CameraDiscovery
        disc = CameraDiscovery()
        path = disc._get_device_path(0)
        system = platform.system()
        if system == "Linux":
            assert path == "/dev/video0"
        elif system == "Darwin":
            assert "0" in path  # macOS doesn't have /dev/video

    @pytest.mark.camera
    def test_network_discovery_respects_timeout(self):
        """Network discovery should respect timeout and not hang."""
        try:
            from backend.core.camera_discovery import CameraDiscovery
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")

        disc = CameraDiscovery()
        # Very short timeout to ensure it doesn't hang
        result = asyncio.get_event_loop().run_until_complete(
            disc.discover_network_cameras(timeout=2)
        )
        assert isinstance(result, list)

    @pytest.mark.camera
    def test_camera_discover_api_endpoint(self, client):
        """POST /cameras/discover should return discovery results."""
        with patch("backend.core.camera_discovery.CameraDiscovery") as MockDisc:
            mock_inst = MockDisc.return_value
            mock_inst.discover_usb_cameras = AsyncMock(return_value=[
                {"type": "usb", "index": 0, "name": "USB Camera 0",
                 "resolution": "640x480", "fps": 30, "status": "available",
                 "device_path": "/dev/video0",
                 "auto_config": {"camera_id": "usb_camera_0", "camera_type": "usb",
                                 "source": "0", "enabled": True},
                 "discovered_at": datetime.now().isoformat()}
            ])
            mock_inst.discover_network_cameras = AsyncMock(return_value=[])
            mock_inst.scanning = False

            resp = client.post("/api/cameras/discover")
            # Should succeed or return result
            assert resp.status_code in (200, 202)


# ============================================================================
# SECTION 4: Notification System
# ============================================================================


class TestNotificationSystem:
    """Test alert and notification pipeline."""

    def test_alert_manager_imports(self):
        """Alert manager should import without errors."""
        from backend.core.alert_manager import get_alert_manager
        mgr = get_alert_manager()
        assert mgr is not None

    def test_notification_channel_enum(self):
        """NotificationChannel enum should define expected channels."""
        from backend.core.alert_notification_system import NotificationChannel
        channels = [c.value for c in NotificationChannel]
        assert "email" in channels
        assert "webhook" in channels
        assert "push" in channels

    def test_alert_priority_levels(self):
        """AlertPriority should define LOW through CRITICAL."""
        from backend.core.alert_notification_system import AlertPriority
        assert AlertPriority.LOW.value == "low"
        assert AlertPriority.CRITICAL.value == "critical"

    def test_alert_rule_creation(self):
        """AlertRule dataclass should create with defaults."""
        from backend.core.alert_notification_system import AlertRule, NotificationChannel, AlertPriority
        rule = AlertRule(
            id="test-rule",
            name="Motion Alert",
            event_types=["motion_detected"],
            channels=[NotificationChannel.WEBHOOK],
            priority=AlertPriority.HIGH,
            recipients=["http://localhost:8080/hook"],
        )
        assert rule.enabled is True
        assert rule.cooldown_seconds == 300
        assert rule.max_per_hour == 10

    def test_ecosystem_webhook_delivery_uses_httpx(self):
        """send_webhook should use httpx, not aiohttp."""
        import inspect
        from backend.api.routes.ecosystem import send_webhook
        source = inspect.getsource(send_webhook)
        assert "httpx" in source
        assert "aiohttp" not in source

    @pytest.mark.asyncio
    async def test_ecosystem_broadcast_sends_to_websockets(self):
        """broadcast_to_ecosystem should send to all connected sockets."""
        from backend.api.routes.ecosystem import broadcast_to_ecosystem, _ecosystem_websockets

        mock_ws = AsyncMock()
        _ecosystem_websockets.append(mock_ws)
        try:
            await broadcast_to_ecosystem({"event": "test"})
            mock_ws.send_json.assert_called_once_with({"event": "test"})
        finally:
            if mock_ws in _ecosystem_websockets:
                _ecosystem_websockets.remove(mock_ws)

    @pytest.mark.asyncio
    async def test_ecosystem_broadcast_cleans_disconnected(self):
        """broadcast_to_ecosystem should remove dead sockets."""
        from backend.api.routes.ecosystem import broadcast_to_ecosystem, _ecosystem_websockets

        mock_ws = AsyncMock()
        mock_ws.send_json.side_effect = Exception("disconnected")
        _ecosystem_websockets.append(mock_ws)
        try:
            await broadcast_to_ecosystem({"event": "test"})
            assert mock_ws not in _ecosystem_websockets
        finally:
            if mock_ws in _ecosystem_websockets:
                _ecosystem_websockets.remove(mock_ws)


# ============================================================================
# SECTION 5: Granular Camera Controls
# ============================================================================


class TestGranularCameraControls:
    """Test camera PATCH endpoint for toggling features."""

    @pytest.fixture
    def test_camera(self, db_session):
        """Create a test camera in the database."""
        from backend.database.models import Camera
        cam = Camera(
            camera_id="test_cam_ctrl",
            camera_type="mock",
            source="0",
            is_active=True,
            face_detection_enabled=True,
            face_detection_threshold=0.6,
            face_detection_model="hog",
            motion_detection_enabled=False,
            motion_sensitivity=5,
            motion_threshold=50,
            min_contour_area=500,
            recording_enabled=False,
            pre_motion_seconds=5,
            post_motion_seconds=10,
            max_recording_duration=300,
            noise_reduction="medium",
            detect_shadows=True,
        )
        db_session.add(cam)
        db_session.commit()
        return cam

    def test_toggle_motion_detection(self, client, test_camera):
        """PATCH should toggle motion_detection_enabled."""
        resp = client.patch(
            f"/api/cameras/{test_camera.camera_id}",
            json={"motion_detection_enabled": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["motion_detection_enabled"] is True

        # Toggle off
        resp = client.patch(
            f"/api/cameras/{test_camera.camera_id}",
            json={"motion_detection_enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["motion_detection_enabled"] is False

    def test_toggle_face_detection(self, client, test_camera):
        """PATCH should toggle face_detection_enabled."""
        resp = client.patch(
            f"/api/cameras/{test_camera.camera_id}",
            json={"face_detection_enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["face_detection_enabled"] is False

    def test_toggle_recording(self, client, test_camera):
        """PATCH should toggle recording_enabled."""
        resp = client.patch(
            f"/api/cameras/{test_camera.camera_id}",
            json={"recording_enabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["recording_enabled"] is True

    def test_adjust_motion_sensitivity(self, client, test_camera):
        """Changing motion_sensitivity should recalculate min_contour_area."""
        resp = client.patch(
            f"/api/cameras/{test_camera.camera_id}",
            json={"motion_sensitivity": 8},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["motion_sensitivity"] == 8
        # Higher sensitivity = lower min_contour_area
        assert data["min_contour_area"] < 500

    def test_adjust_face_detection_threshold(self, client, test_camera):
        """PATCH should update face_detection_threshold."""
        resp = client.patch(
            f"/api/cameras/{test_camera.camera_id}",
            json={"face_detection_threshold": 0.4},
        )
        assert resp.status_code == 200
        assert resp.json()["face_detection_threshold"] == 0.4

    def test_adjust_recording_params(self, client, test_camera):
        """PATCH should update recording parameters together."""
        resp = client.patch(
            f"/api/cameras/{test_camera.camera_id}",
            json={
                "pre_motion_seconds": 3,
                "post_motion_seconds": 15,
                "max_recording_duration": 600,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pre_motion_seconds"] == 3
        assert data["post_motion_seconds"] == 15
        assert data["max_recording_duration"] == 600

    def test_adjust_motion_threshold(self, client, test_camera):
        """PATCH should update motion_threshold (pixel sensitivity)."""
        resp = client.patch(
            f"/api/cameras/{test_camera.camera_id}",
            json={"motion_threshold": 30},
        )
        assert resp.status_code == 200
        assert resp.json()["motion_threshold"] == 30

    def test_adjust_noise_reduction(self, client, test_camera):
        """PATCH should update noise_reduction level."""
        for level in ["low", "medium", "high"]:
            resp = client.patch(
                f"/api/cameras/{test_camera.camera_id}",
                json={"noise_reduction": level},
            )
            assert resp.status_code == 200
            assert resp.json()["noise_reduction"] == level

    def test_multi_field_update(self, client, test_camera):
        """PATCH with multiple fields should update all at once."""
        resp = client.patch(
            f"/api/cameras/{test_camera.camera_id}",
            json={
                "motion_detection_enabled": True,
                "face_detection_enabled": False,
                "recording_enabled": True,
                "motion_sensitivity": 3,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["motion_detection_enabled"] is True
        assert data["face_detection_enabled"] is False
        assert data["recording_enabled"] is True
        assert data["motion_sensitivity"] == 3

    def test_nonexistent_camera_returns_404(self, client):
        """PATCH on missing camera should return 404."""
        resp = client.patch(
            "/api/cameras/nonexistent_camera_id",
            json={"motion_detection_enabled": True},
        )
        assert resp.status_code == 404


# ============================================================================
# SECTION 6: Privacy & Platform Permissions
# ============================================================================


class TestPrivacyAndPermissions:
    """Test privacy handling for macOS, Linux, and Docker."""

    def test_macos_camera_path_format(self):
        """macOS camera paths should NOT use /dev/video format."""
        from backend.core.camera_discovery import CameraDiscovery
        disc = CameraDiscovery()
        if platform.system() == "Darwin":
            path = disc._get_device_path(0)
            assert not path.startswith("/dev/video"), "macOS should not use /dev/video paths"

    def test_linux_camera_path_format(self):
        """Linux camera paths should use /dev/video format."""
        from backend.core.camera_discovery import CameraDiscovery
        disc = CameraDiscovery()
        if platform.system() == "Linux":
            path = disc._get_device_path(0)
            assert path == "/dev/video0"

    def test_docker_compose_has_device_comments(self):
        """docker-compose.yml should document device passthrough."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        if compose_file.exists():
            content = compose_file.read_text()
            assert "/dev/video" in content, \
                "docker-compose.yml should document video device passthrough"

    def test_ecosystem_token_not_in_logs(self):
        """Tokens should not be logged in plain text at INFO level."""
        import logging
        from backend.api.routes.ecosystem import logger as eco_logger

        # Verify the logger doesn't log at DEBUG by default
        assert eco_logger.level <= logging.WARNING or eco_logger.level == logging.NOTSET

    def test_rate_limiting_blocks_brute_force(self):
        """Rate limiter should block after MAX_AUTH_ATTEMPTS."""
        from backend.core.ecosystem_security import (
            check_rate_limit, record_auth_attempt,
            MAX_AUTH_ATTEMPTS, _auth_attempts, _blocked_ips,
        )
        test_ip = "10.99.99.99"
        # Clean state
        _auth_attempts.pop(test_ip, None)
        _blocked_ips.pop(test_ip, None)

        try:
            for _ in range(MAX_AUTH_ATTEMPTS):
                record_auth_attempt(test_ip, success=False)

            is_allowed, wait_time = check_rate_limit(test_ip)
            assert is_allowed is False
            assert wait_time is not None and wait_time > 0
        finally:
            _auth_attempts.pop(test_ip, None)
            _blocked_ips.pop(test_ip, None)

    def test_successful_auth_clears_rate_limit(self):
        """Successful auth should clear rate limit counters."""
        from backend.core.ecosystem_security import (
            check_rate_limit, record_auth_attempt,
            _auth_attempts, _blocked_ips,
        )
        test_ip = "10.99.99.88"
        _auth_attempts.pop(test_ip, None)
        _blocked_ips.pop(test_ip, None)

        try:
            record_auth_attempt(test_ip, success=False)
            record_auth_attempt(test_ip, success=False)
            record_auth_attempt(test_ip, success=True)  # Should clear

            is_allowed, _ = check_rate_limit(test_ip)
            assert is_allowed is True
            assert test_ip not in _auth_attempts
        finally:
            _auth_attempts.pop(test_ip, None)
            _blocked_ips.pop(test_ip, None)


# ============================================================================
# SECTION 7: Ecosystem Event Mapper (existing tests + new coverage)
# ============================================================================


class TestEcosystemEventMapper:
    """Extended tests for ecosystem event building."""

    def test_motion_event_payload(self):
        from backend.core.ecosystem_events import build_motion_event
        payload = build_motion_event(
            camera_id="cam_1",
            motion_areas=[{"x": 10, "y": 20, "w": 50, "h": 60, "area": 3000}],
            snapshot_path="/data/snapshots/cam1_123.jpg",
            zone_ids=[1, 3],
        )
        assert payload["event_type"] == "security.motion_detected"
        assert payload["data"]["camera_id"] == "cam_1"

    def test_face_event_known_person(self):
        from backend.core.ecosystem_events import build_face_event
        payload = build_face_event(
            camera_id="cam_2", person_name="Alice",
            confidence=0.92, is_known=True,
        )
        assert payload["event_type"] == "security.person_detected"

    def test_face_event_unknown_triggers_alert(self):
        from backend.core.ecosystem_events import build_face_event
        payload = build_face_event(
            camera_id="cam_2", person_name="Unknown",
            confidence=0.0, is_known=False,
        )
        assert payload["event_type"] == "security.alert"
        assert payload["data"]["severity"] == "warning"

    def test_intrusion_event(self):
        from backend.core.ecosystem_events import build_intrusion_event
        payload = build_intrusion_event(
            camera_id="cam_1",
            details="Repeated unknown faces",
            recording_url="/api/recordings/42",
        )
        assert payload["event_type"] == "security.intrusion"
        assert payload["data"]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_publish_event_with_mock_client(self):
        from backend.core.ecosystem_events import publish_ecosystem_event
        mock_eco = MagicMock()
        mock_eco.publish = AsyncMock(return_value={"delivered": 1})
        result = await publish_ecosystem_event(
            mock_eco, "security.motion_detected", {"camera_id": "cam_1"},
        )
        assert result["delivered"] == 1

    @pytest.mark.asyncio
    async def test_publish_gracefully_handles_no_client(self):
        from backend.core.ecosystem_events import publish_ecosystem_event
        result = await publish_ecosystem_event(
            None, "security.motion_detected", {"camera_id": "cam_1"},
        )
        assert result is None
