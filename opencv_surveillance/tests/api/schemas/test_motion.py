# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for motion detection API schemas
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.api.schemas.motion import (
    MotionEventBase,
    MotionEventCreate,
    MotionEventResponse,
    MotionEventListResponse,
    MotionZoneBase,
    MotionZoneCreate,
    MotionZoneUpdate,
    MotionZoneResponse,
    MotionZoneListResponse,
)


class TestMotionEventBase:
    """Test MotionEventBase schema"""

    def test_valid_motion_event_base(self):
        """Test valid motion event base"""
        event = MotionEventBase(
            camera_id="front_door",
            motion_area=5000,
            motion_percentage=12.5,
            contour_count=3,
            snapshot_path="snapshots/front_door/snapshot.jpg",
            recording_path="recordings/front_door/recording.mp4",
            faces_detected=2,
            triggered_zones="zone1,zone2",
        )

        assert event.camera_id == "front_door"
        assert event.motion_area == 5000
        assert event.motion_percentage == 12.5
        assert event.contour_count == 3
        assert event.faces_detected == 2

    def test_minimal_motion_event_base(self):
        """Test minimal motion event with only required fields"""
        event = MotionEventBase(camera_id="cam1")

        assert event.camera_id == "cam1"
        assert event.motion_area is None
        assert event.motion_percentage is None
        assert event.contour_count is None
        assert event.snapshot_path is None
        assert event.recording_path is None
        assert event.faces_detected == 0
        assert event.triggered_zones is None


class TestMotionEventCreate:
    """Test MotionEventCreate schema"""

    def test_valid_motion_event_create(self):
        """Test valid motion event creation"""
        event = MotionEventCreate(
            camera_id="back_yard",
            motion_area=8000,
            motion_percentage=25.0,
        )

        assert event.camera_id == "back_yard"
        assert event.motion_area == 8000
        assert event.motion_percentage == 25.0


class TestMotionEventResponse:
    """Test MotionEventResponse schema"""

    def test_valid_motion_event_response(self):
        """Test valid motion event response"""
        now = datetime.now()
        event = MotionEventResponse(
            id=123,
            camera_id="front_door",
            detected_at=now,
            motion_area=5000,
            motion_percentage=15.5,
            snapshot_path="front_door/snapshot.jpg",
        )

        assert event.id == 123
        assert event.camera_id == "front_door"
        assert event.detected_at == now
        assert event.motion_area == 5000

    def test_normalize_snapshot_path_with_none(self):
        """Test snapshot path validator with None"""
        now = datetime.now()
        event = MotionEventResponse(
            id=1,
            camera_id="cam1",
            detected_at=now,
            snapshot_path=None,
        )

        assert event.snapshot_path is None

    def test_normalize_snapshot_path_with_prefix(self):
        """Test snapshot path validator strips data/snapshots/ prefix"""
        now = datetime.now()
        event = MotionEventResponse(
            id=1,
            camera_id="cam1",
            detected_at=now,
            snapshot_path="data/snapshots/cam1/snapshot_123.jpg",
        )

        # Should strip the 'data/snapshots/' prefix
        assert event.snapshot_path == "cam1/snapshot_123.jpg"

    def test_normalize_snapshot_path_without_prefix(self):
        """Test snapshot path validator with path without prefix"""
        now = datetime.now()
        event = MotionEventResponse(
            id=1,
            camera_id="cam1",
            detected_at=now,
            snapshot_path="cam1/snapshot.jpg",
        )

        # Should return just the filename when no prefix
        assert event.snapshot_path == "cam1/snapshot.jpg"

    def test_normalize_snapshot_path_absolute_path(self):
        """Test snapshot path validator with absolute path"""
        now = datetime.now()
        event = MotionEventResponse(
            id=1,
            camera_id="cam1",
            detected_at=now,
            snapshot_path="/home/user/openeye/data/snapshots/cam1/snapshot.jpg",
        )

        # Should return just the filename
        assert event.snapshot_path == "cam1/snapshot.jpg"


