# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for database CRUD operations
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.database import crud, models
from backend.api.schemas.user import UserCreate


class TestUserCRUD:
    """Test User CRUD operations"""

    def test_get_user_by_username_exists(self, db_session: Session):
        """Test retrieving existing user by username"""
        # Create test user
        user_data = UserCreate(username="testuser", email="test@example.com", password="testpass123")
        created_user = crud.create_user(db_session, user_data)

        # Retrieve user
        retrieved_user = crud.get_user_by_username(db_session, "testuser")

        assert retrieved_user is not None
        assert retrieved_user.username == "testuser"
        assert retrieved_user.email == "test@example.com"
        assert retrieved_user.id == created_user.id

    def test_get_user_by_username_not_exists(self, db_session: Session):
        """Test retrieving non-existent user returns None"""
        retrieved_user = crud.get_user_by_username(db_session, "nonexistent")
        assert retrieved_user is None

    def test_create_user(self, db_session: Session):
        """Test user creation"""
        user_data = UserCreate(username="newuser", email="new@example.com", password="securepass")
        created_user = crud.create_user(db_session, user_data)

        assert created_user.id is not None
        assert created_user.username == "newuser"
        assert created_user.email == "new@example.com"
        # Password should be hashed, not plain text
        assert created_user.hashed_password != "securepass"
        assert len(created_user.hashed_password) > 20  # Bcrypt hashes are long

    def test_get_user_by_id(self, db_session: Session):
        """Test retrieving user by ID"""
        user_data = UserCreate(username="idtest", email="id@example.com", password="pass123")
        created_user = crud.create_user(db_session, user_data)

        retrieved_user = crud.get_user(db_session, created_user.id)

        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.username == "idtest"

    def test_get_user_by_id_not_exists(self, db_session: Session):
        """Test retrieving non-existent user by ID returns None"""
        retrieved_user = crud.get_user(db_session, 99999)
        assert retrieved_user is None


