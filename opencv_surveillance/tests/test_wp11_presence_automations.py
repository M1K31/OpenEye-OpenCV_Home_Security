"""WP11 unit tests: OpenEye presence automations, egress safety, TTL/release, consent/cooldown, and Freeze."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

pytest.importorskip("ecosystem_policy", reason="appecosystem-policy not installed")

from backend.core.presence_automations import (
    DoorTarget,
    PresenceAutomationEngine,
    PresenceEvent,
    PresenceRule,
)
from ecosystem_policy import PolicyEngine


class FakeClock:
    def __init__(self, start: float = 10000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeHub:
    def __init__(self):
        self.calls: list[dict] = []

    async def invoke(self, capability: str, target: dict, parameters: dict | None = None, **kwargs):
        self.calls.append({"capability": capability, "target": target, "parameters": parameters or {}})
        return {"status": "completed", "command_id": f"cmd-{len(self.calls)}"}


def test_unknown_person_restricts_zone_protects_egress_and_lifts_on_ttl_and_release(tmp_path: Path):
    clock = FakeClock()
    policy = PolicyEngine(authority="standalone_local", persistence_path=tmp_path / "policy.json")
    door_ops: list[tuple[str, str]] = []
    notifs: list[dict] = []

    async def fake_doors(door_id: str, op: str) -> bool:
        door_ops.append((door_id, op))
        return True

    async def fake_notify(n: dict):
        notifs.append(n)

    engine = PresenceAutomationEngine(
        policy_engine=policy,
        notification_fn=fake_notify,
        door_controller=fake_doors,
        clock=clock,
    )
    engine.register_door(DoorTarget(door_id="office_interior", zone="office", egress=False))
    engine.register_door(DoorTarget(door_id="office_fire_exit", zone="office", egress=True))
    engine.register_door(DoorTarget(door_id="kitchen_door", zone="kitchen", egress=False))

    engine.add_rule(PresenceRule(
        rule_id="rule-office-unknown",
        owner="mikel",
        zone="office",
        person_match="unknown",
        unknown_min_frames=2,
        ttl_seconds=300,
        actions=[{"type": "access.restrict_zone", "ttl_seconds": 300}],
    ))

    # Frame 1: single bad frame does NOT fire yet
    ev1 = PresenceEvent(zone="office", camera_id="cam1", person_name="unknown", snapshot_ref="/host/secret/snap1.jpg")
    r1 = asyncio.run(engine.handle_presence(ev1))
    assert r1[0]["status"] == "awaiting_frames"
    assert door_ops == []

    # Frame 2: confirms unknown -> locks ONLY office_interior; egress door & kitchen untouched
    r2 = asyncio.run(engine.handle_presence(ev1))
    assert r2[0]["status"] == "fired"
    act_res = r2[0]["results"][0]
    assert act_res["doors_locked"] == ["office_interior"]
    assert act_res["egress_skipped"] == ["office_fire_exit"]
    assert ("kitchen_door", "lock") not in door_ops

    # Notification carries zone + deep link, ZERO host snapshot paths
    assert len(notifs) == 1
    notif_json = json.dumps(notifs[0])
    assert "office" in notif_json
    assert "/host/secret/snap1.jpg" not in notif_json

    # Manual one-tap release works even under Emergency Freeze!
    policy.freeze(initiated_by="operator", reason="test freeze")
    rel = asyncio.run(engine.release_zone("office", released_by="operator"))
    assert rel["status"] == "released"
    assert rel["doors_released"] == ["office_interior"]

    # While frozen, new presence events do NOT fire any automation
    policy.freeze(initiated_by="operator", reason="still frozen")
    frozen_res = asyncio.run(engine.handle_presence(ev1))
    assert frozen_res[0]["status"] == "skipped_frozen"

    # Unfreeze and test TTL auto-expiry (after manual release grace passes)
    policy.resume(operator_id="operator", auth_method="totp", reason="clear")
    clock.advance(400)
    asyncio.run(engine.handle_presence(ev1))
    asyncio.run(engine.handle_presence(ev1))
    assert "office" in engine.active_restrictions

    clock.advance(301)
    expired = asyncio.run(engine.expire_due_restrictions())
    assert len(expired) == 1
    assert expired[0]["status"] == "released"
    assert "office" not in engine.active_restrictions


def test_false_unknown_suppression_and_low_confidence_guard(tmp_path: Path):
    clock = FakeClock()
    policy = PolicyEngine(authority="standalone_local", persistence_path=tmp_path / "policy.json")
    engine = PresenceAutomationEngine(policy_engine=policy, clock=clock)
    engine.register_door(DoorTarget(door_id="lab_door", zone="lab"))
    engine.add_rule(PresenceRule(
        rule_id="rule-lab",
        owner="mikel",
        zone="lab",
        person_match="unknown",
        unknown_min_frames=1,
        actions=[{"type": "access.restrict_zone"}],
    ))
    engine.add_rule(PresenceRule(
        rule_id="rule-lights-mikel",
        owner="mikel",
        zone="lab",
        person_match="known:mikel",
        min_confidence=0.80,
        actions=[{"type": "infrastructure.control", "subsystem": "lights", "command": "on"}],
    ))

    # Known person in same zone suppresses Family 1 restriction
    res_known = asyncio.run(engine.handle_presence(
        PresenceEvent(zone="lab", camera_id="cam1", person_name="unknown", known_present_in_zone=True)
    ))
    assert res_known[0]["results"][0]["status"] == "suppressed"
    assert res_known[0]["results"][0]["reason"] == "known_present_in_zone"

    # Guests-expected mode suppresses Family 1 restriction
    engine.set_guests_expected(True)
    res_guest = asyncio.run(engine.handle_presence(
        PresenceEvent(zone="lab", camera_id="cam1", person_name="unknown")
    ))
    assert res_guest[0]["results"][0]["status"] == "suppressed"
    assert res_guest[0]["results"][0]["reason"] == "guests_expected"

    # Low-confidence known match does NOT fire
    res_low_conf = asyncio.run(engine.handle_presence(
        PresenceEvent(zone="lab", camera_id="cam1", person_name="mikel", confidence=0.55)
    ))
    assert res_low_conf[0]["status"] == "below_confidence"


def test_presence_triggered_scan_enforces_consent_approval_and_cooldown(tmp_path: Path):
    clock = FakeClock()
    policy = PolicyEngine(authority="standalone_local", persistence_path=tmp_path / "policy.json")
    hub = FakeHub()
    engine = PresenceAutomationEngine(policy_engine=policy, hub_client=hub, clock=clock)

    # Enroll dev-consent-only (consent YES, standing grant NO)
    policy.enroll_device("dev-consent-only", "fp-1", owner="mikel", aup_version="2.0")
    # Enroll dev-designated (consent YES, standing grant YES)
    policy.enroll_device("dev-designated", "fp-2", owner="mikel", aup_version="2.0")
    policy.designate_auto_scan("dev-designated", profiles=["quick"], initiators=["openeye_presence"])

    engine.add_rule(PresenceRule(
        rule_id="rule-server-room-scans",
        owner="mikel",
        zone="server_room",
        person_match="unknown",
        unknown_min_frames=1,
        cooldown_seconds=1800,
        actions=[
            {"type": "scan.request", "device_id": "visitor-phone", "profile": "quick"},
            {"type": "scan.request", "device_id": "dev-consent-only", "profile": "quick"},
            {"type": "scan.request", "device_id": "dev-designated", "profile": "quick"},
        ],
    ))

    ev = PresenceEvent(zone="server_room", camera_id="cam_sr", person_name="unknown")
    res = asyncio.run(engine.handle_presence(ev))
    results = res[0]["results"]

    # Visitor device with no consent -> awaiting_consent (NOT scanned)
    assert results[0]["status"] == "awaiting_consent"
    # Device with consent but no auto-scan designation -> awaiting_approval (NOT scanned)
    assert results[1]["status"] == "awaiting_approval"
    # Designated device with recorded consent -> scan queued via hub
    assert results[2]["status"] == "scan_queued"
    assert len(hub.calls) == 1
    assert hub.calls[0]["capability"] == "scan.request"
    assert hub.calls[0]["parameters"]["target_device"] == "dev-designated"

    # Immediate re-trigger respects cooldown (does NOT queue a second scan)
    res2 = asyncio.run(engine.handle_presence(ev))
    assert res2[0]["results"][2]["status"] == "cooldown_active"
    assert len(hub.calls) == 1
