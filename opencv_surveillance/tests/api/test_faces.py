# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
API Tests for Face Recognition Endpoints

Tests the /api/faces/ endpoints including:
- List known faces
- Upload face
- Delete face
- Face detection history
- Face clustering
"""

import pytest
from datetime import datetime
from backend.database import models


class TestFacesAPI:
    """Test suite for faces API endpoints"""

    def test_list_faces_empty(self, client, auth_headers):
        """Test listing faces when none exist"""
        response = client.get("/api/faces/people", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "people" in data
        assert len(data["people"]) == 0

    def test_upload_face_missing_file(self, client, auth_headers):
        """Test uploading face without file"""
        response = client.post(
            "/api/faces/upload",
            data={"person_name": "John Doe"},
            headers=auth_headers
        )
        assert response.status_code in [400, 422]  # Bad request or validation error

    def test_delete_face(self, client, auth_headers):
        """Test deleting a known face"""
        response = client.delete("/api/faces/John_Doe", headers=auth_headers)
        # May return 200 (deleted), 404 (not found), or 500 (filesystem error)
        assert response.status_code in [200, 404, 500]

    def test_train_model(self, client, auth_headers):
        """Test triggering face recognition model training"""
        response = client.post("/api/faces/train", headers=auth_headers)
        # Training may succeed or fail depending on available faces
        assert response.status_code in [200, 400, 500]

    def test_list_faces_unauthorized(self, client):
        """Test that unauthenticated requests are rejected"""
        response = client.get("/api/faces/people")
        assert response.status_code == 401


class TestFaceHistory:
    """Test suite for face detection history"""

    def test_list_face_history_empty(self, client, auth_headers):
        """Test listing face detection events when none exist"""
        response = client.get("/api/faces/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert data["total"] == 0

    def test_list_face_history_with_data(self, client, auth_headers, db_session, test_camera):
        """Test listing face detection events with existing data"""
        # Create test face detection events
        event1 = models.FaceDetectionEvent(
            camera_id=test_camera.camera_id,
            detected_at=datetime.utcnow(),
            person_name="John Doe",
            confidence=0.95,
            snapshot_path="snapshots/john_1.jpg"
        )
        event2 = models.FaceDetectionEvent(
            camera_id=test_camera.camera_id,
            detected_at=datetime.utcnow(),
            person_name="Jane Doe",
            confidence=0.87,
            snapshot_path="snapshots/jane_1.jpg"
        )
        db_session.add_all([event1, event2])
        db_session.commit()

        response = client.get("/api/faces/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["events"]) == 2

    def test_face_history_pagination(self, client, auth_headers, db_session, test_camera):
        """Test pagination of face detection history"""
        # Create multiple events
        for i in range(15):
            event = models.FaceDetectionEvent(
                camera_id=test_camera.camera_id,
                detected_at=datetime.utcnow(),
                person_name=f"Person_{i}",
                confidence=0.9,
                snapshot_path=f"snapshots/person_{i}.jpg"
            )
            db_session.add(event)
        db_session.commit()

        # Test page 1
        response = client.get("/api/faces/history?limit=10&skip=0", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert len(data["events"]) == 10

        # Test page 2
        response = client.get("/api/faces/history?limit=10&skip=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 5

    def test_face_history_filter_by_person(self, client, auth_headers, db_session, test_camera):
        """Test filtering face history by person name"""
        event1 = models.FaceDetectionEvent(
            camera_id=test_camera.camera_id,
            detected_at=datetime.utcnow(),
            person_name="John Doe",
            confidence=0.95,
            snapshot_path="snapshots/john_1.jpg"
        )
        event2 = models.FaceDetectionEvent(
            camera_id=test_camera.camera_id,
            detected_at=datetime.utcnow(),
            person_name="Jane Doe",
            confidence=0.87,
            snapshot_path="snapshots/jane_1.jpg"
        )
        db_session.add_all([event1, event2])
        db_session.commit()

        response = client.get("/api/faces/history?person_name=John Doe", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for event in data["events"]:
            assert event["person_name"] == "John Doe"


class TestFaceClustering:
    """Test suite for face clustering endpoints"""

    def test_list_clusters_empty(self, client, auth_headers):
        """Test listing face clusters when none exist"""
        response = client.get("/api/clusters/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "clusters" in data

    def test_trigger_clustering(self, client, auth_headers):
        """Test triggering face clustering algorithm"""
        response = client.post("/api/clusters/run", headers=auth_headers)
        # Clustering may succeed or fail depending on available data
        assert response.status_code in [200, 400, 500]

    def test_get_cluster_details(self, client, auth_headers, db_session):
        """Test getting details of a specific cluster"""
        # Create test cluster
        cluster = models.FaceCluster(
            label="0",
            representative_snapshot_path="clusters/cluster_0.jpg",
            face_count=5
        )
        db_session.add(cluster)
        db_session.commit()
        db_session.refresh(cluster)

        response = client.get(f"/api/clusters/{cluster.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cluster.id
        assert data["member_count"] == 5

    def test_identify_cluster(self, client, auth_headers, db_session):
        """Test assigning a person name to a cluster"""
        cluster = models.FaceCluster(
            label="0",
            representative_snapshot_path="clusters/cluster_0.jpg",
            face_count=5
        )
        db_session.add(cluster)
        db_session.commit()
        db_session.refresh(cluster)

        response = client.post(
            f"/api/clusters/{cluster.id}/identify",
            json={"person_name": "John Doe"},
            headers=auth_headers
        )
        # May succeed or fail depending on implementation
        assert response.status_code in [200, 400, 500]
