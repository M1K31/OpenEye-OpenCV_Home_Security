# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Cloud AI Provider Key Management

Keys for Anthropic / OpenAI / Gemini live in the shared ecosystem credential
store (~/.config/ecosystem/provider_keys.json, mode 0600) behind the registry's
/ai/providers endpoints. This router lets OpenEye's settings UI manage them
without the browser ever talking to the registry directly.

Security posture mirrors the ecosystem-secret endpoints elsewhere in the fleet:
  - every route requires an admin user
  - writes/deletes additionally require a loopback caller, 404-cloaked
  - no route ever returns a key; reads expose only configured/last4/updated_at
  - request bodies are never logged
"""
from typing import Any, Optional

import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.core.auth import require_admin
from backend.api.schemas import user as user_schema

logger = logging.getLogger(__name__)

router = APIRouter()

REGISTRY_URL = os.environ.get("ECOSYSTEM_REGISTRY_URL", "http://localhost:8500")
_TIMEOUT = 8.0
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

# Tasks exposed for per-task provider routing. Cloud usage is metered, so the
# point is to spend it selectively rather than flipping one global switch.
ROUTABLE_TASKS = ("chat", "security", "embed")


class ProviderKeyBody(BaseModel):
    api_key: str


class RoutingBody(BaseModel):
    task_providers: dict[str, str]
    allow_cloud_fallback: Optional[bool] = None


def _require_loopback(request: Request) -> None:
    """Writes are loopback-only and 404-cloaked.

    A forwarded header means the request crossed a proxy, so it is not a genuine
    local caller even when request.client looks local.
    """
    if request.headers.get("x-forwarded-for"):
        raise HTTPException(status_code=404, detail="Not found")
    host = (request.client.host if request.client else "") or ""
    if host not in _LOOPBACK_HOSTS:
        raise HTTPException(status_code=404, detail="Not found")


def _signed_headers(method: str, url: str, body: Optional[dict] = None) -> dict:
    from ecosystem_auth.tokens import get_ecosystem_secret, sign_request

    return sign_request(method, url, get_ecosystem_secret(), body)


async def _registry(method: str, path: str, body: Optional[dict] = None) -> Any:
    """Call the registry, turning transport problems into clean HTTP errors."""
    url = f"{REGISTRY_URL}{path}"
    try:
        headers = _signed_headers(method, url, body)
    except Exception as e:
        logger.warning("Cannot sign registry request: %s", e.__class__.__name__)
        raise HTTPException(
            status_code=503,
            detail="Ecosystem secret is not provisioned; run `ecosystem secret generate`.",
        )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.request(method, url, headers=headers, json=body)
    except Exception as e:
        logger.warning("Registry unreachable: %s", e.__class__.__name__)
        raise HTTPException(status_code=503, detail="Ecosystem registry is unreachable.")

    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", "registry rejected the request")
        except Exception:
            detail = "registry rejected the request"
        raise HTTPException(status_code=resp.status_code, detail=detail)
    return resp.json()


@router.get("/providers")
async def list_providers(
    current_user: user_schema.User = Depends(require_admin),
) -> dict:
    """Masked status for each provider. Never returns a key."""
    return await _registry("GET", "/ai/providers")


@router.put("/providers/{provider}/key")
async def set_provider_key(
    provider: str,
    body: ProviderKeyBody,
    request: Request,
    current_user: user_schema.User = Depends(require_admin),
) -> dict:
    """Store a provider API key. Admin + loopback only."""
    _require_loopback(request)
    # Deliberately not logged — this body carries the secret.
    return await _registry("PUT", f"/ai/providers/{provider}/key", {"api_key": body.api_key})


@router.delete("/providers/{provider}/key")
async def delete_provider_key(
    provider: str,
    request: Request,
    current_user: user_schema.User = Depends(require_admin),
) -> dict:
    """Remove a stored provider API key. Admin + loopback only."""
    _require_loopback(request)
    return await _registry("DELETE", f"/ai/providers/{provider}/key")


@router.get("/providers/routing")
async def get_routing(
    current_user: user_schema.User = Depends(require_admin),
) -> dict:
    """Per-task provider routing from the shared ecosystem AI profile."""
    data = await _registry("GET", "/ai-profile")
    prof = data.get("profile", data) if isinstance(data, dict) else {}
    return {
        "default_provider": prof.get("default_provider", "ollama"),
        "task_providers": prof.get("task_providers") or {},
        "allow_cloud_fallback": prof.get("allow_cloud_fallback", True),
        "cloud": {k: bool(v.get("enabled")) for k, v in (prof.get("cloud") or {}).items()},
        "tasks": list(ROUTABLE_TASKS),
    }


@router.put("/providers/routing")
async def set_routing(
    body: RoutingBody,
    request: Request,
    current_user: user_schema.User = Depends(require_admin),
) -> dict:
    """Set which provider serves each task.

    Selecting a cloud provider also ENABLES it in the shared profile —
    build_providers() only constructs an enabled provider, so without this the
    choice would silently do nothing.

    Note this writes the SHARED ecosystem profile: the change affects every app
    on this machine, not just OpenEye. That is intended — one AI configuration
    for the whole ecosystem.
    """
    _require_loopback(request)

    current = await _registry("GET", "/ai-profile")
    prof = current.get("profile", current) if isinstance(current, dict) else {}
    cloud = {k: dict(v) for k, v in (prof.get("cloud") or {}).items()}

    task_providers = {t: (body.task_providers.get(t) or "") for t in ROUTABLE_TASKS}
    for chosen in task_providers.values():
        if chosen and chosen in cloud:
            cloud[chosen]["enabled"] = True

    payload: dict[str, Any] = {"task_providers": task_providers, "cloud": cloud}
    if body.allow_cloud_fallback is not None:
        payload["allow_cloud_fallback"] = body.allow_cloud_fallback

    await _registry("PUT", "/ai-profile", payload)
    return await get_routing(current_user=current_user)
