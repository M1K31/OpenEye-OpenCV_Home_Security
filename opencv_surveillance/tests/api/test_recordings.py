# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
API Tests for Recordings Endpoints

Tests the /api/recordings/ endpoints including:
- List recordings with pagination
- Get single recording details
- Download recording
- Delete recording
- Filtering and sorting
"""

import pytest
from datetime import datetime
from backend.database import models


class TestRecordingsAPI:
    """Test suite for recordings API endpoints"""

    def test_list_recordings_empty(self, client, auth_headers):
        """Test listing recordings when none exist"""
        response = client.get("/api/recordings/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "recordings" in data
        assert "total" in data
        assert data["total"] == 0
        assert len(data["recordings"]) == 0

    def test_list_recordings_with_data(self, client, auth_headers, db_session, test_camera):
        """Test listing recordings with existing data"""
        # Create test recordings
        recording1 = models.RecordingEvent(
            camera_id=test_camera.camera_id,
            started_at=datetime.utcnow(),
            file_path="test_recording_1.mp4",
            file_size_bytes=1024000,
            duration_seconds=60.0,
            trigger_type="motion"
        )
        recording2 = models.RecordingEvent(
            camera_id=test_camera.camera_id,
            started_at=datetime.utcnow(),
            file_path="test_recording_2.mp4",
            file_size_bytes=2048000,
            duration_seconds=120.0,
            trigger_type="face"
        )
        db_session.add_all([recording1, recording2])
        db_session.commit()

        response = client.get("/api/recordings/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["recordings"]) == 2

    def test_list_recordings_pagination(self, client, auth_headers, db_session, test_camera):
        """Test pagination of recordings"""
        # Create multiple recordings
        for i in range(15):
            recording = models.RecordingEvent(
                camera_id=test_camera.camera_id,
                started_at=datetime.utcnow(),
                file_path=f"test_recording_{i}.mp4",
                file_size_bytes=1024000,
                duration_seconds=60.0,
                trigger_type="motion"
            )
            db_session.add(recording)
        db_session.commit()

        # Test page 1
        response = client.get("/api/recordings/?limit=10&skip=0", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert len(data["recordings"]) == 10

        # Test page 2
        response = client.get("/api/recordings/?limit=10&skip=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["recordings"]) == 5

    def test_list_recordings_filter_by_camera(self, client, auth_headers, db_session, test_camera):
        """Test filtering recordings by camera ID"""
        # Create another camera
        camera2 = models.Camera(
            camera_id="test_camera_2",
            camera_name="Test Camera 2",
            source_url="mock",
            enabled=True
        )
        db_session.add(camera2)
        db_session.commit()

        # Create recordings for both cameras
        recording1 = models.RecordingEvent(
            camera_id=test_camera.camera_id,
            started_at=datetime.utcnow(),
            file_path="camera1_recording.mp4",
            file_size_bytes=1024000,
            duration_seconds=60.0
        )
        recording2 = models.RecordingEvent(
            camera_id=camera2.camera_id,
            started_at=datetime.utcnow(),
            file_path="camera2_recording.mp4",
            file_size_bytes=1024000,
            duration_seconds=60.0
        )
        db_session.add_all([recording1, recording2])
        db_session.commit()

        # Filter by camera 1
        response = client.get(
            f"/api/recordings/?camera_id={test_camera.camera_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["recordings"][0]["camera_id"] == test_camera.camera_id

    def test_list_recordings_unauthorized(self, client):
        """Test that unauthenticated requests are rejected"""
        response = client.get("/api/recordings/")
        assert response.status_code == 401

    def test_get_recording_details(self, client, auth_headers, db_session, test_camera):
        """Test getting details of a specific recording"""
        recording = models.RecordingEvent(
            camera_id=test_camera.camera_id,
            started_at=datetime.utcnow(),
            file_path="test_recording.mp4",
            file_size_bytes=1024000,
            duration_seconds=60.0,
            trigger_type="motion"
        )
        db_session.add(recording)
        db_session.commit()
        db_session.refresh(recording)

        response = client.get(f"/api/recordings/{recording.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == recording.id
        assert data["camera_id"] == test_camera.camera_id
        assert data["file_path"] == "test_recording.mp4"

    def test_get_recording_not_found(self, client, auth_headers):
        """Test getting a non-existent recording"""
        response = client.get("/api/recordings/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_recording(self, client, auth_headers, db_session, test_camera):
        """Test deleting a recording"""
        recording = models.RecordingEvent(
            camera_id=test_camera.camera_id,
            started_at=datetime.utcnow(),
            file_path="test_recording.mp4",
            file_size_bytes=1024000,
            duration_seconds=60.0
        )
        db_session.add(recording)
        db_session.commit()
        db_session.refresh(recording)

        response = client.delete(f"/api/recordings/{recording.id}", headers=auth_headers)
        assert response.status_code == 200

        # Verify recording is deleted
        response = client.get(f"/api/recordings/{recording.id}", headers=auth_headers)
        assert response.status_code == 404
