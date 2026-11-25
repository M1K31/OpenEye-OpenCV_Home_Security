"""WP11 — OpenEye Presence Automations Engine.

Turns owner-authored presence rules ("who is where") into safe, policy-gated
actions across three families:
1. Restrict access on an unknown person (`access.restrict_zone`)
   - `access.release_zone` is an operator/timer-only release operation (never
     triggered automatically by camera rules) and ALWAYS works, even under Freeze.
   - Hard life-safety invariant: NEVER lock an egress or life-safety door.
   - Mandatory bounded TTL + background expiry monitor + one-tap manual release.
   - Requires >= 2 distinct unknown frames (`unknown_min_frames >= 2`) + false-unknown
     lockout suppression (known person in zone, recent manual release grace, or
     guests-expected mode).
   - Per-zone locking serializes restrict/release; Freeze is re-checked before
     every individual door command.
2. Presence-triggered vulnerability scans (`scan.request`)
   - Default is NO scan. Requires BOTH recorded owner consent/AUP acceptance AND
     a valid standing auto-scan designation or verified approval record.
   - Independent per-device AND per-zone cooldowns recorded ONLY after hub acceptance.
3. Infrastructure by identity (`infrastructure.control`)
   - Requires recognised identity meeting `min_confidence` and a configured actuator.

Privacy: notifications carry `"unknown person in <zone>"` + deep link, NEVER raw
face images or host snapshot paths. Under Emergency Freeze, all automations stop
EXCEPT `release_zone`.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
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
    restriction_id: str
    zone: str
    doors_locked: list[str]
    rule_id: str
    created_at: float
    expires_at: float
    pending_recovery: list[str] = field(default_factory=list)
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
    frame_id: str | None = None
    timestamp: float = field(default_factory=time.time)


class PresenceAutomationEngine:
    """Evaluates owner-defined WP11 presence rules with hard safety & consent gates."""

    def __init__(
        self,
        *,
        policy_engine: Any = None,
        approval_queue: Any = None,
        hub_client: Any = None,
        notification_fn: Callable[[dict[str, Any]], Awaitable[Any]] | None = None,
        door_controller: Callable[[str, str], Awaitable[bool]] | None = None,
        infrastructure_controller: Callable[[str, str], Awaitable[bool]] | None = None,
        clock: Callable[[], float] = time.time,
        manual_release_grace_seconds: int = 300,
    ):
        self.policy_engine = policy_engine
        self.approval_queue = approval_queue
        self.hub_client = hub_client
        self._notify = notification_fn
        self._door_controller = door_controller
        self._infra_controller = infrastructure_controller
        self._clock = clock
        self.manual_release_grace_seconds = max(30, int(manual_release_grace_seconds))

        self.rules: dict[str, PresenceRule] = {}
        self.doors: dict[str, DoorTarget] = {}
        self.active_restrictions: dict[str, ActiveRestriction] = {}
        self.guests_expected: bool = False
        self.face_consents: dict[str, dict[str, Any]] = {}
        self.firing_log: list[dict[str, Any]] = []

        self._zone_locks: dict[str, asyncio.Lock] = {}
        self._unknown_frame_streaks: dict[str, int] = {}
        self._last_frame_ids: dict[str, str] = {}
        self._last_manual_release: dict[str, float] = {}
        self._device_scan_cooldowns: dict[str, float] = {}
        self._zone_scan_cooldowns: dict[str, float] = {}
        self._expiry_task: asyncio.Task[Any] | None = None

    def _zone_lock(self, zone: str) -> asyncio.Lock:
        if zone not in self._zone_locks:
            self._zone_locks[zone] = asyncio.Lock()
        return self._zone_locks[zone]

    # ---- Background Expiry Lifecycle ----

    def start_expiry_monitor(self, interval_seconds: float = 5.0) -> None:
        """Start an independent background timer to lift expired restrictions without waiting for events."""
        if self._expiry_task is not None and not self._expiry_task.done():
            return

        async def _loop() -> None:
            while True:
                await asyncio.sleep(max(0.5, float(interval_seconds)))
                try:
                    await self.expire_due_restrictions()
                except Exception as exc:
                    logger.warning("Presence expiry sweep error: %r", exc)

        self._expiry_task = asyncio.create_task(_loop())

    async def stop_expiry_monitor(self) -> None:
        if self._expiry_task is not None:
            self._expiry_task.cancel()
            try:
                await self._expiry_task
            except asyncio.CancelledError:
                pass
            self._expiry_task = None

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
        if self._door_controller is None:
            return {
                "status": "controller_unavailable",
                "zone": zone,
                "doors_locked": [],
                "egress_skipped": [],
            }

        async with self._zone_lock(zone):
            if self._is_frozen():
                return {"status": "skipped_frozen", "zone": zone, "doors_locked": [], "egress_skipped": []}

            now = self._clock()
            existing = self.active_restrictions.get(zone)
            if existing is not None and not existing.released and now < existing.expires_at:
                # Preserve existing restriction & its original expiry deadline (never renew on repeat frames)
                return {
                    "status": "already_restricted",
                    "zone": zone,
                    "restriction_id": existing.restriction_id,
                    "doors_locked": list(existing.doors_locked),
                    "egress_skipped": [],
                    "expires_at": existing.expires_at,
                }

            zone_doors = [d for d in self.doors.values() if d.zone == zone]
            clamped_ttl = max(60, min(int(ttl_seconds), 86400))
            restriction_id = f"restr-{uuid.uuid4().hex[:12]}"
            egress_skipped: list[str] = []
            record: ActiveRestriction | None = None
            frozen_mid_loop = False

            for door in zone_doors:
                if door.is_protected_egress():
                    egress_skipped.append(door.door_id)
                    continue
                # Re-check Freeze BEFORE every single door command
                if self._is_frozen():
                    frozen_mid_loop = True
                    break
                try:
                    ok = bool(await self._door_controller(door.door_id, "lock"))
                except Exception as exc:
                    logger.warning("Door lock for %s failed with unknown outcome: %r", door.door_id, exc)
                    # Track unknown outcome in pending_recovery so release_zone still attempts unlock
                    if record is None:
                        record = ActiveRestriction(
                            restriction_id=restriction_id,
                            zone=zone,
                            doors_locked=[],
                            pending_recovery=[door.door_id],
                            rule_id=rule_id,
                            created_at=now,
                            expires_at=now + clamped_ttl,
                        )
                        self.active_restrictions[zone] = record
                    else:
                        record.pending_recovery.append(door.door_id)
                    continue

                if ok:
                    # Record each confirmed lock immediately before awaiting next door
                    if record is None:
                        record = ActiveRestriction(
                            restriction_id=restriction_id,
                            zone=zone,
                            doors_locked=[door.door_id],
                            rule_id=rule_id,
                            created_at=now,
                            expires_at=now + clamped_ttl,
                        )
                        self.active_restrictions[zone] = record
                    else:
                        record.doors_locked.append(door.door_id)

            doors_locked = list(record.doors_locked) if record else []
            status = (
                "partial_frozen" if (frozen_mid_loop and doors_locked)
                else ("skipped_frozen" if frozen_mid_loop else ("restricted" if doors_locked else "no_lockable_doors"))
            )
            return {
                "status": status,
                "zone": zone,
                "restriction_id": record.restriction_id if record else None,
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
        expected_restriction_id: str | None = None,
    ) -> dict[str, Any]:
        """One-tap release for a restricted zone. ALWAYS permitted, even under Emergency Freeze."""
        async with self._zone_lock(zone):
            now = self._clock()
            if manual:
                self._last_manual_release[zone] = now

            active = self.active_restrictions.get(zone)
            if active is None or active.released:
                return {"status": "already_clear", "zone": zone, "doors_released": [], "doors_failed": []}
            if expected_restriction_id is not None and active.restriction_id != expected_restriction_id:
                return {"status": "superseded", "zone": zone, "doors_released": [], "doors_failed": []}

            targets = list(dict.fromkeys([*active.doors_locked, *active.pending_recovery]))
            released_doors: list[str] = []
            failed_doors: list[str] = []

            for door_id in targets:
                if self._door_controller is None:
                    failed_doors.append(door_id)
                    continue
                try:
                    ok = bool(await self._door_controller(door_id, "unlock"))
                except Exception as exc:
                    logger.warning("Failed unlocking door %s in zone %s: %r", door_id, zone, exc)
                    ok = False
                if ok:
                    released_doors.append(door_id)
                else:
                    failed_doors.append(door_id)

            if failed_doors:
                # Retain failed doors on active restriction for retry (even under Freeze)
                active.doors_locked = list(failed_doors)
                active.pending_recovery = []
                return {
                    "status": "partial_release",
                    "zone": zone,
                    "doors_released": released_doors,
                    "doors_failed": failed_doors,
                    "released_by": released_by,
                }

            active.released = True
            active.released_by = released_by
            active.released_at = now
            self.active_restrictions.pop(zone, None)
            return {
                "status": "released",
                "zone": zone,
                "doors_released": released_doors,
                "doors_failed": [],
                "released_by": released_by,
            }

    async def expire_due_restrictions(self) -> list[dict[str, Any]]:
        """Lift any active zone restrictions whose TTL has elapsed (isolating per-zone failures)."""
        now = self._clock()
        expired = [
            (zone, r.restriction_id)
            for zone, r in list(self.active_restrictions.items())
            if not r.released and now >= r.expires_at
        ]
        results: list[dict[str, Any]] = []
        for zone, restr_id in expired:
            results.append(
                await self.release_zone(
                    zone,
                    released_by="ttl_expiry",
                    manual=False,
                    expected_restriction_id=restr_id,
                )
            )
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
        # Deduplicate repeated delivery of the same frame_id per zone
        if event.frame_id is not None and self._last_frame_ids.get(event.zone) == event.frame_id:
            return [{"status": "duplicate_frame", "zone": event.zone, "frame_id": event.frame_id}]
        if event.frame_id is not None:
            self._last_frame_ids[event.zone] = event.frame_id

        if is_unknown:
            self._unknown_frame_streaks[event.zone] = self._unknown_frame_streaks.get(event.zone, 0) + 1
        else:
            self._unknown_frame_streaks[event.zone] = 0

        outcomes: list[dict[str, Any]] = []
        for rule in self.rules.values():
            if not rule.enabled or rule.zone != event.zone:
                continue

            has_restrict = any(str(a.get("type") or "") == "access.restrict_zone" for a in rule.actions)
            required_unknown_frames = max(2, rule.unknown_min_frames) if has_restrict else max(1, rule.unknown_min_frames)

            # Match check + confidence / multi-frame confirmation
            if rule.person_match == "unknown":
                if not is_unknown:
                    continue
                if self._unknown_frame_streaks.get(event.zone, 0) < required_unknown_frames:
                    outcomes.append({
                        "rule_id": rule.rule_id,
                        "status": "awaiting_frames",
                        "frames_seen": self._unknown_frame_streaks[event.zone],
                        "frames_required": required_unknown_frames,
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

                if act_type == "access.release_zone":
                    rule_results.append({
                        "action": act_type,
                        "status": "rejected",
                        "reason": "access.release_zone is operator/timer-only and cannot be triggered by a camera rule",
                    })
                elif act_type == "access.restrict_zone":
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
                    subsystem = str(action.get("subsystem") or "lights").lower()
                    if subsystem in ("door", "lock", "access", "alarm"):
                        rule_results.append({
                            "action": act_type,
                            "status": "denied",
                            "reason": "Physical access must use access.restrict_zone",
                        })
                    elif is_unknown or event.confidence < rule.min_confidence:
                        rule_results.append({
                            "action": act_type,
                            "status": "below_confidence",
                            "reason": "Recognised identity above min_confidence required for infrastructure control",
                        })
                    elif self._infra_controller is None:
                        rule_results.append({
                            "action": act_type,
                            "subsystem": subsystem,
                            "status": "controller_unavailable",
                        })
                    else:
                        cmd = str(action.get("command") or "on")
                        ok = bool(await self._infra_controller(subsystem, cmd))
                        rule_results.append({
                            "action": act_type,
                            "subsystem": subsystem,
                            "command": cmd,
                            "status": "executed" if ok else "failed",
                        })

            # Record audit entry BEFORE notification so a notification failure never erases the outcome
            firing_entry: dict[str, Any] = {
                "rule_id": rule.rule_id,
                "zone": event.zone,
                "camera_id": event.camera_id,
                "person": "unknown" if is_unknown else event.person_name,
                "snapshot_ref": event.snapshot_ref,  # Local audit only
                "results": rule_results,
                "timestamp": now,
            }
            self.firing_log.append(firing_entry)

            # Privacy-preserving notification (zero raw face images or host snapshot paths)
            notification_error: str | None = None
            if self._notify is not None and rule_results:
                label = "unknown person" if is_unknown else str(event.person_name)
                try:
                    await self._notify({
                        "type": "notify.presence",
                        "source_app": "openeye",
                        "severity": "high" if is_unknown else "low",
                        "title": f"{label.title()} in {event.zone}",
                        "body": f"{label} detected in {event.zone} (rule {rule.rule_id}).",
                        "deep_link": f"/openeye/zones/{event.zone}",
                        "dedupe_key": f"presence:{rule.rule_id}:{event.zone}:{int(now // 60)}",
                    })
                except Exception as exc:
                    notification_error = str(exc)
                    logger.warning("Presence notification failed for rule %s: %r", rule.rule_id, exc)

            outcome: dict[str, Any] = {"rule_id": rule.rule_id, "status": "fired", "results": rule_results}
            if notification_error is not None:
                outcome["notification_error"] = notification_error
            outcomes.append(outcome)

        return outcomes

    async def _handle_presence_scan(
        self,
        action: dict[str, Any],
        rule: PresenceRule,
        event: PresenceEvent,
        now: float,
    ) -> dict[str, Any]:
        """Queue `scan.request` ONLY for devices with recorded consent AND verified owner approval."""
        device_id = str(action.get("device_id") or "").strip()
        profile = str(action.get("profile") or "quick").strip().lower()
        if not device_id:
            return {"status": "skipped", "reason": "missing device_id"}

        # Independent per-device AND per-zone cooldown checks
        dev_last = self._device_scan_cooldowns.get(device_id, 0.0)
        if dev_last and (now - dev_last) < rule.cooldown_seconds:
            return {
                "status": "cooldown_active",
                "scope": "device",
                "device_id": device_id,
                "retry_after_seconds": int(rule.cooldown_seconds - (now - dev_last)),
            }
        zone_last = self._zone_scan_cooldowns.get(event.zone, 0.0)
        if zone_last and (now - zone_last) < rule.cooldown_seconds:
            return {
                "status": "cooldown_active",
                "scope": "zone",
                "device_id": device_id,
                "retry_after_seconds": int(rule.cooldown_seconds - (now - zone_last)),
            }

        # Enforce BOTH Global Constraint conditions:
        # 1) Recorded device owner consent / AUP acceptance (never assumed)
        # 2) Ecosystem owner standing auto-scan grant OR verified approval queue record
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

        verified_approval = False
        approved_ref = action.get("approved_ref")
        if not has_grant and isinstance(approved_ref, str) and approved_ref.strip() and self.approval_queue is not None:
            lookup = getattr(self.approval_queue, "get", None)
            if callable(lookup):
                rec = lookup(approved_ref.strip())
                if (
                    isinstance(rec, dict)
                    and rec.get("status") == "approved"
                    and rec.get("action") == "scan.request"
                    and (rec.get("target") or {}).get("identifier") == device_id
                ):
                    verified_approval = True

        if not has_grant and not verified_approval:
            return {
                "status": "awaiting_approval",
                "device_id": device_id,
                "reason": "Device has consent but lacks standing auto-scan designation or verified owner approval",
            }

        # Require an actual hub client; NEVER fabricate `scan_queued` or record cooldown when hub is absent
        if self.hub_client is None or not hasattr(self.hub_client, "invoke"):
            return {"status": "hub_unavailable", "device_id": device_id, "reason": "Ecosystem hub client unavailable"}

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
        if not isinstance(resp, dict) or resp.get("status") in ("failed", "denied", "provider_unavailable"):
            return {"status": "hub_rejected", "device_id": device_id, "hub_response": resp}

        # Record BOTH device and zone cooldowns ONLY after hub acceptance
        self._device_scan_cooldowns[device_id] = now
        self._zone_scan_cooldowns[event.zone] = now
        return {"status": "scan_queued", "device_id": device_id, "hub_response": resp}
