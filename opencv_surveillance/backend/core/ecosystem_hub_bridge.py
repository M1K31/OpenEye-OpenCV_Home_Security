"""Phase 2 & 3 HubRuntime, capability manifest, policy/approval singletons, onboarding consent, and federated push sink bridge for OpenEye (priority=50)."""
from __future__ import annotations

import json
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_policy_engine: Any = None
_step_up_auth: Any = None
_approval_queue: Any = None


def _find_ecosystem_root() -> Path | None:
    env = os.environ.get("APP_ECOSYSTEM_PATH")
    candidates = [Path(env).expanduser()] if env else []
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / "appEcosystem")
    for root in candidates:
        if root.is_dir():
            return root.resolve()
    return None


def _ensure_ecosystem_paths() -> None:
    root = _find_ecosystem_root()
    if root is not None:
        for rel in (
            "",
            "auth/python",
            "packages/ecosystem-client",
            "packages/ecosystem-ai",
            "packages/ecosystem-hub",
            "packages/ecosystem-policy",
        ):
            p = (root / rel).resolve()
            if p.is_dir() and str(p) not in sys.path:
                sys.path.insert(0, str(p))


def _policy_state_dir() -> Path:
    base = Path(
        os.environ.get("OPENEYE_POLICY_DIR")
        or os.environ.get("OPENEYE_DATA_DIR")
        or os.environ.get("OPENEYE_DATA_ROOT")
        or (Path.home() / ".local" / "share" / "openeye")
    )
    d = base / "policy"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_policy_engine() -> Any:
    """Return process-wide blue-team `PolicyEngine` for OpenEye."""
    global _policy_engine
    if _policy_engine is None:
        _ensure_ecosystem_paths()
        from ecosystem_policy import Ed25519PolicySigner, PolicyEngine

        state_dir = _policy_state_dir()
        signer = Ed25519PolicySigner.load_or_create(key_dir=state_dir / "keys")
        _policy_engine = PolicyEngine(
            signer=signer,
            authority="standalone_local",
            persistence_path=state_dir / "policy_state.json",
        )
    return _policy_engine


def get_step_up_auth() -> Any:
    """Return process-wide `StepUpAuthenticator` for TOTP / Passkey / Device-Key verification."""
    global _step_up_auth
    if _step_up_auth is None:
        _ensure_ecosystem_paths()
        from ecosystem_policy import StepUpAuthenticator

        store_env = os.environ.get("OPENEYE_STEP_UP_PATH")
        store_path = Path(store_env) if store_env else (_policy_state_dir() / "step_up_credentials.json")
        _step_up_auth = StepUpAuthenticator(store_path=store_path)
    return _step_up_auth


def get_approval_queue(
    revert_callback: Callable[[dict[str, Any]], Any] | None = None,
    approve_callback: Callable[[dict[str, Any]], Any] | None = None,
) -> Any:
    """Return process-wide `LocalApprovalQueue` (`F10` unified approval store)."""
    global _approval_queue
    if _approval_queue is None:
        _ensure_ecosystem_paths()
        from ecosystem_policy import LocalApprovalQueue

        _approval_queue = LocalApprovalQueue(
            db_path=_policy_state_dir() / "unified_approvals.db",
            step_up=get_step_up_auth(),
            revert_callback=revert_callback,
            approve_callback=approve_callback,
        )
    else:
        if revert_callback is not None and getattr(_approval_queue, "_revert_cb", None) is None:
            _approval_queue._revert_cb = revert_callback
        if approve_callback is not None and getattr(_approval_queue, "_approve_cb", None) is None:
            _approval_queue._approve_cb = approve_callback
    return _approval_queue


def reset_policy_singletons() -> None:
    """Reset cached policy/step-up/approval singletons (used by isolated unit tests)."""
    global _policy_engine, _step_up_auth, _approval_queue
    _policy_engine = None
    _step_up_auth = None
    _approval_queue = None


