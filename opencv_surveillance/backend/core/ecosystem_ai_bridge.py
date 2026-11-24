"""Optional LLM capability for OpenEye via the shared ecosystem AI layer.

OpenEye's core intelligence is computer vision; it has no built-in LLM. This
bridge gives it an *optional*, Ollama-default LLM path (cloud providers opt-in)
through the shared `ecosystem_ai` package, plus access to the ecosystem-wide AI
profile so any LLM use matches what the user selected in other apps.

Everything is best-effort and guarded: if `ecosystem_ai` isn't installed or no
provider is reachable, the helpers return None and OpenEye runs unchanged.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

SERVICE_NAME = "openeye"


def _make_profile_client():
    """Build an AIProfileClient from ecosystem env config, or None if the AI
    layer / auth isn't available."""
    try:
        from ecosystem_ai import AIProfileClient
        from ecosystem_auth.tokens import sign_request
    except Exception:
        return None

    registry_url = os.environ.get("ECOSYSTEM_REGISTRY_URL", "http://localhost:8500")
    secret = os.environ.get("ECOSYSTEM_HMAC_SECRET")
    if not secret:
        # Fail-closed: without a shared secret we cannot authenticate reads.
        return None

    # A weak secret is refused on the same footing as a missing one.
    #
    # The API route that manages this secret validates it (hex, 32-128 chars,
    # see routes/settings.py), but setting the environment variable directly —
    # in .env, in compose, or in a shell — bypassed that entirely and the value
    # was used to sign peer requests as-is. Since it authenticates requests
    # BETWEEN devices, a guessable one lets anything on the network impersonate
    # this installation to its peers.
    #
    # Fail closed rather than warn: peering silently disabled is recoverable and
    # visible in the log, peering running on a guessable key is neither.
    from backend.core.auth import is_weak_secret

    if is_weak_secret(secret):
        logger.error(
            "ECOSYSTEM_HMAC_SECRET is empty, too short (under 32 characters) or a "
            "known placeholder. Ecosystem peering is disabled rather than signed "
            "with a guessable key. Generate one with `openssl rand -hex 32` and "
            "set the same value on every peer."
        )
        return None

    def signer(method: str, url: str, body: Optional[dict]) -> dict:
        return sign_request(method, url, secret, body)

    return AIProfileClient(registry_url, service_name=SERVICE_NAME, signer=signer)


async def shared_selected_model() -> Optional[str]:
    """Return the ecosystem-wide selected model, or None if unavailable."""
    client = _make_profile_client()
    if client is None:
        return None
    try:
        profile = await client.fetch()
        return profile.selected_model
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("Could not read shared model selection: %s", e)
        return None
    finally:
        try:
            await client.aclose()
        except Exception:
            pass


async def summarize_event(prompt: str) -> Optional[str]:
    """Best-effort natural-language summary of a surveillance event using the
    ecosystem's selected LLM (Ollama by default). Returns None if no provider is
    available, so callers degrade gracefully.

    Example caller (not wired by default):
        text = await summarize_event("Person detected at front door, 02:14.")
    """
    try:
        from ecosystem_ai import build_router, default_profile, detect, ChatMessage
    except Exception:
        return None

    client = _make_profile_client()
    profile = None
    if client is not None:
        try:
            profile = await client.fetch()
        except Exception:
            profile = None
        finally:
            try:
                await client.aclose()
            except Exception:
                pass
    if profile is None:
        profile = default_profile()

    try:
        _, tier = detect()
        router = build_router(profile, tier=tier)
        result = await router.chat([ChatMessage("user", prompt)])
        return result.text
    except Exception as e:
        logger.debug("LLM summary unavailable: %s", e)
        return None
