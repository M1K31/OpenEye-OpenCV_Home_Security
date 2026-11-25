"""WP11 — OpenEye Presence Automations Engine.

Turns owner-authored presence rules ("who is where") into safe, policy-gated
actions across three families:
1. Restrict access on an unknown person (`access.restrict_zone` / `access.release_zone`)
   - Hard life-safety invariant: NEVER lock an egress or life-safety door
   - Mandatory TTL + one-tap manual release (manual release ALWAYS works, even under Freeze)
   - Multi-frame confirmation (`unknown_min_frames`) + false-unknown lockout suppression
     (known person in zone, recent manual release grace window, or guests-expected mode)
2. Presence-triggered vulnerability scans (`scan.request`)
   - Default is NO scan. Requires BOTH recorded owner consent/AUP acceptance AND
     ecosystem owner approval (standing auto-scan designation or per-run approval)
   - Per-device and per-zone cooldowns
3. Infrastructure by identity (lights, music, climate)

Privacy: notifications carry `"unknown person in <zone>"` + deep link, NEVER raw
face images or host snapshot paths. Under Emergency Freeze, all automations stop
EXCEPT `release_zone`.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

_EGRESS_KEYWORDS: tuple[str, ...] = (
    "egress",
    "fire_exit",
    "fire-exit",
    "emergency_exit",
    "emergency-exit",
    "life_safety",
    "life-safety",
)


@dataclass
class DoorTarget:
    door_id: str
    zone: str
    egress: bool = False
    life_safety: bool = False

    def is_protected_egress(self) -> bool:
        if self.egress or self.life_safety:
            return True
        low = self.door_id.lower()
        return any(kw in low for kw in _EGRESS_KEYWORDS)


@dataclass
class PresenceRule:
    rule_id: str
    owner: str
    zone: str
    person_match: str  # "unknown" | "known:<name>" | "group:<group>"
    actions: list[dict[str, Any]] = field(default_factory=list)
    min_confidence: float = 0.75
    unknown_min_frames: int = 3
    ttl_seconds: int = 900
    cooldown_seconds: int = 1800
    enabled: bool = True


@dataclass
class ActiveRestriction:
    zone: str
    doors_locked: list[str]
    rule_id: str
    created_at: float
    expires_at: float
    released: bool = False
    released_by: str | None = None
    released_at: float | None = None


@dataclass
class PresenceEvent:
    zone: str
    camera_id: str
    person_name: str | None  # None or "unknown" for unrecognised
    person_group: str | None = None
    confidence: float = 0.0
    known_present_in_zone: bool = False
    snapshot_ref: str | None = None  # Kept local on host; NEVER placed in notifications
    timestamp: float = field(default_factory=time.time)


class PresenceAutomationEngine:
    """Evaluates owner-defined WP11 presence rules with hard safety & consent gates."""

    def __init__(
        self,
        *,
        policy_engine: Any = None,
        hub_client: Any = None,
        notification_fn: Callable[[dict[str, Any]], Awaitable[Any]] | None = None,
        door_controller: Callable[[str, str], Awaitable[bool]] | None = None,
        clock: Callable[[], float] = time.time,
        manual_release_grace_seconds: int = 300,
    ):
        self.policy_engine = policy_engine
        self.hub_client = hub_client
        self._notify = notification_fn
        self._door_controller = door_controller
        self._clock = clock
        self.manual_release_grace_seconds = max(30, int(manual_release_grace_seconds))

        self.rules: dict[str, PresenceRule] = {}
        self.doors: dict[str, DoorTarget] = {}
        self.active_restrictions: dict[str, ActiveRestriction] = {}
        self.guests_expected: bool = False
        self.face_consents: dict[str, dict[str, Any]] = {}
        self.firing_log: list[dict[str, Any]] = []

        self._unknown_frame_streaks: dict[str, int] = {}
        self._last_manual_release: dict[str, float] = {}
        self._scan_cooldowns: dict[str, float] = {}

    # ---- Configuration & Consent ----

    def register_door(self, door: DoorTarget) -> None:
        self.doors[door.door_id] = door

    def add_rule(self, rule: PresenceRule) -> None:
        self.rules[rule.rule_id] = rule

    def set_guests_expected(self, enabled: bool) -> None:
        self.guests_expected = bool(enabled)

    def record_face_consent(
        self,
        person_name: str,
        *,
        consented_by: str,
        aup_version: str = "1.0",
    ) -> dict[str, Any]:
        rec = {
            "person_name": person_name,
            "consented_by": consented_by,
            "aup_version": aup_version,
            "recorded_at": self._clock(),
            "revoked": False,
        }
        self.face_consents[person_name] = rec
        return dict(rec)

    def _is_frozen(self) -> bool:
        if self.policy_engine is None:
            return False
        if getattr(self.policy_engine, "frozen", False):
            return True
        if hasattr(self.policy_engine, "export_state"):
            return bool((self.policy_engine.export_state() or {}).get("frozen"))
        return False

    # ---- Zone Restriction & One-Tap Release (Always Allowed Even Under Freeze) ----

    async def restrict_zone(
        self,
        zone: str,
        *,
        rule_id: str,
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        """Lock non-egress doors in `zone` for a bounded TTL. Refuses egress/life-safety doors."""
        if self._is_frozen():
            return {"status": "skipped_frozen", "zone": zone, "doors_locked": [], "egress_skipped": []}

        zone_doors = [d for d in self.doors.values() if d.zone == zone]
        doors_locked: list[str] = []
        egress_skipped: list[str] = []

        for door in zone_doors:
            if door.is_protected_egress():
                egress_skipped.append(door.door_id)
                continue
            ok = True
            if self._door_controller is not None:
                ok = bool(await self._door_controller(door.door_id, "lock"))
            if ok:
                doors_locked.append(door.door_id)

        now = self._clock()
        clamped_ttl = max(60, min(int(ttl_seconds), 86400))
        if doors_locked:
            self.active_restrictions[zone] = ActiveRestriction(
                zone=zone,
                doors_locked=doors_locked,
                rule_id=rule_id,
                created_at=now,
                expires_at=now + clamped_ttl,
            )
        return {
            "status": "restricted" if doors_locked else "no_lockable_doors",
            "zone": zone,
            "doors_locked": doors_locked,
            "egress_skipped": egress_skipped,
            "ttl_seconds": clamped_ttl,
        }

    async def release_zone(
        self,
        zone: str,
        *,
        released_by: str = "operator",
        manual: bool = True,
    ) -> dict[str, Any]:
        """One-tap release for a restricted zone. ALWAYS permitted, even under Emergency Freeze."""
        now = self._clock()
        if manual:
            self._last_manual_release[zone] = now

        active = self.active_restrictions.get(zone)
        if active is None or active.released:
            return {"status": "already_clear", "zone": zone, "doors_released": []}

        released_doors: list[str] = []
        for door_id in active.doors_locked:
            if self._door_controller is not None:
                await self._door_controller(door_id, "unlock")
            released_doors.append(door_id)

        active.released = True
        active.released_by = released_by
        active.released_at = now
        self.active_restrictions.pop(zone, None)
        return {
            "status": "released",
            "zone": zone,
            "doors_released": released_doors,
            "released_by": released_by,
        }

    async def expire_due_restrictions(self) -> list[dict[str, Any]]:
        """Lift any active zone restrictions whose TTL has elapsed."""
        now = self._clock()
        expired_zones = [
            zone for zone, r in list(self.active_restrictions.items())
            if not r.released and now >= r.expires_at
        ]
        results: list[dict[str, Any]] = []
        for zone in expired_zones:
            results.append(await self.release_zone(zone, released_by="ttl_expiry", manual=False))
        return results

    # ---- Presence Event Evaluation ----

    async def handle_presence(self, event: PresenceEvent) -> list[dict[str, Any]]:
        """Evaluate all matching owner rules for a camera presence event."""
        now = self._clock()
        await self.expire_due_restrictions()

        # Global Invariant: Freeze stops ALL automations (only release_zone remains active)
        if self._is_frozen():
            return [{"status": "skipped_frozen", "zone": event.zone}]

        is_unknown = not event.person_name or event.person_name.strip().lower() == "unknown"
        if is_unknown:
            self._unknown_frame_streaks[event.zone] = self._unknown_frame_streaks.get(event.zone, 0) + 1
        else:
            self._unknown_frame_streaks[event.zone] = 0

        outcomes: list[dict[str, Any]] = []
        for rule in self.rules.values():
            if not rule.enabled or rule.zone != event.zone:
                continue

            # Match check + confidence / multi-frame confirmation
            if rule.person_match == "unknown":
                if not is_unknown:
                    continue
                if self._unknown_frame_streaks.get(event.zone, 0) < max(1, rule.unknown_min_frames):
                    outcomes.append({
                        "rule_id": rule.rule_id,
                        "status": "awaiting_frames",
                        "frames_seen": self._unknown_frame_streaks[event.zone],
                        "frames_required": rule.unknown_min_frames,
                    })
                    continue
            elif rule.person_match.startswith("known:"):
                expected = rule.person_match.split(":", 1)[1]
                if is_unknown or event.person_name != expected:
                    continue
                if event.confidence < rule.min_confidence:
                    outcomes.append({"rule_id": rule.rule_id, "status": "below_confidence"})
                    continue
            elif rule.person_match.startswith("group:"):
                expected_group = rule.person_match.split(":", 1)[1]
                if is_unknown or event.person_group != expected_group:
                    continue
                if event.confidence < rule.min_confidence:
                    outcomes.append({"rule_id": rule.rule_id, "status": "below_confidence"})
                    continue
            else:
                continue

            rule_results: list[dict[str, Any]] = []
            for action in rule.actions:
                act_type = str(action.get("type") or "")

                if act_type == "access.restrict_zone":
                    # False-unknown lockout suppression
                    recent_release = (
                        now - self._last_manual_release.get(event.zone, 0.0)
                    ) < self.manual_release_grace_seconds
                    if self.guests_expected or event.known_present_in_zone or recent_release:
                        reason = (
                            "guests_expected" if self.guests_expected
                            else ("known_present_in_zone" if event.known_present_in_zone else "recent_manual_release")
                        )
                        rule_results.append({
                            "action": act_type,
                            "status": "suppressed",
                            "reason": reason,
                        })
                        continue
                    res = await self.restrict_zone(
                        event.zone,
                        rule_id=rule.rule_id,
                        ttl_seconds=int(action.get("ttl_seconds") or rule.ttl_seconds),
                    )
                    rule_results.append({"action": act_type, **res})

                elif act_type == "scan.request":
                    res = await self._handle_presence_scan(action, rule, event, now)
                    rule_results.append({"action": act_type, **res})

                elif act_type == "infrastructure.control":
                    # Convenience actions (lights/music/climate) run immediately; physical access forbidden here
                    subsystem = str(action.get("subsystem") or "lights").lower()
                    if subsystem in ("door", "lock", "access", "alarm"):
                        rule_results.append({
                            "action": act_type,
                            "status": "denied",
                            "reason": "Physical access must use access.restrict_zone",
                        })
                    else:
                        rule_results.append({
                            "action": act_type,
                            "subsystem": subsystem,
                            "command": action.get("command", "on"),
                            "status": "executed",
                        })

            # Privacy-preserving notification (zero raw face images or host snapshot paths)
            if self._notify is not None and rule_results:
                label = "unknown person" if is_unknown else str(event.person_name)
                await self._notify({
                    "type": "notify.presence",
                    "source_app": "openeye",
                    "severity": "high" if is_unknown else "low",
                    "title": f"{label.title()} in {event.zone}",
                    "body": f"{label} detected in {event.zone} (rule {rule.rule_id}).",
                    "deep_link": f"/openeye/zones/{event.zone}",
                    "dedupe_key": f"presence:{rule.rule_id}:{event.zone}:{int(now // 60)}",
                })

            firing_entry = {
                "rule_id": rule.rule_id,
                "zone": event.zone,
                "camera_id": event.camera_id,
                "person": "unknown" if is_unknown else event.person_name,
                "snapshot_ref": event.snapshot_ref,  # Local audit only
                "results": rule_results,
                "timestamp": now,
            }
            self.firing_log.append(firing_entry)
            outcomes.append({"rule_id": rule.rule_id, "status": "fired", "results": rule_results})

        return outcomes

    async def _handle_presence_scan(
        self,
        action: dict[str, Any],
        rule: PresenceRule,
        event: PresenceEvent,
        now: float,
    ) -> dict[str, Any]:
        """Queue `scan.request` ONLY for devices with recorded consent AND owner approval."""
        device_id = str(action.get("device_id") or "").strip()
        profile = str(action.get("profile") or "quick").strip().lower()
        if not device_id:
            return {"status": "skipped", "reason": "missing device_id"}

        # Per-device and per-zone cooldown check
        cooldown_key = f"{event.zone}:{device_id}"
        last_ts = self._scan_cooldowns.get(cooldown_key, 0.0)
        if last_ts and (now - last_ts) < rule.cooldown_seconds:
            return {
                "status": "cooldown_active",
                "device_id": device_id,
                "retry_after_seconds": int(rule.cooldown_seconds - (now - last_ts)),
            }

        # Enforce BOTH Global Constraint conditions:
        # 1) Recorded device owner consent / AUP acceptance (never assumed)
        # 2) Ecosystem owner standing auto-scan grant or explicit per-run approval
        if self.policy_engine is None:
            return {"status": "awaiting_consent", "device_id": device_id, "reason": "No policy engine configured"}

        enrolled_list = (
            self.policy_engine.list_enrolled_devices()
            if hasattr(self.policy_engine, "list_enrolled_devices")
            else []
        )
        enrolled = next((d for d in enrolled_list if d.get("device_id") == device_id), None)
        if enrolled is None or enrolled.get("revoked") or not enrolled.get("owner") or not enrolled.get("aup_version"):
            return {
                "status": "awaiting_consent",
                "device_id": device_id,
                "reason": "Device lacks recorded owner consent / AUP acceptance",
            }

        has_grant = False
        if hasattr(self.policy_engine, "has_valid_auto_scan_grant"):
            has_grant, _ = self.policy_engine.has_valid_auto_scan_grant(
                device_id=device_id,
                public_key_fingerprint=enrolled.get("public_key_fingerprint"),
                profile=profile,
                initiator="openeye_presence",
            )
        approved_ref = action.get("approved_ref")
        if not has_grant and not approved_ref:
            return {
                "status": "awaiting_approval",
                "device_id": device_id,
                "reason": "Device has consent but lacks standing auto-scan designation or per-run owner approval",
            }

        self._scan_cooldowns[cooldown_key] = now
        if self.hub_client is not None and hasattr(self.hub_client, "invoke"):
            resp = await self.hub_client.invoke(
                capability="scan.request",
                target={"scope": "local", "identifier": device_id},
                parameters={
                    "target_device": device_id,
                    "profile": profile,
                    "offline": True,
                    "public_key_fingerprint": enrolled.get("public_key_fingerprint"),
                },
                rationale=f"WP11 presence rule {rule.rule_id} in {event.zone}",
            )
            return {"status": "scan_queued", "device_id": device_id, "hub_response": resp}
        return {"status": "scan_queued", "device_id": device_id}