def resolve_ui_asset_path(filename: str) -> Path | None:
    """Resolve shared `@appecosystem/ui-controls` bundle, Apple HIG theme CSS, or typography fonts."""
    root = _find_ecosystem_root()
    candidates: list[Path] = []
    if root is not None:
        if filename == "ecosystem-ui-controls.js":
            candidates.append(root / "packages" / "ecosystem-ui-controls" / "dist" / "ecosystem-ui-controls.js")
        elif filename == "ecosystem-theme.css":
            candidates.append(root / "theme" / "ecosystem-theme.css")
        elif filename.startswith("fonts/"):
            candidates.append(root / "theme" / filename)
    local_prefix = Path.home() / ".local" / "share" / "ecosystem"
    if filename == "ecosystem-ui-controls.js":
        candidates.append(local_prefix / "packages" / "ecosystem-ui-controls" / "dist" / "ecosystem-ui-controls.js")
    elif filename == "ecosystem-theme.css":
        candidates.append(local_prefix / "theme" / "ecosystem-theme.css")
    elif filename.startswith("fonts/"):
        candidates.append(local_prefix / "theme" / filename)
    for target in candidates:
        if target.is_file():
            return target
    return None


def local_device_identity() -> tuple[str, str]:
    """Return `(device_id, public_key_fingerprint)` bound to OpenEye's local Ed25519 key."""
    engine = get_policy_engine()
    host = os.environ.get("ECOSYSTEM_DEVICE_ID") or f"openeye-{socket.gethostname().split('.')[0].lower()}"
    return host, engine.signer.fingerprint


