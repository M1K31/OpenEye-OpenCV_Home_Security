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
