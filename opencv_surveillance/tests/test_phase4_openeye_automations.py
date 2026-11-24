"""Tests for OpenEye Phase 4 Automations (scan condition, device_scan, and ecosystem_freeze actions)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("ecosystem_policy", reason="appecosystem-policy not installed")
pytest.importorskip("ecosystem_client", reason="appecosystem-client not installed")

from backend.core.automation_engine import (
    evaluate_rule_conditions,
    execute_action,
    execute_ecosystem_freeze_action,
    execute_device_scan_action,
    execute_scan_schedule_action,
)
from backend.core.ecosystem_hub_bridge import (
    get_policy_engine,
    local_device_identity,
    record_onboarding_consent,
    reset_policy_singletons,
)


@pytest.fixture(autouse=True)
def clean_policy_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    policy_dir = tmp_path / "openeye_policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OPENEYE_POLICY_DIR", str(policy_dir))
    monkeypatch.setenv("ECOSYSTEM_DEVICE_ID", "openeye-test-device")
    reset_policy_singletons()
    yield
    reset_policy_singletons()


def test_evaluate_rule_conditions_scan_grant_valid():
    pe = get_policy_engine()
    dev_id, fp = local_device_identity()

    # 1. Without grant, scan_grant_valid condition returns False
    conds = {"scan_grant_valid": {"device_id": dev_id, "profile": "quick"}}
    assert evaluate_rule_conditions(conds) is False

    # 2. Record onboarding consent to grant auto_scan
    record_onboarding_consent(
        owner="admin",
        aup_accepted=True,
        designate_auto_scan=True,
        auto_scan_profiles=["quick"],
    )

    # 3. Now scan_grant_valid evaluates to True
    assert evaluate_rule_conditions(conds) is True


def test_execute_ecosystem_freeze_action():
    pe = get_policy_engine()
    assert pe.frozen is False

    action = {
        "type": "ecosystem_freeze",
        "config": {"reason": "Intruder detected at perimeter"},
    }
    res = execute_action(action, person_name="Unknown Intruder", camera_id="cam_front", db=MagicMock())

    assert res["type"] == "ecosystem_freeze"
    assert res["success"] is True
    assert res["frozen"] is True
    assert pe.frozen is True


def test_execute_device_scan_action():
    pe = get_policy_engine()
    dev_id, _ = local_device_identity()

    # When policy is frozen, device_scan action is denied
    pe.freeze(initiated_by="test", reason="Testing frozen denial")
    action = {
        "type": "device_scan",
        "config": {"device_id": dev_id, "profile": "quick"},
    }
    res = execute_action(action, person_name="Worker", camera_id="cam_office", db=MagicMock())
    assert res["type"] == "device_scan"
    assert res["success"] is False
    assert res["status"] == "denied"

