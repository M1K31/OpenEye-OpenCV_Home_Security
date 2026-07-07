"""Central notification dispatch for automation rules and ecosystem routes.

Single source of truth for "send this message through the user's configured
channels": loads enabled NotificationProvider rows, applies optional targeting
and cooldown, and delivers via NotificationService. Used by the (sync,
camera-thread) automation engine through dispatch_from_thread() and awaited
directly by async API routes.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.database.alert_models import NotificationProvider
from backend.services.notification_service import get_notification_service

logger = logging.getLogger(__name__)

# Provider types the dispatcher can deliver to in v1. sms/push rows are
# skipped: their configs lack recipient / device-token fields.
SUPPORTED_TYPES = {"email", "telegram", "discord", "webhook"}

# ---------------------------------------------------------------------------
# Cooldown state (process-local; resets on restart — fine for a rate limiter)
# ---------------------------------------------------------------------------
_cooldown_lock = threading.Lock()
_last_sent: Dict[Any, float] = {}
_suppressed: Dict[Any, int] = {}

# App event loop, captured at startup so camera threads can schedule onto it.
_app_loop: Optional[asyncio.AbstractEventLoop] = None


def set_app_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once from FastAPI startup so threads can reach the loop."""
    global _app_loop
    _app_loop = loop


def check_cooldown(key: Any, seconds: int) -> tuple[bool, int]:
    """Return (allowed, suppressed_count_to_report).

    seconds <= 0 or key None disables cooldown. When allowed after a window,
    returns how many sends were suppressed since the last delivery.
    """
    if key is None or seconds <= 0:
        return True, 0
    now = time.monotonic()
    with _cooldown_lock:
        last = _last_sent.get(key)
        if last is not None and (now - last) < seconds:
            _suppressed[key] = _suppressed.get(key, 0) + 1
            return False, 0
        count = _suppressed.pop(key, 0)
        _last_sent[key] = now
        return True, count


async def _send_via_provider(provider: NotificationProvider, config: dict,
                             title: str, message: str, priority: str) -> bool:
    """Deliver one message through one provider. Returns success."""
    svc = get_notification_service()
    ptype = provider.provider_type

    if ptype == "discord":
        ok, err = await svc.send_webhook(
            config["webhook_url"], {"content": f"**{title}**\n{message}"})
    elif ptype == "webhook":
        ok, err = await svc.send_webhook(
            config["url"],
            {"title": title, "message": message, "priority": priority,
             "source": "openeye"})
    elif ptype == "telegram":
        chat_id = config.get("chat_id")
        if not chat_id:
            logger.warning("Telegram provider '%s' has no chat_id; skipping "
                           "(edit the provider and add one)", provider.provider_name)
            return False
        ok, err = await svc.send_webhook(
            f"https://api.telegram.org/bot{config['bot_token']}/sendMessage",
            {"chat_id": chat_id, "text": f"{title}\n{message}"})
    elif ptype == "email":
        to_addr = (config.get("to_email") or config.get("from_email")
                   or config.get("username"))
        if not to_addr:
            logger.warning("Email provider '%s' has no recipient; skipping",
                           provider.provider_name)
            return False
        ok, err = await svc.send_email(to_addr, title, message, smtp=config)
    else:
        logger.warning("Provider type '%s' not supported by automation "
                       "dispatch (v1); skipping '%s'", ptype, provider.provider_name)
        return False

    if not ok:
        logger.warning("Notification via %s '%s' failed: %s",
                       ptype, provider.provider_name, err)
    return bool(ok)


async def dispatch_notification(
    db,
    *,
    message: str,
    title: str = "OpenEye Alert",
    priority: str = "normal",
    event_type: str = "automation",
    camera_id: Optional[str] = None,
    person_name: Optional[str] = None,
    target_providers: Optional[List[str]] = None,
    cooldown_key: Any = None,
    cooldown_seconds: int = 0,
) -> Dict[str, Any]:
    """Send `message` through enabled providers.

    target_providers: list matching provider_type, provider_name, or str(id);
    None fans out to all enabled. Returns
    {"delivered_via": [...], "suppressed": bool, "suppressed_count": int}.
    Never raises.
    """
    allowed, prior_suppressed = check_cooldown(cooldown_key, cooldown_seconds)
    if not allowed:
        logger.debug("Notification suppressed by cooldown (key=%s)", cooldown_key)
        return {"delivered_via": [], "suppressed": True, "suppressed_count": 0}

    if prior_suppressed:
        message = f"{message} (+{prior_suppressed} earlier events suppressed)"

    delivered: List[str] = []
    try:
        providers = (db.query(NotificationProvider)
                     .filter(NotificationProvider.enabled == True)  # noqa: E712
                     .all())
        for p in providers:
            if target_providers is not None:
                idset = {p.provider_type, p.provider_name, str(p.id)}
                if not idset.intersection(target_providers):
                    continue
            try:
                config = p.decrypt_config()
                ok = await _send_via_provider(p, config, title, message, priority)
            except Exception:
                logger.exception("Provider '%s' raised during send", p.provider_name)
                ok = False
            # usage counters (best-effort)
            try:
                if ok:
                    p.total_sent = (p.total_sent or 0) + 1
                    p.last_used_at = datetime.utcnow()
                    delivered.append(f"{p.provider_type}:{p.provider_name}")
                else:
                    p.total_failed = (p.total_failed or 0) + 1
                db.commit()
            except Exception:
                db.rollback()
    except Exception:
        logger.exception("dispatch_notification failed")

    return {"delivered_via": delivered, "suppressed": False,
            "suppressed_count": prior_suppressed}
