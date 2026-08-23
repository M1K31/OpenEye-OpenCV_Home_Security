# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
A camera that fails to load at startup must be retried automatically.

Background
----------
Two recovery paths exist and only one was covered. A camera that is running and
then dies is retried by its own capture loop. A camera that fails to open AT
STARTUP has no capture loop at all, so nothing ever retried it — the operator
had to press reconnect by hand.

Observed on 2026-08-22: the server started at 21:27:38 with
`CAMERA STARTUP SUMMARY: 0/1 cameras loaded`, the camera was plugged in
afterwards, and the system sat idle until a human clicked reconnect at 21:31:19.
For an appliance that may boot before its camera is ready — a power cut, a
reboot, a USB hub settling — that is a security system that quietly never starts
watching.

Threading note
--------------
The retry runs on a background thread. main.py warns that opening a camera off
the main thread segfaults on macOS, but the reconnect endpoint is a sync `def`,
which FastAPI runs in a threadpool worker, and it opened a camera successfully
from there on 2026-08-22. The same threading model is used here deliberately.
"""

import time

import pytest

from backend.core.camera_manager import CameraManager


@pytest.fixture
def manager(monkeypatch):
    """A CameraManager with no real cameras and a fast backoff."""
    mgr = CameraManager()
    mgr.cameras = {}
    mgr._pending_cameras = {}
    monkeypatch.setattr(CameraManager, "RETRY_BACKOFF_MIN", 0.01)
    monkeypatch.setattr(CameraManager, "RETRY_BACKOFF_MAX", 0.04)
    return mgr


def test_a_failed_camera_is_recorded_for_retry(manager):
    """A camera that could not be opened at startup must not be forgotten."""
    manager.register_pending_camera(
        camera_id="usb_camera_0", camera_type="usb", source="0",
        enable_face_detection=True, reason="device unavailable",
    )
    assert "usb_camera_0" in manager._pending_cameras


def test_a_pending_camera_is_retried_and_cleared_on_success(manager, monkeypatch):
    """Once the device appears, the camera starts and stops being pending."""
    calls = []

    def _add(camera_id, camera_type, source, enable_face_detection=True, **kw):
        calls.append(camera_id)
        return True, "started"

    monkeypatch.setattr(manager, "add_camera", _add)

    manager.register_pending_camera(
        camera_id="usb_camera_0", camera_type="usb", source="0",
        enable_face_detection=True, reason="device unavailable",
    )
    manager._pending_cameras["usb_camera_0"]["next_attempt"] = 0   # make it due
    assert manager.retry_pending_cameras() == 1
    assert calls == ["usb_camera_0"]
    assert "usb_camera_0" not in manager._pending_cameras, (
        "a camera that started must stop being retried"
    )


def test_a_still_absent_camera_stays_pending_and_backs_off(manager, monkeypatch):
    """Retrying an absent camera must not become a spin loop."""
    attempts = {"n": 0}

    def _add(**kw):
        attempts["n"] += 1
        return False, "device unavailable"

    monkeypatch.setattr(manager, "add_camera", _add)

    manager.register_pending_camera(
        camera_id="usb_camera_0", camera_type="usb", source="0",
        enable_face_detection=True, reason="device unavailable",
    )

    manager._pending_cameras["usb_camera_0"]["next_attempt"] = 0   # make it due
    manager.retry_pending_cameras()
    assert attempts["n"] == 1
    assert "usb_camera_0" in manager._pending_cameras

    # Immediately again: the backoff must suppress it.
    manager.retry_pending_cameras()
    assert attempts["n"] == 1, "backoff did not suppress an immediate retry"

    backoff_before = manager._pending_cameras["usb_camera_0"]["backoff"]
    time.sleep(0.05)
    manager.retry_pending_cameras()
    assert attempts["n"] == 2
    assert manager._pending_cameras["usb_camera_0"]["backoff"] > backoff_before, (
        "backoff should grow between failed attempts"
    )


def test_backoff_is_capped(manager, monkeypatch):
    """An absent camera settles at a steady, cheap retry interval."""
    monkeypatch.setattr(manager, "add_camera", lambda **kw: (False, "nope"))
    manager.register_pending_camera(
        camera_id="usb_camera_0", camera_type="usb", source="0",
        enable_face_detection=True, reason="unavailable",
    )
    for _ in range(10):
        manager._pending_cameras["usb_camera_0"]["next_attempt"] = 0
        manager.retry_pending_cameras()
    assert manager._pending_cameras["usb_camera_0"]["backoff"] <= CameraManager.RETRY_BACKOFF_MAX


def test_an_already_running_camera_is_never_retried(manager, monkeypatch):
    """
    Guard against reopening a camera that recovered by another route.

    The operator can click reconnect, which starts the camera through a
    different path. Retrying it afterwards would open a second capture on the
    same device.
    """
    monkeypatch.setattr(manager, "add_camera",
                        lambda **kw: pytest.fail("must not reopen a running camera"))

    manager.register_pending_camera(
        camera_id="usb_camera_0", camera_type="usb", source="0",
        enable_face_detection=True, reason="unavailable",
    )

    class _Running:
        is_running = True

    manager.cameras["usb_camera_0"] = _Running()
    assert manager.retry_pending_cameras() == 0
    assert "usb_camera_0" not in manager._pending_cameras


def test_the_first_retry_is_not_immediate(manager, monkeypatch):
    """
    Startup has just spent ~16s probing this device across 8 attempts, so an
    instant retry would only repeat a known failure. The first attempt waits for
    the minimum backoff; only then does retrying make sense.
    """
    monkeypatch.setattr(manager, "add_camera",
                        lambda **kw: pytest.fail("retried before the backoff elapsed"))
    manager.register_pending_camera(
        camera_id="usb_camera_0", camera_type="usb", source="0",
        enable_face_detection=True, reason="unavailable",
    )
    assert manager.retry_pending_cameras() == 0
