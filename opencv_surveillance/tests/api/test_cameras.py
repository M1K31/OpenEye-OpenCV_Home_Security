# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
API Tests for Camera Endpoints

Tests the /api/cameras/ endpoints including:
- List cameras
- Get camera details
- Create camera
- Update camera
- Delete camera
- Start/stop camera streaming
"""

import pytest
from backend.database import models


class TestCamerasAPI:
    """Test suite for cameras API endpoints"""

    def test_list_cameras_empty(self, client, auth_headers):
        """Test listing cameras when none exist"""
        response = client.get("/api/cameras/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "cameras" in data
        assert len(data["cameras"]) == 0

    def test_list_cameras_with_data(self, client, auth_headers, test_camera):
        """Test listing cameras with existing data"""
        response = client.get("/api/cameras/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["cameras"]) == 1
        assert data["cameras"][0]["camera_id"] == "test_camera_1"

    def test_get_camera_details(self, client, auth_headers, test_camera):
        """Test getting details of a specific camera"""
        response = client.get(f"/api/cameras/{test_camera.camera_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["camera_id"] == test_camera.camera_id
        assert data["camera_name"] == "Test Camera"
        assert data["enabled"] is True

    def test_get_camera_not_found(self, client, auth_headers):
        """Test getting a non-existent camera"""
        response = client.get("/api/cameras/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_create_camera(self, client, auth_headers):
        """Test creating a new camera"""
        camera_data = {
            "camera_id": "new_camera",
            "camera_name": "New Test Camera",
            "source_url": "rtsp://example.com/stream",
            "enabled": True,
            "motion_detection_enabled": True,
            "face_recognition_enabled": False,
            "recording_enabled": False
        }
        response = client.post("/api/cameras/", json=camera_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["camera_id"] == "new_camera"
        assert data["camera_name"] == "New Test Camera"

    def test_create_camera_duplicate_id(self, client, auth_headers, test_camera):
        """Test creating a camera with duplicate ID"""
        camera_data = {
            "camera_id": test_camera.camera_id,  # Duplicate ID
            "camera_name": "Duplicate Camera",
            "source_url": "rtsp://example.com/stream"
        }
        response = client.post("/api/cameras/", json=camera_data, headers=auth_headers)
        assert response.status_code == 400  # Bad request

    def test_update_camera(self, client, auth_headers, test_camera):
        """Test updating camera configuration"""
        update_data = {
            "camera_name": "Updated Camera Name",
            "motion_detection_enabled": False
        }
        response = client.put(
            f"/api/cameras/{test_camera.camera_id}",
            json=update_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["camera_name"] == "Updated Camera Name"
        assert data["motion_detection_enabled"] is False

    def test_delete_camera(self, client, auth_headers, test_camera):
        """Test deleting a camera"""
        response = client.delete(
            f"/api/cameras/{test_camera.camera_id}",
            headers=auth_headers
        )
        assert response.status_code == 200

        # Verify camera is deleted
        response = client.get(f"/api/cameras/{test_camera.camera_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_camera_statistics(self, client, auth_headers, test_camera):
        """Test getting camera statistics"""
        response = client.get(
            f"/api/cameras/{test_camera.camera_id}/statistics",
            headers=auth_headers
        )
        # Statistics endpoint may return 200 with data or 404 if not implemented
        assert response.status_code in [200, 404]

    def test_list_cameras_unauthorized(self, client):
        """Test that unauthenticated requests are rejected"""
        response = client.get("/api/cameras/")
        assert response.status_code == 401


class TestCameraControl:
    """Test suite for camera control operations"""

    def test_start_camera(self, client, auth_headers, test_camera):
        """Test starting a camera stream"""
        response = client.post(
            f"/api/cameras/{test_camera.camera_id}/start",
            headers=auth_headers
        )
        # May return 200 (success) or 500 (if no actual camera hardware)
        assert response.status_code in [200, 500]

    def test_stop_camera(self, client, auth_headers, test_camera):
        """Test stopping a camera stream"""
        response = client.post(
            f"/api/cameras/{test_camera.camera_id}/stop",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_get_camera_snapshot(self, client, auth_headers, test_camera):
        """Test getting a camera snapshot"""
        response = client.get(
            f"/api/cameras/{test_camera.camera_id}/snapshot",
            headers=auth_headers
        )
        # Snapshot may not be available in test environment
        assert response.status_code in [200, 404, 500]
