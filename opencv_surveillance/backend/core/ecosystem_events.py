"""Map OpenEye alert types to ecosystem event types and publish."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_motion_event(
    camera_id: str,
    motion_areas: list[dict],
    snapshot_path: str | None = None,
    zone_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Build a security.motion_detected event payload."""
    return {
        "event_type": "security.motion_detected",
        "data": {
            "camera_id": camera_id,
            "motion_areas": motion_areas,
            "snapshot_path": snapshot_path,
            "zone_ids": zone_ids or [],
        },
    }


def build_face_event(
    camera_id: str,
    person_name: str,
    confidence: float,
    is_known: bool,
) -> dict[str, Any]:
    """Build a security.person_detected or security.alert event."""
    if is_known:
        return {
            "event_type": "security.person_detected",
            "data": {
                "camera_id": camera_id,
                "person_name": person_name,
                "confidence": confidence,
            },
        }
    return {
        "event_type": "security.alert",
        "data": {
            "camera_id": camera_id,
            "person_name": person_name,
            "confidence": confidence,
            "severity": "warning",
            "reason": "unknown_person",
        },
    }


def build_intrusion_event(
    camera_id: str,
    details: str,
    recording_url: str | None = None,
) -> dict[str, Any]:
    """Build a security.intrusion event payload."""
    return {
        "event_type": "security.intrusion",
        "data": {
            "camera_id": camera_id,
            "details": details,
            "recording_url": recording_url,
            "severity": "critical",
        },
    }


async def publish_ecosystem_event(
    eco_client,
    event_type: str,
    data: dict[str, Any],
) -> dict | None:
    """Publish an event via the ecosystem client. No-op if client is None."""
    if eco_client is None:
        return None
    try:
        return await eco_client.publish(event_type, data)
    except Exception as e:
        logger.debug(f"Ecosystem publish failed for {event_type}: {e}")
        return None
