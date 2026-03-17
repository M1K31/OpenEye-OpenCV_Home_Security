"""Event subscriber that receives webhooks and dispatches to registered handlers."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

from .match import matches_pattern

logger = logging.getLogger(__name__)

HandlerFunc = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventSubscriber:
    """Receives and dispatches ecosystem events."""

    def __init__(self, hmac_secret: str):
        self._hmac_secret = hmac_secret
        self._handlers: dict[str, list[HandlerFunc]] = defaultdict(list)

    def on(self, event_pattern: str, handler: HandlerFunc | None = None):
        """Register an event handler. Works as a method or decorator."""
        if handler is not None:
            self._handlers[event_pattern].append(handler)
            return handler

        def decorator(fn: HandlerFunc) -> HandlerFunc:
            self._handlers[event_pattern].append(fn)
            return fn
        return decorator

    async def dispatch(self, envelope: dict[str, Any]) -> None:
        """Verify signature and dispatch event to matching handlers."""
        if not self._verify_envelope(envelope):
            logger.warning(
                f"Rejected event {envelope.get('id', '?')}: invalid signature"
            )
            return

        event_type = envelope.get("type", "")
        handlers = self._get_matching_handlers(event_type)
        for handler in handlers:
            try:
                await handler(envelope)
            except Exception as e:
                logger.error(f"Handler error for {event_type}: {e}")

    def _verify_envelope(self, envelope: dict[str, Any]) -> bool:
        """Verify the HMAC signature on an event envelope."""
        from ecosystem_auth.tokens import verify_signature

        signature = envelope.get("signature")
        if not signature:
            return False

        signable = {
            "id": envelope.get("id", ""),
            "type": envelope.get("type", ""),
            "source": envelope.get("source", ""),
            "timestamp": envelope.get("timestamp", 0),
            "data": envelope.get("data", {}),
        }
        return verify_signature(signable, signature, self._hmac_secret)

    def _get_matching_handlers(self, event_type: str) -> list[HandlerFunc]:
        """Find all handlers whose pattern matches the event type."""
        matched = []
        for pattern, handlers in self._handlers.items():
            if matches_pattern(event_type, pattern):
                matched.extend(handlers)
        return matched

    @property
    def subscriptions(self) -> list[str]:
        """Return list of event patterns this subscriber is listening for."""
        return list(self._handlers.keys())