class TestCameraCRUD:
    """Test Camera CRUD operations"""

    def test_get_camera_by_id_exists(self, db_session: Session):
        """Test retrieving existing camera by camera_id"""
        camera_data = {
            "camera_id": "test_cam_1",
            "camera_type": "Test Camera",
            "source": "rtsp://test",
            "is_active": True
        }
        created_camera = crud.create_camera(db_session, camera_data)

        retrieved_camera = crud.get_camera_by_id(db_session, "test_cam_1")

        assert retrieved_camera is not None
        assert retrieved_camera.camera_id == "test_cam_1"
        assert retrieved_camera.camera_type == "Test Camera"

    def test_get_camera_by_id_not_exists(self, db_session: Session):
        """Test retrieving non-existent camera returns None"""
        retrieved_camera = crud.get_camera_by_id(db_session, "nonexistent_cam")
        assert retrieved_camera is None

    def test_get_camera_by_pk(self, db_session: Session):
        """Test retrieving camera by primary key"""
        camera_data = {
            "camera_id": "pk_test_cam",
            "camera_type": "PK Test Camera",
            "source": "rtsp://pktest",
            "is_active": True
        }
        created_camera = crud.create_camera(db_session, camera_data)

        retrieved_camera = crud.get_camera_by_pk(db_session, created_camera.id)

        assert retrieved_camera is not None
        assert retrieved_camera.id == created_camera.id
        assert retrieved_camera.camera_id == "pk_test_cam"

    def test_get_camera_by_pk_not_exists(self, db_session: Session):
        """Test retrieving non-existent camera by PK returns None"""
        retrieved_camera = crud.get_camera_by_pk(db_session, 99999)
        assert retrieved_camera is None

    def test_get_cameras_empty(self, db_session: Session):
        """Test getting cameras from empty database"""
        cameras = crud.get_cameras(db_session)
        assert cameras == []

    def test_get_cameras_with_data(self, db_session: Session):
        """Test getting multiple cameras"""
        # Create multiple cameras
        for i in range(5):
            camera_data = {
                "camera_id": f"cam_{i}",
                "camera_type": f"Camera {i}",
                "source": f"rtsp://test{i}",
                "is_active": True
            }
            crud.create_camera(db_session, camera_data)

        cameras = crud.get_cameras(db_session)

        assert len(cameras) == 5
        assert all(cam.camera_id.startswith("cam_") for cam in cameras)

    def test_get_cameras_pagination(self, db_session: Session):
        """Test camera pagination"""
        # Create 10 cameras
        for i in range(10):
            camera_data = {
                "camera_id": f"pag_cam_{i}",
                "camera_type": f"Pagination Camera {i}",
                "source": f"rtsp://pag{i}",
                "is_active": True
            }
            crud.create_camera(db_session, camera_data)

        # Get first page (skip 0, limit 5)
        page1 = crud.get_cameras(db_session, skip=0, limit=5)
        assert len(page1) == 5

        # Get second page (skip 5, limit 5)
        page2 = crud.get_cameras(db_session, skip=5, limit=5)
        assert len(page2) == 5

        # Ensure pages don't overlap
        page1_ids = {cam.camera_id for cam in page1}
        page2_ids = {cam.camera_id for cam in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_get_active_cameras_only(self, db_session: Session):
        """Test retrieving only active cameras"""
        # Create active cameras
        for i in range(3):
            camera_data = {
                "camera_id": f"active_cam_{i}",
                "camera_type": f"Active Camera {i}",
                "source": f"rtsp://active{i}",
                "is_active": True
            }
            crud.create_camera(db_session, camera_data)

        # Create inactive cameras
        for i in range(2):
            camera_data = {
                "camera_id": f"inactive_cam_{i}",
                "camera_type": f"Inactive Camera {i}",
                "source": f"rtsp://inactive{i}",
                "is_active": False
            }
            crud.create_camera(db_session, camera_data)

        active_cameras = crud.get_active_cameras(db_session)

        assert len(active_cameras) == 3
        assert all(cam.is_active for cam in active_cameras)
        assert all(cam.camera_id.startswith("active_") for cam in active_cameras)

    def test_create_camera(self, db_session: Session):
        """Test camera creation"""
        camera_data = {
            "camera_id": "new_camera",
            "camera_type": "New Test Camera",
            "source": "rtsp://new",
            "is_active": True,
            "motion_detection_enabled": True,
            "face_detection_enabled": False
        }
        created_camera = crud.create_camera(db_session, camera_data)

        assert created_camera.id is not None
        assert created_camera.camera_id == "new_camera"
        assert created_camera.camera_type == "New Test Camera"
        assert created_camera.is_active is True
        assert created_camera.motion_detection_enabled is True
        assert created_camera.face_detection_enabled is False

    def test_update_camera_success(self, db_session: Session):
        """Test successful camera update"""
        # Create camera
        camera_data = {
            "camera_id": "update_cam",
            "camera_type": "Original Name",
            "source": "rtsp://original",
            "is_active": True
        }
        created_camera = crud.create_camera(db_session, camera_data)

        # Update camera
        update_data = {
            "camera_type": "Updated Name",
            "motion_detection_enabled": True
        }
        updated_camera = crud.update_camera(db_session, "update_cam", update_data)

        assert updated_camera is not None
        assert updated_camera.camera_id == "update_cam"
        assert updated_camera.camera_type == "Updated Name"
        assert updated_camera.motion_detection_enabled is True
        # Original source should be unchanged
        assert updated_camera.source == "rtsp://original"

    def test_update_camera_not_found(self, db_session: Session):
        """Test updating non-existent camera returns None"""
        update_data = {"camera_type": "Updated"}
        result = crud.update_camera(db_session, "nonexistent_cam", update_data)
        assert result is None

    def test_delete_camera_success(self, db_session: Session):
        """Test successful camera deletion"""
        # Create camera
        camera_data = {
            "camera_id": "delete_cam",
            "camera_type": "To Be Deleted",
            "source": "rtsp://delete",
            "is_active": True
        }
        crud.create_camera(db_session, camera_data)

        # Delete camera
        result = crud.delete_camera(db_session, "delete_cam")
        assert result is True

        # Verify deletion
        deleted_camera = crud.get_camera_by_id(db_session, "delete_cam")
        assert deleted_camera is None

    def test_delete_camera_not_found(self, db_session: Session):
        """Test deleting non-existent camera returns False"""
        result = crud.delete_camera(db_session, "nonexistent_cam")
        assert result is False

    def test_deactivate_camera_success(self, db_session: Session):
        """Test deactivating camera"""
        # Create active camera
        camera_data = {
            "camera_id": "deactivate_cam",
            "camera_type": "Active Camera",
            "source": "rtsp://deactivate",
            "is_active": True
        }
        crud.create_camera(db_session, camera_data)

        # Deactivate camera
        deactivated_camera = crud.deactivate_camera(db_session, "deactivate_cam")

        assert deactivated_camera is not None
        assert deactivated_camera.camera_id == "deactivate_cam"
        assert deactivated_camera.is_active is False

    def test_deactivate_camera_not_found(self, db_session: Session):
        """Test deactivating non-existent camera returns None"""
        result = crud.deactivate_camera(db_session, "nonexistent_cam")
        assert result is None

    def test_update_camera_last_active(self, db_session: Session):
        """Test updating camera last_active timestamp"""
        # Create camera
        camera_data = {
            "camera_id": "last_active_cam",
            "camera_type": "Last Active Test",
            "source": "rtsp://lastactive",
            "is_active": True
        }
        created_camera = crud.create_camera(db_session, camera_data)
        original_last_active = created_camera.last_active_at

        # Update last_active
        updated_camera = crud.update_camera_last_active(db_session, "last_active_cam")

        assert updated_camera is not None
        assert updated_camera.last_active_at is not None
        # Last active should be updated (different from original)
        if original_last_active is not None:
            assert updated_camera.last_active_at >= original_last_active

    def test_update_camera_last_active_not_found(self, db_session: Session):
        """Test updating last_active for non-existent camera returns None"""
        result = crud.update_camera_last_active(db_session, "nonexistent_cam")
        assert result is None


class TestSystemSettingsCRUD:
    """Test System Settings CRUD operations"""

    def test_get_system_setting_exists(self, db_session: Session):
        """Test retrieving existing system setting"""
        # Create setting
        setting_data = {
            "setting_key": "test_key",
            "setting_value": "test_value",
            "setting_type": "string",
            "description": "Test setting"
        }
        crud.set_system_setting(db_session, **setting_data)

        # Retrieve setting
        retrieved_setting = crud.get_system_setting(db_session, "test_key")

        assert retrieved_setting is not None
        assert retrieved_setting.setting_key == "test_key"
        assert retrieved_setting.setting_value == "test_value"
        assert retrieved_setting.setting_type == "string"

    def test_get_system_setting_not_exists(self, db_session: Session):
        """Test retrieving non-existent setting returns None"""
        retrieved_setting = crud.get_system_setting(db_session, "nonexistent_key")
        assert retrieved_setting is None

    def test_get_all_system_settings_empty(self, db_session: Session):
        """Test getting all settings from empty database"""
        settings = crud.get_all_system_settings(db_session)
        assert settings == []

    def test_get_all_system_settings_with_data(self, db_session: Session):
        """Test getting all system settings"""
        # Create multiple settings
        for i in range(5):
            setting_data = {
                "setting_key": f"key_{i}",
                "setting_value": f"value_{i}",
                "setting_type": "string",
                "description": f"Test setting {i}"
            }
            crud.set_system_setting(db_session, **setting_data)

        settings = crud.get_all_system_settings(db_session)

        assert len(settings) == 5
        assert all(s.setting_key.startswith("key_") for s in settings)

    def test_set_system_setting_create(self, db_session: Session):
        """Test creating new system setting"""
        setting_data = {
            "setting_key": "new_setting",
            "setting_value": "new_value",
            "setting_type": "string",
            "description": "New test setting"
        }
        created_setting = crud.set_system_setting(db_session, **setting_data)

        assert created_setting is not None
        assert created_setting.setting_key == "new_setting"
        assert created_setting.setting_value == "new_value"
        assert created_setting.setting_type == "string"
        assert created_setting.description == "New test setting"

    def test_set_system_setting_update(self, db_session: Session):
        """Test updating existing system setting"""
        # Create initial setting
        initial_data = {
            "setting_key": "update_setting",
            "setting_value": "initial_value",
            "setting_type": "string",
            "description": "Initial description"
        }
        crud.set_system_setting(db_session, **initial_data)

        # Update setting
        update_data = {
            "setting_key": "update_setting",
            "setting_value": "updated_value",
            "setting_type": "string",
            "description": "Updated description"
        }
        updated_setting = crud.set_system_setting(db_session, **update_data)

        assert updated_setting.setting_value == "updated_value"
        assert updated_setting.description == "Updated description"

        # Verify only one setting exists
        all_settings = crud.get_all_system_settings(db_session)
        matching_settings = [s for s in all_settings if s.setting_key == "update_setting"]
        assert len(matching_settings) == 1

    def test_delete_system_setting_success(self, db_session: Session):
        """Test deleting system setting"""
        # Create setting
        setting_data = {
            "setting_key": "delete_setting",
            "setting_value": "delete_value",
            "setting_type": "string",
            "description": "To be deleted"
        }
        crud.set_system_setting(db_session, **setting_data)

        # Delete setting
        result = crud.delete_system_setting(db_session, "delete_setting")
        assert result is True

        # Verify deletion
        deleted_setting = crud.get_system_setting(db_session, "delete_setting")
        assert deleted_setting is None

    def test_delete_system_setting_not_found(self, db_session: Session):
        """Test deleting non-existent setting returns False"""
        result = crud.delete_system_setting(db_session, "nonexistent_setting")
        assert result is False

    def test_initialize_default_settings(self, db_session: Session):
        """Test initializing default system settings"""
        # Initialize defaults
        crud.initialize_default_settings(db_session)

        # Verify default settings were created
        all_settings = crud.get_all_system_settings(db_session)
        assert len(all_settings) > 0  # Should have created default settings

        # Check for some expected default keys
        setting_keys = {s.setting_key for s in all_settings}
        expected_keys = {"recordings_path", "faces_path", "display_mode"}
        assert expected_keys.issubset(setting_keys)


class TestRefreshTokenCRUD:
    """Test Refresh Token CRUD operations"""

    def test_create_refresh_token(self, db_session: Session):
        """Test creating refresh token"""
        # Create user first
        user_data = UserCreate(username="tokenuser", email="token@example.com", password="pass123")
        user = crud.create_user(db_session, user_data)

        # Create refresh token
        token_string = "test_refresh_token_12345"
        expires_delta = timedelta(days=7)
        created_token = crud.create_refresh_token(
            db_session,
            token=token_string,
            user_id=user.id,
            expires_delta=expires_delta
        )

        assert created_token.id is not None
        assert created_token.token == token_string
        assert created_token.user_id == user.id
        assert created_token.revoked is False
        assert created_token.expires_at > datetime.utcnow()

    def test_get_refresh_token_exists(self, db_session: Session):
        """Test retrieving existing refresh token"""
        # Create user and token
        user_data = UserCreate(username="gettoken", email="get@example.com", password="pass123")
        user = crud.create_user(db_session, user_data)

        token_string = "get_token_12345"
        crud.create_refresh_token(db_session, token=token_string, user_id=user.id)

        # Retrieve token
        retrieved_token = crud.get_refresh_token(db_session, token_string)

        assert retrieved_token is not None
        assert retrieved_token.token == token_string
        assert retrieved_token.user_id == user.id

    def test_get_refresh_token_not_exists(self, db_session: Session):
        """Test retrieving non-existent token returns None"""
        retrieved_token = crud.get_refresh_token(db_session, "nonexistent_token")
        assert retrieved_token is None

    def test_get_user_refresh_tokens(self, db_session: Session):
        """Test getting all tokens for a user"""
        # Create user
        user_data = UserCreate(username="multitoken", email="multi@example.com", password="pass123")
        user = crud.create_user(db_session, user_data)

        # Create multiple tokens for user
        for i in range(3):
            token_string = f"user_token_{i}"
            crud.create_refresh_token(db_session, token=token_string, user_id=user.id)

        # Get user's tokens
        user_tokens = crud.get_user_refresh_tokens(db_session, user.id)

        assert len(user_tokens) == 3
        assert all(t.user_id == user.id for t in user_tokens)

    def test_get_user_refresh_tokens_empty(self, db_session: Session):
        """Test getting tokens for user with no tokens"""
        # Create user without tokens
        user_data = UserCreate(username="notokens", email="notokens@example.com", password="pass123")
        user = crud.create_user(db_session, user_data)

        user_tokens = crud.get_user_refresh_tokens(db_session, user.id)
        assert user_tokens == []

    def test_revoke_refresh_token_success(self, db_session: Session):
        """Test revoking refresh token"""
        # Create user and token
        user_data = UserCreate(username="revoketoken", email="revoke@example.com", password="pass123")
        user = crud.create_user(db_session, user_data)

        token_string = "revoke_token_12345"
        crud.create_refresh_token(db_session, token=token_string, user_id=user.id)

        # Revoke token
        result = crud.revoke_refresh_token(db_session, token_string)
        assert result is True

        # Verify token is revoked
        revoked_token = crud.get_refresh_token(db_session, token_string)
        assert revoked_token.revoked is True

    def test_revoke_refresh_token_not_found(self, db_session: Session):
        """Test revoking non-existent token returns False"""
        result = crud.revoke_refresh_token(db_session, "nonexistent_token")
        assert result is False

    def test_revoke_all_user_tokens(self, db_session: Session):
        """Test revoking all tokens for a user"""
        # Create user with multiple tokens
        user_data = UserCreate(username="revokeall", email="revokeall@example.com", password="pass123")
        user = crud.create_user(db_session, user_data)

        for i in range(5):
            token_string = f"revoke_all_token_{i}"
            crud.create_refresh_token(db_session, token=token_string, user_id=user.id)

        # Revoke all user tokens
        revoked_count = crud.revoke_all_user_tokens(db_session, user.id)
        assert revoked_count == 5

        # Verify all tokens are revoked
        user_tokens = crud.get_user_refresh_tokens(db_session, user.id)
        assert all(t.revoked for t in user_tokens)

    def test_revoke_all_user_tokens_no_tokens(self, db_session: Session):
        """Test revoking all tokens for user with no tokens"""
        # Create user without tokens
        user_data = UserCreate(username="revokeempty", email="revokeempty@example.com", password="pass123")
        user = crud.create_user(db_session, user_data)

        revoked_count = crud.revoke_all_user_tokens(db_session, user.id)
        assert revoked_count == 0

    def test_delete_expired_tokens(self, db_session: Session):
        """Test deleting expired tokens"""
        # Create user
        user_data = UserCreate(username="expireduser", email="expired@example.com", password="pass123")
        user = crud.create_user(db_session, user_data)

        # Create expired token (negative expiry)
        expired_token = "expired_token_12345"
        expired_delta = timedelta(days=-7)  # Expired 7 days ago
        crud.create_refresh_token(db_session, token=expired_token, user_id=user.id, expires_delta=expired_delta)

        # Create valid token
        valid_token = "valid_token_12345"
        valid_delta = timedelta(days=7)  # Expires in 7 days
        crud.create_refresh_token(db_session, token=valid_token, user_id=user.id, expires_delta=valid_delta)

        # Delete expired tokens
        deleted_count = crud.delete_expired_tokens(db_session)
        assert deleted_count == 1

        # Verify expired token is deleted
        assert crud.get_refresh_token(db_session, expired_token) is None

        # Verify valid token remains
        assert crud.get_refresh_token(db_session, valid_token) is not None


class TestFaceDetectionEventsCRUD:
    """Test Face Detection Events CRUD operations"""

    def test_create_face_detection_event(self, db_session: Session):
        """Test creating face detection event"""
        event_data = {
            "camera_id": "face_cam_1",
            "person_name": "John Doe",
            "confidence": 0.95,
            "snapshot_path": "/snapshots/face_1.jpg"
        }
        created_event = crud.create_face_detection_event(db_session, event_data)

        assert created_event.id is not None
        assert created_event.camera_id == "face_cam_1"
        assert created_event.person_name == "John Doe"
        assert created_event.confidence == 0.95
        assert created_event.snapshot_path == "/snapshots/face_1.jpg"
        assert isinstance(created_event.detected_at, datetime)

    def test_get_face_detection_events_empty(self, db_session: Session):
        """Test getting events from empty database"""
        events = crud.get_face_detection_events(db_session)
        assert events == []

    def test_get_face_detection_events_with_data(self, db_session: Session):
        """Test getting multiple face detection events"""
        # Create multiple events
        for i in range(5):
            event_data = {
                "camera_id": f"cam_{i}",
                "person_name": f"Person {i}",
                "confidence": 0.8 + (i * 0.02),
                "snapshot_path": f"/snapshots/face_{i}.jpg"
            }
            crud.create_face_detection_event(db_session, event_data)

        events = crud.get_face_detection_events(db_session)

        assert len(events) == 5
        assert all(hasattr(e, 'person_name') for e in events)

    def test_get_recent_face_detections(self, db_session: Session):
        """Test getting recent face detections with limit"""
        # Create 10 events
        for i in range(10):
            event_data = {
                "camera_id": "recent_cam",
                "person_name": f"Person {i}",
                "confidence": 0.9,
                "snapshot_path": f"/snapshots/recent_{i}.jpg"
            }
            crud.create_face_detection_event(db_session, event_data)

        # Get recent 5 detections
        recent_events = crud.get_recent_face_detections(db_session, limit=5)

        assert len(recent_events) == 5
        assert all(e.camera_id == "recent_cam" for e in recent_events)


class TestRecordingEventsCRUD:
    """Test Recording Events CRUD operations"""

    def test_create_recording_event(self, db_session: Session):
        """Test creating recording event"""
        event_data = {
            "camera_id": "rec_cam_1",
            "recording_path": "/recordings/rec_1.mp4",
            "started_at": datetime.utcnow(),
            "motion_detected": True
        }
        created_event = crud.create_recording_event(db_session, event_data)

        assert created_event.id is not None
        assert created_event.camera_id == "rec_cam_1"
        assert created_event.recording_path == "/recordings/rec_1.mp4"
        assert created_event.motion_detected is True
        assert created_event.started_at is not None

    def test_update_recording_event_success(self, db_session: Session):
        """Test updating recording event"""
        # Create recording event
        event_data = {
            "camera_id": "update_rec_cam",
            "recording_path": "/recordings/update_rec.mp4",
            "started_at": datetime.utcnow(),
            "motion_detected": True
        }
        created_event = crud.create_recording_event(db_session, event_data)

        # Update event
        end_time = datetime.utcnow()
        update_data = {
            "end_time": end_time,
            "file_size": 1024000
        }
        updated_event = crud.update_recording_event(db_session, created_event.id, update_data)

        assert updated_event is not None
        assert updated_event.id == created_event.id
        assert updated_event.end_time == end_time
        assert updated_event.file_size == 1024000

    def test_update_recording_event_not_found(self, db_session: Session):
        """Test updating non-existent recording event returns None"""
        update_data = {"file_size": 1024}
        result = crud.update_recording_event(db_session, 99999, update_data)
        assert result is None

    def test_get_recording_events_empty(self, db_session: Session):
        """Test getting recordings from empty database"""
        recordings = crud.get_recording_events(db_session)
        assert recordings == []

    def test_get_recording_events_with_data(self, db_session: Session):
        """Test getting multiple recording events"""
        # Create multiple recordings
        for i in range(5):
            event_data = {
                "camera_id": f"cam_{i}",
                "recording_path": f"/recordings/rec_{i}.mp4",
                "started_at": datetime.utcnow(),
                "motion_detected": True
            }
            crud.create_recording_event(db_session, event_data)

        recordings = crud.get_recording_events(db_session)

        assert len(recordings) == 5
        assert all(r.recording_path.startswith("/recordings/rec_") for r in recordings)


class TestSystemLogsCRUD:
    """Test System Logs CRUD operations"""

    def test_create_system_log(self, db_session: Session):
        """Test creating system log"""
        log_data = {
            "log_level": "INFO",
            "message": "Test log message",
            "component": "test_module",
            "details": "Additional details"
        }
        created_log = crud.create_system_log(db_session, log_data)

        assert created_log.id is not None
        assert created_log.log_level == "INFO"
        assert created_log.message == "Test log message"
        assert created_log.component == "test_module"
        assert created_log.details == "Additional details"
        assert isinstance(created_log.created_at, datetime)

    def test_get_system_logs_empty(self, db_session: Session):
        """Test getting logs from empty database"""
        logs = crud.get_system_logs(db_session)
        assert logs == []

    def test_get_system_logs_with_data(self, db_session: Session):
        """Test getting multiple system logs"""
        # Create multiple logs
        for i in range(5):
            log_data = {
                "log_level": "INFO",
                "message": f"Test message {i}",
                "component": "test_source",
                "details": f"Details {i}"
            }
            crud.create_system_log(db_session, log_data)

        logs = crud.get_system_logs(db_session)

        assert len(logs) == 5
        assert all(log.component == "test_source" for log in logs)

    def test_get_system_logs_pagination(self, db_session: Session):
        """Test system logs pagination"""
        # Create 10 logs
        for i in range(10):
            log_data = {
                "log_level": "INFO",
                "message": f"Paginated message {i}",
                "component": "pagination_test"
            }
            crud.create_system_log(db_session, log_data)

        # Get first page
        page1 = crud.get_system_logs(db_session, skip=0, limit=5)
        assert len(page1) == 5

        # Get second page
        page2 = crud.get_system_logs(db_session, skip=5, limit=5)
        assert len(page2) == 5

        # Ensure pages don't overlap
        page1_ids = {log.id for log in page1}
        page2_ids = {log.id for log in page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestPTZPresetsCRUD:
    """Test PTZ Presets CRUD operations"""

    def test_get_ptz_presets_by_camera_empty(self, db_session: Session):
        """Test getting PTZ presets for camera with none"""
        presets = crud.get_ptz_presets_by_camera(db_session, "empty_camera")
        assert presets == []

    def test_create_ptz_preset(self, db_session: Session):
        """Test creating PTZ preset"""
        preset_data = {
            "preset_number": 1,
            "name": "Home Position",
            "pan": 0.0,
            "tilt": 0.0,
            "zoom": 1.0
        }
        created_preset = crud.create_ptz_preset(db_session, "ptz_cam_1", preset_data)

        assert created_preset.id is not None
        assert created_preset.camera_id == "ptz_cam_1"
        assert created_preset.preset_number == 1
        assert created_preset.name == "Home Position"
        assert created_preset.pan == 0.0
        assert created_preset.tilt == 0.0
        assert created_preset.zoom == 1.0

    def test_get_ptz_preset_by_id(self, db_session: Session):
        """Test retrieving PTZ preset by ID"""
        preset_data = {
            "preset_number": 1,
            "name": "Test Preset",
            "pan": 45.0,
            "tilt": 30.0,
            "zoom": 2.0
        }
        created_preset = crud.create_ptz_preset(db_session, "ptz_cam", preset_data)

        retrieved_preset = crud.get_ptz_preset_by_id(db_session, created_preset.id)

        assert retrieved_preset is not None
        assert retrieved_preset.id == created_preset.id
        assert retrieved_preset.name == "Test Preset"

    def test_get_ptz_preset_by_id_not_found(self, db_session: Session):
        """Test retrieving non-existent preset by ID returns None"""
        preset = crud.get_ptz_preset_by_id(db_session, 99999)
        assert preset is None

    def test_delete_ptz_preset_success(self, db_session: Session):
        """Test deleting PTZ preset"""
        preset_data = {
            "preset_number": 1,
            "name": "Delete Me",
            "pan": 0.0,
            "tilt": 0.0,
            "zoom": 1.0
        }
        created_preset = crud.create_ptz_preset(db_session, "delete_cam", preset_data)

        result = crud.delete_ptz_preset(db_session, created_preset.id)
        assert result is True

        # Verify deletion
        deleted_preset = crud.get_ptz_preset_by_id(db_session, created_preset.id)
        assert deleted_preset is None

    def test_delete_ptz_preset_not_found(self, db_session: Session):
        """Test deleting non-existent preset returns False"""
        result = crud.delete_ptz_preset(db_session, 99999)
        assert result is False