class TestMotionEventListResponse:
    """Test MotionEventListResponse schema"""

    def test_valid_motion_event_list_response(self):
        """Test valid motion event list response"""
        now = datetime.now()
        events = [
            MotionEventResponse(id=1, camera_id="cam1", detected_at=now),
            MotionEventResponse(id=2, camera_id="cam1", detected_at=now),
        ]

        response = MotionEventListResponse(
            events=events,
            total=100,
            limit=2,
            offset=0,
            has_more=True,
        )

        assert len(response.events) == 2
        assert response.total == 100
        assert response.limit == 2
        assert response.offset == 0
        assert response.has_more is True

    def test_empty_motion_event_list(self):
        """Test empty motion event list"""
        response = MotionEventListResponse(
            events=[],
            total=0,
        )

        assert len(response.events) == 0
        assert response.total == 0
        assert response.limit == 100  # Default
        assert response.offset == 0  # Default
        assert response.has_more is False  # Default


class TestMotionZoneBase:
    """Test MotionZoneBase schema"""

    def test_valid_motion_zone_base(self):
        """Test valid motion zone base"""
        zone = MotionZoneBase(
            name="Front Porch",
            zone_type="polygon",
            coordinates="[[0.1,0.1],[0.5,0.1],[0.5,0.5],[0.1,0.5]]",
            is_active=True,
            is_exclusion_zone=False,
            sensitivity_multiplier=1.5,
            color="#FF0000",
            opacity=0.5,
        )

        assert zone.name == "Front Porch"
        assert zone.zone_type == "polygon"
        assert zone.is_active is True
        assert zone.is_exclusion_zone is False
        assert zone.sensitivity_multiplier == 1.5
        assert zone.color == "#FF0000"
        assert zone.opacity == 0.5

    def test_motion_zone_defaults(self):
        """Test motion zone with default values"""
        zone = MotionZoneBase(
            name="Test Zone",
            coordinates="[[0,0],[1,0],[1,1],[0,1]]",
        )

        assert zone.zone_type == "polygon"
        assert zone.is_active is True
        assert zone.is_exclusion_zone is False
        assert zone.sensitivity_multiplier == 1.0
        assert zone.color == "#00FF00"
        assert zone.opacity == 0.3

    def test_zone_name_min_length(self):
        """Test zone name minimum length validation"""
        with pytest.raises(ValidationError) as exc_info:
            MotionZoneBase(
                name="",  # Empty string
                coordinates="[[0,0]]",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_zone_name_max_length(self):
        """Test zone name maximum length validation"""
        long_name = "a" * 101  # 101 characters
        with pytest.raises(ValidationError) as exc_info:
            MotionZoneBase(
                name=long_name,
                coordinates="[[0,0]]",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_zone_type_validation(self):
        """Test zone_type must be polygon or rectangle"""
        # Valid types
        for valid_type in ["polygon", "rectangle"]:
            zone = MotionZoneBase(
                name="Test",
                zone_type=valid_type,
                coordinates="[[0,0]]",
            )
            assert zone.zone_type == valid_type

        # Invalid type
        with pytest.raises(ValidationError) as exc_info:
            MotionZoneBase(
                name="Test",
                zone_type="circle",  # Invalid
                coordinates="[[0,0]]",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("zone_type",) for error in errors)

    def test_sensitivity_multiplier_range(self):
        """Test sensitivity_multiplier must be between 0.0 and 10.0"""
        # Valid values
        for value in [0.0, 5.0, 10.0]:
            zone = MotionZoneBase(
                name="Test",
                coordinates="[[0,0]]",
                sensitivity_multiplier=value,
            )
            assert zone.sensitivity_multiplier == value

        # Invalid values
        for invalid_value in [-0.1, 10.1]:
            with pytest.raises(ValidationError) as exc_info:
                MotionZoneBase(
                    name="Test",
                    coordinates="[[0,0]]",
                    sensitivity_multiplier=invalid_value,
                )

            errors = exc_info.value.errors()
            assert any(error["loc"] == ("sensitivity_multiplier",) for error in errors)

    def test_color_validation(self):
        """Test color must be valid hex color"""
        # Valid colors
        for valid_color in ["#000000", "#FFFFFF", "#FF00FF", "#abc123"]:
            zone = MotionZoneBase(
                name="Test",
                coordinates="[[0,0]]",
                color=valid_color,
            )
            assert zone.color.upper() == valid_color.upper()

        # Invalid colors
        for invalid_color in ["#GGG", "#12345", "red", "000000"]:
            with pytest.raises(ValidationError) as exc_info:
                MotionZoneBase(
                    name="Test",
                    coordinates="[[0,0]]",
                    color=invalid_color,
                )

            errors = exc_info.value.errors()
            assert any(error["loc"] == ("color",) for error in errors)

    def test_opacity_range(self):
        """Test opacity must be between 0.0 and 1.0"""
        # Valid values
        for value in [0.0, 0.5, 1.0]:
            zone = MotionZoneBase(
                name="Test",
                coordinates="[[0,0]]",
                opacity=value,
            )
            assert zone.opacity == value

        # Invalid values
        for invalid_value in [-0.1, 1.1]:
            with pytest.raises(ValidationError) as exc_info:
                MotionZoneBase(
                    name="Test",
                    coordinates="[[0,0]]",
                    opacity=invalid_value,
                )

            errors = exc_info.value.errors()
            assert any(error["loc"] == ("opacity",) for error in errors)


class TestMotionZoneCreate:
    """Test MotionZoneCreate schema"""

    def test_valid_motion_zone_create(self):
        """Test valid motion zone creation"""
        zone = MotionZoneCreate(
            name="Driveway",
            camera_id="front_cam",
            coordinates="[[0.2,0.2],[0.8,0.2],[0.8,0.8],[0.2,0.8]]",
        )

        assert zone.name == "Driveway"
        assert zone.camera_id == "front_cam"
        assert zone.coordinates is not None

    def test_camera_id_required(self):
        """Test camera_id is required for creation"""
        with pytest.raises(ValidationError) as exc_info:
            MotionZoneCreate(
                name="Test Zone",
                coordinates="[[0,0]]",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("camera_id",) for error in errors)


class TestMotionZoneUpdate:
    """Test MotionZoneUpdate schema"""

    def test_valid_motion_zone_update(self):
        """Test valid motion zone update with some fields"""
        update = MotionZoneUpdate(
            name="Updated Name",
            is_active=False,
            sensitivity_multiplier=2.5,
        )

        assert update.name == "Updated Name"
        assert update.is_active is False
        assert update.sensitivity_multiplier == 2.5
        # Other fields should be None
        assert update.zone_type is None
        assert update.coordinates is None

    def test_motion_zone_update_all_optional(self):
        """Test all fields are optional for update"""
        update = MotionZoneUpdate()

        assert update.name is None
        assert update.zone_type is None
        assert update.coordinates is None
        assert update.is_active is None
        assert update.is_exclusion_zone is None
        assert update.sensitivity_multiplier is None
        assert update.color is None
        assert update.opacity is None

    def test_update_name_min_length(self):
        """Test update name validation"""
        with pytest.raises(ValidationError) as exc_info:
            MotionZoneUpdate(name="")  # Empty string

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)


class TestMotionZoneResponse:
    """Test MotionZoneResponse schema"""

    def test_valid_motion_zone_response(self):
        """Test valid motion zone response"""
        now = datetime.now()
        zone = MotionZoneResponse(
            id=456,
            name="Backyard",
            camera_id="back_cam",
            zone_type="rectangle",
            coordinates="[[0,0],[1,1]]",
            created_at=now,
            updated_at=now,
            motion_events_count=25,
            last_motion_at=now,
        )

        assert zone.id == 456
        assert zone.name == "Backyard"
        assert zone.camera_id == "back_cam"
        assert zone.motion_events_count == 25
        assert zone.last_motion_at == now

    def test_motion_zone_response_defaults(self):
        """Test motion zone response with default values"""
        now = datetime.now()
        zone = MotionZoneResponse(
            id=1,
            name="Test",
            camera_id="cam1",
            coordinates="[[0,0]]",
            created_at=now,
            updated_at=now,
        )

        assert zone.motion_events_count == 0
        assert zone.last_motion_at is None


class TestMotionZoneListResponse:
    """Test MotionZoneListResponse schema"""

    def test_valid_motion_zone_list_response(self):
        """Test valid motion zone list response"""
        now = datetime.now()
        zones = [
            MotionZoneResponse(
                id=1,
                name="Zone 1",
                camera_id="cam1",
                coordinates="[[0,0]]",
                created_at=now,
                updated_at=now,
            ),
            MotionZoneResponse(
                id=2,
                name="Zone 2",
                camera_id="cam1",
                coordinates="[[0,0]]",
                created_at=now,
                updated_at=now,
            ),
        ]

        response = MotionZoneListResponse(
            zones=zones,
            total=2,
            camera_id="cam1",
        )

        assert len(response.zones) == 2
        assert response.total == 2
        assert response.camera_id == "cam1"

    def test_empty_motion_zone_list(self):
        """Test empty motion zone list"""
        response = MotionZoneListResponse(
            zones=[],
            total=0,
            camera_id="cam1",
        )

        assert len(response.zones) == 0
        assert response.total == 0
        assert response.camera_id == "cam1"
