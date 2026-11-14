"""PTZ connect must not exfiltrate stored camera credentials to an arbitrary host.

Security review of PR #8: when the caller overrode camera_ip, the stored
credentials were still used, so a request could point the connect at any host
and have the camera's password sent there (SSRF / credential exfiltration).
"""
import pytest

from backend.database import crud
from backend.api.routes import ptz as ptz_routes


@pytest.fixture
def ptz_camera(db_session):
    return crud.create_camera(db_session, {
        "camera_id": "cam-ptz-1",
        "camera_type": "rtsp",
        "source": "rtsp://camuser:campass@192.168.1.50:554/stream",
    })


@pytest.fixture
def fake_controller(monkeypatch):
    class _Ctrl:
        def __init__(self):
            self.connect_calls = []
            self.camera_ip = ""
            self.port = 0
            self.active_protocol = "onvif"
            self.vendor_hint = "generic"
            self.device_info = {}
            self.last_error = None

        async def connect(self, *, camera_ip, port, username, password, vendor_hint):
            self.connect_calls.append(
                {"camera_ip": camera_ip, "port": port, "username": username, "password": password}
            )
            self.camera_ip = camera_ip
            return True

        async def get_status(self):
            return {"connected": True}

    ctrl = _Ctrl()
    monkeypatch.setattr(ptz_routes, "get_ptz_controller", lambda *a, **k: ctrl)
    return ctrl


def _connect(client, headers, body):
    return client.post("/api/cameras/cam-ptz-1/ptz/connect", json=body, headers=headers)


def test_no_override_uses_stored_credentials(client, ptz_camera, fake_controller, auth_headers):
    resp = _connect(client, auth_headers, {})
    assert resp.status_code == 200, resp.text
    call = fake_controller.connect_calls[-1]
    assert call["camera_ip"] == "192.168.1.50"
    assert call["username"] == "camuser" and call["password"] == "campass"


def test_viewer_cannot_override_the_host(client, ptz_camera, fake_controller, auth_headers):
    resp = _connect(client, auth_headers, {"camera_ip": "10.0.0.9", "username": "u", "password": "p"})
    assert resp.status_code == 403
    assert fake_controller.connect_calls == []


def test_admin_host_override_requires_request_credentials(client, ptz_camera, fake_controller, admin_auth_headers):
    resp = _connect(client, admin_auth_headers, {"camera_ip": "10.0.0.9"})
    assert resp.status_code == 400
    assert fake_controller.connect_calls == []


def test_admin_host_override_never_sends_stored_credentials(client, ptz_camera, fake_controller, admin_auth_headers):
    resp = _connect(client, admin_auth_headers, {"camera_ip": "10.0.0.9", "username": "newu", "password": "newp"})
    assert resp.status_code == 200, resp.text
    call = fake_controller.connect_calls[-1]
    assert call["camera_ip"] == "10.0.0.9"
    # The stored password must never reach the overridden host.
    assert call["username"] == "newu" and call["password"] == "newp"


def test_same_host_override_is_allowed_without_admin(client, ptz_camera, fake_controller, auth_headers):
    # Supplying the camera's own stored IP is not a host override.
    resp = _connect(client, auth_headers, {"camera_ip": "192.168.1.50"})
    assert resp.status_code == 200, resp.text
    assert fake_controller.connect_calls[-1]["password"] == "campass"
