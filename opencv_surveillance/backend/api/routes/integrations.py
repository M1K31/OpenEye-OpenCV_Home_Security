# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Smart Home Integrations API Routes
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from backend.core.auth import get_current_active_user, require_admin

router = APIRouter()
logger = logging.getLogger(__name__)


# These endpoints are NOT implemented, and now say so.
#
# Every configure route below used to accept a payload, return
# {"success": true, "message": "... configured"}, and discard the payload
# entirely — no storage, no call into the integration modules, nothing. The
# status routes then reported enabled=false forever. Verified live on
# 2026-08-03: an anonymous POST of a Home Assistant token returned success, and
# the status endpoint immediately reported the integration disabled.
#
# The payloads are third-party account credentials: Home Assistant long-lived
# tokens, Nest client secrets and refresh tokens, MQTT passwords. Accepting a
# credential, claiming success, and dropping it is worse than refusing it — the
# user believes the secret is stored and working, and has no reason to look
# again. 501 with an honest message is the correct answer until there is
# somewhere to put them.
#
# What is still missing is a persistence model: nothing in backend/database
# describes an integration, which is very likely why these were left as stubs in
# the first place. Secrets also need encrypting at rest before any of this
# stores anything real. See docs/INTEGRATIONS_ZONES_THEMES_PLAN.md workstream A.
_NOT_IMPLEMENTED = (
    "Smart-home integrations are not implemented yet. This endpoint previously "
    "reported success while discarding the credentials it was given; it now "
    "refuses them instead. No configuration has been stored."
)


def _not_implemented(kind: str):
    logger.info("Rejected %s integration config: feature not implemented", kind)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_NOT_IMPLEMENTED,
    )


# Pydantic Models


class HomeAssistantConfig(BaseModel):
    ha_url: str
    ha_token: str
    mqtt_enabled: bool = False
    mqtt_broker: Optional[str] = None
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None


class HomeKitConfig(BaseModel):
    bridge_name: str = "OpenEye Bridge"
    pin_code: str = "031-45-154"


class NestConfig(BaseModel):
    project_id: str
    client_id: str
    client_secret: str
    refresh_token: str


# NOTE: these do NOT call the modules under backend/integrations/.
#
# The previous comment here claimed "actual implementations use the existing
# integration files", and each endpoint repeated the claim. No such call exists
# anywhere: homeassistant_integration.py, homekit_integration.py and
# nest_integrations.py have zero importers in the entire codebase. A comment
# asserting a connection that was never made is worse than no comment, because
# it stops the next reader from checking.


@router.post("/integrations/homeassistant/configure")
async def configure_home_assistant(
        config: HomeAssistantConfig,
        current_user=Depends(require_admin)):
    """Configure Home Assistant integration"""
    _not_implemented("Home Assistant")


@router.get("/integrations/homeassistant/status")
def get_home_assistant_status(current_user=Depends(get_current_active_user)):
    """Get Home Assistant integration status"""
    return {
        "enabled": False,
        "note": "Not implemented — see docs/INTEGRATIONS_ZONES_THEMES_PLAN.md",
    }


@router.post("/integrations/homekit/configure")
def configure_homekit(
        config: HomeKitConfig,
        current_user=Depends(require_admin)):
    """Configure HomeKit integration"""
    _not_implemented("HomeKit")


@router.get("/integrations/homekit/status")
def get_homekit_status(current_user=Depends(get_current_active_user)):
    """Get HomeKit integration status"""
    return {
        "enabled": False,
        "note": "Not implemented — see docs/INTEGRATIONS_ZONES_THEMES_PLAN.md",
    }


@router.post("/integrations/nest/configure")
def configure_nest(
        config: NestConfig,
        current_user=Depends(require_admin)):
    """Configure Google Nest integration"""
    _not_implemented("Google Nest")


@router.get("/integrations/nest/status")
def get_nest_status(current_user=Depends(get_current_active_user)):
    """Get Nest integration status"""
    return {
        "enabled": False,
        "note": "Not implemented — see docs/INTEGRATIONS_ZONES_THEMES_PLAN.md",
    }


@router.get("/integrations/nest/devices")
async def list_nest_devices(current_user=Depends(get_current_active_user)):
    """List all Google Nest devices"""
    return {"devices": [], "note": "Not implemented — no Nest integration is wired up"}


# ============================================================================
# ECOSYSTEM INTEGRATION SYNC (v3.11.0)
# ============================================================================


from backend.api.schemas import ecosystem as eco_schema


@router.get("/integrations/", response_model=eco_schema.IntegrationsResponse)
async def get_all_integrations(current_user=Depends(get_current_active_user)):
    """
    Get all configured integrations for ecosystem sync.
    
    Used by MagicMirror ecosystem module to sync integrations.
    """
    # TODO: Load actual configuration from database/files
    return eco_schema.IntegrationsResponse(
        homeassistant=eco_schema.IntegrationConfig(configured=False),
        homekit=eco_schema.IntegrationConfig(configured=False),
        googlenest=eco_schema.IntegrationConfig(configured=False)
    )


@router.post("/integrations/sync", response_model=eco_schema.IntegrationSyncResponse)
async def sync_integrations(
        request: eco_schema.IntegrationSyncRequest,
        current_user=Depends(require_admin)):
    """
    Sync integrations from a companion app.
    
    Merges integration configurations from MagicMirror or other ecosystem apps.
    """
    # Report these as SKIPPED, not synced.
    #
    # This used to append each supplied integration to `synced` and return
    # success=True, next to a "TODO: Save ..." comment — nothing was ever
    # written. A companion app calling this was told its configuration had been
    # accepted and would have had no reason to retry or warn anyone. Reporting
    # them as skipped keeps the response shape the ecosystem expects while
    # telling the truth about what happened.
    synced = []
    skipped = []
    conflicts = []

    for name, supplied in (
        ("homeassistant", request.homeassistant),
        ("homekit", request.homekit),
        ("googlenest", request.googlenest),
    ):
        if supplied:
            skipped.append(name)

    if skipped:
        logger.info(
            "Integration sync requested for %s but storage is not implemented; "
            "reported as skipped", ", ".join(skipped))

    return eco_schema.IntegrationSyncResponse(
        success=False if skipped else True,
        synced=synced,
        skipped=skipped,
        conflicts=conflicts
    )
