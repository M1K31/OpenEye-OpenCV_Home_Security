import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEcosystemEventMapper:
    def test_motion_event_payload(self):
        from backend.core.ecosystem_events import build_motion_event

        payload = build_motion_event(
            camera_id="cam_1",
            motion_areas=[{"x": 10, "y": 20, "w": 50, "h": 60, "area": 3000}],
            snapshot_path="/data/snapshots/cam1_123.jpg",
            zone_ids=[1, 3],
        )
        assert payload["event_type"] == "security.motion_detected"
        assert payload["data"]["camera_id"] == "cam_1"
        assert payload["data"]["zone_ids"] == [1, 3]
        assert len(payload["data"]["motion_areas"]) == 1

    def test_person_detected_event(self):
        from backend.core.ecosystem_events import build_face_event

        payload = build_face_event(
            camera_id="cam_2",
            person_name="Alice",
            confidence=0.92,
            is_known=True,
        )
        assert payload["event_type"] == "security.person_detected"
        assert payload["data"]["person_name"] == "Alice"
        assert payload["data"]["confidence"] == 0.92

    def test_unknown_face_event(self):
        from backend.core.ecosystem_events import build_face_event

        payload = build_face_event(
            camera_id="cam_2",
            person_name="Unknown",
            confidence=0.0,
            is_known=False,
        )
        assert payload["event_type"] == "security.alert"
        assert payload["data"]["severity"] == "warning"

    def test_intrusion_event(self):
        from backend.core.ecosystem_events import build_intrusion_event

        payload = build_intrusion_event(
            camera_id="cam_1",
            details="Repeated unknown face detections",
            recording_url="/api/recordings/42",
        )
        assert payload["event_type"] == "security.intrusion"
        assert payload["data"]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_publish_calls_ecosystem_client(self):
        from backend.core.ecosystem_events import publish_ecosystem_event

        mock_eco = MagicMock()
        mock_eco.publish = AsyncMock(return_value={"delivered": 1})

        result = await publish_ecosystem_event(
            mock_eco,
            "security.motion_detected",
            {"camera_id": "cam_1"},
        )
        mock_eco.publish.assert_called_once_with(
            "security.motion_detected", {"camera_id": "cam_1"}
        )
        assert result["delivered"] == 1

    @pytest.mark.asyncio
    async def test_publish_gracefully_handles_no_client(self):
        from backend.core.ecosystem_events import publish_ecosystem_event

        result = await publish_ecosystem_event(
            None,
            "security.motion_detected",
            {"camera_id": "cam_1"},
        )
        assert result is None
