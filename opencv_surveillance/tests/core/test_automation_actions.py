"""Tests for automation-engine action executors."""
from unittest.mock import MagicMock, patch

from backend.core import automation_engine as ae


def test_notification_action_dispatches_with_targeting_and_cooldown():
    with patch("backend.core.notification_dispatch.dispatch_from_thread",
               return_value=True) as bridge:
        result = ae.execute_notification_action(
            {"message": "John at the door", "priority": "high",
             "providers": ["telegram"], "cooldown_seconds": 120},
            person_name="John", camera_id="front_door", rule_id=7)
    assert result["success"] is True and result["queued"] is True
    kwargs = bridge.call_args.kwargs
    assert kwargs["message"] == "John at the door"
    assert kwargs["priority"] == "high"
    assert kwargs["target_providers"] == ["telegram"]
    assert kwargs["cooldown_seconds"] == 120
    assert kwargs["cooldown_key"] == ("rule", 7, "front_door", "John")


def test_notification_action_defaults():
    with patch("backend.core.notification_dispatch.dispatch_from_thread",
               return_value=True) as bridge:
        result = ae.execute_notification_action({}, "Jane", "cam2")
    kwargs = bridge.call_args.kwargs
    assert kwargs["cooldown_seconds"] == 0          # opt-in
    assert kwargs["target_providers"] is None        # fan out
    assert "Jane" in kwargs["message"]
    assert result["success"] is True


def test_notification_action_no_loop_reports_failure():
    with patch("backend.core.notification_dispatch.dispatch_from_thread",
               return_value=False):
        result = ae.execute_notification_action({}, "Jane", "cam2")
    assert result["success"] is False and result["queued"] is False


import time as _time


def test_record_action_requests_recording_on_running_camera():
    fake_cam = MagicMock()
    fake_mgr = MagicMock()
    fake_mgr.get_camera.return_value = fake_cam
    with patch("backend.core.camera_manager.CameraManager", return_value=fake_mgr):
        result = ae.execute_record_action({"duration": 45}, "John", "front_door")
    fake_mgr.get_camera.assert_called_once_with("front_door")
    fake_cam.request_recording.assert_called_once_with(45)
    assert result == {"type": "record", "success": True, "camera_id": "front_door",
                      "duration": 45, "recording_requested": True}


def test_record_action_camera_not_running():
    fake_mgr = MagicMock()
    fake_mgr.get_camera.return_value = None
    with patch("backend.core.camera_manager.CameraManager", return_value=fake_mgr):
        result = ae.execute_record_action({}, "John", "ghost_cam")
    assert result["success"] is False
    assert "not running" in result["error"]


def test_camera_request_recording_sets_window():
    from backend.core.camera_manager import MockCamera
    cam = MockCamera.__new__(MockCamera)   # skip heavy __init__
    cam.manual_record_until = 0.0
    from backend.core.camera_manager import Camera
    Camera.request_recording(cam, 30)
    assert cam.manual_record_until > _time.time() + 25