def record_onboarding_consent(
    *,
    owner: str,
    hub_role: str = "auto",
    aup_accepted: bool = False,
    aup_version: str = "1.0",
    baseline_self_scan: bool = False,
    designate_auto_scan: bool = False,
    auto_scan_profiles: list[str] | None = None,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Persist explicit onboarding consent and enroll local device in `PolicyEngine`.

    Hard Invariant:
      - Silence or omission NEVER creates scan consent (`aup_accepted` and `designate_auto_scan`
        both default to `False`).
      - `designate_auto_scan=True` or `baseline_self_scan=True` requires `aup_accepted=True`.
    """
    valid_roles = ("auto", "host", "join", "standalone")
    if hub_role not in valid_roles:
        raise ValueError(f"Unsupported hub_role '{hub_role}'; expected one of {valid_roles}")
    if (designate_auto_scan or baseline_self_scan) and not aup_accepted:
        raise PermissionError(
            "Explicit Acceptable Use Policy (AUP) consent is required before enabling baseline or automatic scanning."
        )

    engine = get_policy_engine()
    default_dev_id, fp = local_device_identity()
    resolved_device_id = (device_id or default_dev_id).strip()

    enrollment_dict: dict[str, Any] | None = None
    auto_scan_dict: dict[str, Any] | None = None

    if aup_accepted:
        enrollment = engine.enroll_device(
            resolved_device_id,
            fp,
            owner=owner,
            aup_version=aup_version,
            scopes=["system_info", "zbt_scan"],
        )
        enrollment_dict = enrollment.to_dict()
        if designate_auto_scan:
            grant = engine.designate_auto_scan(
                resolved_device_id,
                profiles=list(auto_scan_profiles or ["quick"]),
                scopes=["system_info", "zbt_scan"],
                initiators=["*", "openeye", "aegissiem", "ai-for-survival", "hub"],
                authorization_ref=f"openeye-onboarding:{owner}:aup-{aup_version}",
            )
            auto_scan_dict = grant.to_dict()
        else:
            engine.revoke_auto_scan(resolved_device_id, reason="not_designated_during_onboarding")

    record = {
        "owner": owner,
        "device_id": resolved_device_id,
        "public_key_fingerprint": fp,
        "hub_role": hub_role,
        "aup_accepted": bool(aup_accepted),
        "aup_version": aup_version,
        "baseline_self_scan": bool(baseline_self_scan and aup_accepted),
        "designate_auto_scan": bool(designate_auto_scan and aup_accepted),
        "auto_scan_profiles": list(auto_scan_profiles or ["quick"]) if (designate_auto_scan and aup_accepted) else [],
        "recorded_at": time.time(),
        "enrollment": enrollment_dict,
        "auto_scan_grant": auto_scan_dict,
    }
    consent_path = _policy_state_dir() / "onboarding_consent.json"
    tmp_path = consent_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    os.replace(tmp_path, consent_path)
    return record


def get_onboarding_consent() -> dict[str, Any]:
    """Return persisted onboarding consent state or conservative defaults."""
    consent_path = _policy_state_dir() / "onboarding_consent.json"
    if consent_path.is_file():
        try:
            return json.loads(consent_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read onboarding_consent.json: %r", exc)
    dev_id, fp = local_device_identity()
    return {
        "owner": None,
        "device_id": dev_id,
        "public_key_fingerprint": fp,
        "hub_role": os.environ.get("ECOSYSTEM_HUB_ROLE", "auto"),
        "aup_accepted": False,
        "aup_version": "1.0",
        "baseline_self_scan": False,
        "designate_auto_scan": False,
        "auto_scan_profiles": [],
        "recorded_at": None,
        "enrollment": None,
        "auto_scan_grant": None,
    }


def build_openeye_capabilities() -> list[dict[str, Any]]:
    """Capabilities contributed by OpenEye to the ecosystem mesh."""
    return [
        {
            "capability": "camera.snapshot",
            "version": 1,
            "description": "Capture a point-in-time JPEG snapshot from an authorized OpenEye camera.",
            "action_class": "observe",
            "required_grant": "camera:read",
            "requirements": {"os": ["darwin", "linux", "win32"], "min_tier": 0, "needs_gpu": False},
            "timeout_seconds": 15,
            "cancellable": True,
            "idempotent": True,
            "offline_behavior": "run_local",
        },
        {
            "capability": "camera.record_clip",
            "version": 1,
            "description": "Trigger bounded event clip recording on an OpenEye camera.",
            "action_class": "observe",
            "required_grant": "camera:record",
            "requirements": {"os": ["darwin", "linux", "win32"], "min_tier": 0, "needs_gpu": False},
            "timeout_seconds": 60,
            "cancellable": True,
            "idempotent": False,
            "offline_behavior": "run_local",
        },
        {
            "capability": "automation.trigger_rule",
            "version": 1,
            "description": "Invoke a pre-configured OpenEye automation rule under ecosystem policy evaluation.",
            "action_class": "system_change",
            "required_grant": "automation:trigger",
            "timeout_seconds": 30,
            "cancellable": True,
            "idempotent": False,
            "offline_behavior": "run_local",
        },
        {
            "capability": "notify.deliver.openeye_push",
            "version": 1,
            "description": "Federated mobile/provider push sink (Telegram, Discord, Webhook, Email, WebSocket).",
            "action_class": "observe",
            "required_grant": "notify:deliver",
            "timeout_seconds": 15,
            "cancellable": False,
            "idempotent": True,
            "offline_behavior": "queue_until_online",
        },
        {
            "capability": "ecosystem.freeze",
            "version": 1,
            "description": "Emergency preemption of mutating automations across OpenEye and peers.",
            "action_class": "contain",
            "required_grant": "freeze.request",
            "timeout_seconds": 10,
            "cancellable": False,
            "idempotent": True,
            "offline_behavior": "freeze_local_and_queue_notice",
        },
    ]


async def start_openeye_hub(app: Any, service_port: int, eco_config: Any = None) -> Any:
    """Start HubRuntime (priority=50, fallback Hub host) and return active EcosystemClient."""
    _ensure_ecosystem_paths()
    from ecosystem_client import EcosystemClient
    from ecosystem_client.config import EcosystemConfig
    from ecosystem_hub import HubRuntime

    cfg = eco_config or EcosystemConfig.from_env()
    if not getattr(cfg, "webhook_path", None) or cfg.webhook_path == "/ecosystem/events":
        cfg.webhook_path = "/api/ecosystem/webhook"

    resolved_role = os.environ.get("ECOSYSTEM_HUB_ROLE") or get_onboarding_consent().get("hub_role") or "auto"
    hub = HubRuntime(
        app_name="openeye",
        service_port=service_port,
        priority=50,
        role=resolved_role,
        health_endpoint="/api/health",
        config=cfg,
        capabilities=build_openeye_capabilities(),
    )
    mode = await hub.start()
    app.state.ecosystem_hub = hub
    logger.info("OpenEye HubRuntime active in %s mode (role=%s)", mode, hub.role.value)

    if hub.client is not None:
        return hub.client

    eco = EcosystemClient(
        service_name="openeye",
        service_port=service_port,
        health_endpoint="/api/health",
        priority=50,
        config=cfg,
    )
    await eco.start()
    return eco


async def stop_openeye_hub(app: Any) -> None:
    hub = getattr(app.state, "ecosystem_hub", None)
    if hub is not None:
        try:
            await hub.stop()
        except Exception as exc:
            logger.debug("Error stopping OpenEye HubRuntime: %r", exc)
        app.state.ecosystem_hub = None

    eco = getattr(app.state, "ecosystem", None)
    if eco is not None:
        try:
            await eco.stop()
        except Exception:
            pass
        app.state.ecosystem = None


async def deliver_federated_push(
    envelope: dict[str, Any],
    db: Any = None,
    *,
    broadcast_fn: Any = None,
    dispatch_fn: Any = None,
) -> dict[str, Any]:
    """Deliver a Hub-routed `notification-envelope.v1` to OpenEye WebSocket & configured push providers."""
    _ensure_ecosystem_paths()
    try:
        from ecosystem_client.contracts import assert_valid_schema

        assert_valid_schema(envelope, "notification-envelope.v1")
    except ModuleNotFoundError:
        for req in ("id", "type", "severity", "title", "dedupe_key"):
            if not envelope.get(req):
                raise ValueError(f"Missing required notification field: {req}")

    # Privacy guard: never forward local_only payloads outside local WebSocket HUDs.
    is_local_only = envelope.get("privacy") == "local_only"

    if broadcast_fn is None:
        from backend.api.routes.ecosystem import broadcast_to_ecosystem

        broadcast_fn = broadcast_to_ecosystem

    await broadcast_fn(
        {
            "type": "ecosystem_notification",
            "envelope": envelope,
        }
    )

    delivered_via: list[str] = ["ecosystem_ws"]
    suppressed = False
    if db is not None and not is_local_only:
        if dispatch_fn is None:
            from backend.core import notification_dispatch

            dispatch_fn = notification_dispatch.dispatch_notification

        prio_map = {"low": "low", "medium": "normal", "high": "high", "critical": "urgent"}
        result = await dispatch_fn(
            db,
            title=str(envelope.get("title", "Ecosystem Alert")),
            message=str(envelope.get("body") or envelope.get("title") or ""),
            priority=prio_map.get(str(envelope.get("severity", "medium")), "normal"),
            event_type=str(envelope.get("type", "notify.system")),
            cooldown_key=envelope.get("dedupe_key"),
            cooldown_seconds=60,
        )
        delivered_via.extend(result.get("delivered_via", []))
        suppressed = bool(result.get("suppressed", False))

    return {
        "status": "delivered",
        "id": envelope["id"],
        "dedupe_key": envelope["dedupe_key"],
        "delivered_via": delivered_via,
        "suppressed": suppressed,
    }
