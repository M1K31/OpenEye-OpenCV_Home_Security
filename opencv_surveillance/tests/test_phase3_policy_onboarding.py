"""Unit tests for OpenEye Phase 3 PolicyEngine, AUP onboarding consent, and step-up auth."""
from __future__ import annotations

import os
import pytest
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient

from backend.api.routes import ecosystem
from backend.core.ecosystem_hub_bridge import (
    _ensure_ecosystem_paths,
    get_approval_queue,
    get_onboarding_consent,
    get_policy_engine,
    get_step_up_auth,
    record_onboarding_consent,
    reset_policy_singletons,
    resolve_ui_asset_path,
)

# Test app isolating ecosystem and UI routes without heavy native dependencies
test_app = FastAPI()
test_app.include_router(ecosystem.router, prefix="/api")


@test_app.get("/ui/{asset_name}", include_in_schema=False)
async def get_ui_asset(asset_name: str):
    path = resolve_ui_asset_path(asset_name)
    if path is None:
        raise HTTPException(status_code=404, detail="UI asset not found")
    media_type = "application/javascript" if asset_name.endswith(".js") else "text/css"
    return FileResponse(str(path), media_type=media_type)


@pytest.fixture(autouse=True)
def clean_policy_state(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENEYE_POLICY_DIR", str(tmp_path / "policy"))
    monkeypatch.setenv("OPENEYE_STEP_UP_PATH", str(tmp_path / "policy" / "step_up.json"))
    monkeypatch.setenv("ECOSYSTEM_SECRET", "test-secret-" + "a" * 32)
    reset_policy_singletons()
    yield
    reset_policy_singletons()


def test_onboarding_consent_requires_aup_for_scanning():
    # Invariant: silence or omission never creates scan consent.
    # Designating auto_scan without AUP acceptance must raise PermissionError.
    with pytest.raises(PermissionError, match="Acceptable Use Policy"):
        record_onboarding_consent(
            owner="admin",
            aup_accepted=False,
            designate_auto_scan=True,
        )

    # With AUP accepted, enrollment and auto_scan grant succeed
    rec = record_onboarding_consent(
        owner="admin",
        hub_role="auto",
        aup_accepted=True,
        aup_version="1.0",
        baseline_self_scan=True,
        designate_auto_scan=True,
        auto_scan_profiles=["quick"],
        device_id="openeye-test-node",
    )
    assert rec["aup_accepted"] is True
    assert rec["designate_auto_scan"] is True
    assert rec["device_id"] == "openeye-test-node"
    assert rec["enrollment"] is not None
    assert rec["auto_scan_grant"] is not None

    stored = get_onboarding_consent()
    assert stored["aup_accepted"] is True
    assert stored["owner"] == "admin"

    # PolicyEngine has valid auto scan grant
    engine = get_policy_engine()
    ok, msg = engine.has_valid_auto_scan_grant("openeye-test-node", profile="quick")
    assert ok is True


def test_freeze_and_step_up_resume():
    engine = get_policy_engine()
    step_up = get_step_up_auth()

    # Freeze engages immediately
    state_frozen = engine.freeze(initiated_by="camera_tamper_detector", reason="Physical tampering detected")
    assert state_frozen["frozen"] is True
    assert engine.frozen is True

    # Resuming without step-up auth method raises PermissionError
    with pytest.raises(PermissionError):
        engine.resume(operator_id="admin", auth_method="password")

    # Resuming with TOTP step-up succeeds
    state_resumed = engine.resume(operator_id="admin", auth_method="totp")
    assert state_resumed["frozen"] is False
    assert engine.frozen is False


def test_unified_approvals_mirroring():
    queue = get_approval_queue()
    appr = queue.request_approval(
        requester_service="openeye",
        actor="operator",
        action="camera:calibrate",
        action_class="system_change",
        target={"camera_id": "front_door"},
        summary="Recalibrate PTZ limits on front door camera",
    )
    assert appr["status"] == "pending"
    approval_id = appr["approval_id"]

    pending = queue.list_approvals(status="pending")
    assert any(a["approval_id"] == approval_id for a in pending)

    # Step-up enroll and verify
    step_up = get_step_up_auth()
    enrolled = step_up.enroll_totp("admin")
    secret = enrolled["secret"]

    _ensure_ecosystem_paths()
    from ecosystem_policy import compute_totp

    code = compute_totp(secret)
    token_data = step_up.verify_totp_and_issue_token("admin", code)
    assert token_data is not None
    token = token_data["step_up_token"]

    approved = queue.approve(
        approval_id,
        step_up_token=token,
        resolved_by="admin",
        auth_method="totp",
        note="Approved camera calibration",
    )
    assert approved["status"] == "approved"
    assert approved["resolved_by"] == "admin"


def test_ui_assets_endpoint():
    client = TestClient(test_app)
    res_css = client.get("/ui/ecosystem-theme.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("content-type", "")

    res_js = client.get("/ui/ecosystem-ui-controls.js")
    assert res_js.status_code == 200
    assert "javascript" in res_js.headers.get("content-type", "")


def test_onboarding_consent_endpoint():
    client = TestClient(test_app)
    res = client.get("/api/ecosystem/onboarding/consent")
    assert res.status_code == 200
    data = res.json()
    assert "aup_accepted" in data
    assert "device_id" in data
