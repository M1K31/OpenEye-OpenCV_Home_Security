# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Locust Load Testing Configuration for OpenEye

This file defines load testing scenarios for the OpenEye surveillance system.

Usage:
    # Install Locust
    pip install locust

    # Run load test with web UI
    locust -f tests/performance/locustfile.py --host=http://localhost:8000

    # Run headless with specific settings
    locust -f tests/performance/locustfile.py --host=http://localhost:8000 \
           --users 100 --spawn-rate 10 --run-time 5m --headless

    # Run with HTML report
    locust -f tests/performance/locustfile.py --host=http://localhost:8000 \
           --users 50 --spawn-rate 5 --run-time 2m --headless --html report.html
"""

from locust import HttpUser, task, between, tag
import random
from datetime import datetime, timedelta


class OpenEyeUser(HttpUser):
    """
    Simulates a user interacting with the OpenEye surveillance system

    This class defines realistic user behavior patterns with weighted tasks
    representing typical usage of the system.
    """

    # Wait between 1-3 seconds between tasks (simulates user think time)
    wait_time = between(1, 3)

    # Authentication token (will be set on_start)
    token = None

    def on_start(self):
        """
        Called when a simulated user starts

        Authenticates the user and stores the token for subsequent requests
        """
        # Login to get authentication token
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
            name="/api/auth/login [LOGIN]"
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
        else:
            # If login fails, stop this user
            self.token = None

    def get_headers(self):
        """Get authentication headers"""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(5)
    @tag("recordings", "list")
    def list_recordings(self):
        """
        List recordings with pagination (weight: 5)

        Most common operation - users frequently browse recordings
        """
        page = random.randint(1, 5)
        page_size = random.choice([20, 50, 100])

        self.client.get(
            f"/api/recordings/?page={page}&page_size={page_size}",
            headers=self.get_headers(),
            name="/api/recordings/ [LIST]"
        )

    @task(3)
    @tag("recordings", "filter")
    def list_recordings_filtered(self):
        """
        List recordings with filters (weight: 3)

        Users often filter by camera or date range
        """
        camera_ids = ["front_door", "backyard", "garage", None]
        camera_id = random.choice(camera_ids)

        params = {"page": 1, "page_size": 50}
        if camera_id:
            params["camera_id"] = camera_id

        # Sometimes add date filter
        if random.random() > 0.5:
            start_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
            params["start_date"] = start_date

        self.client.get(
            "/api/recordings/",
            params=params,
            headers=self.get_headers(),
            name="/api/recordings/ [FILTERED]"
        )

    @task(2)
    @tag("cameras", "list")
    def list_cameras(self):
        """
        Get list of cameras (weight: 2)

        Moderate frequency - checking camera status
        """
        self.client.get(
            "/api/cameras/",
            headers=self.get_headers(),
            name="/api/cameras/ [LIST]"
        )

    @task(1)
    @tag("cameras", "detail")
    def get_camera_details(self):
        """
        Get specific camera details (weight: 1)

        Less frequent - viewing individual camera
        """
        camera_ids = ["front_door", "backyard", "garage"]
        camera_id = random.choice(camera_ids)

        self.client.get(
            f"/api/cameras/{camera_id}",
            headers=self.get_headers(),
            name="/api/cameras/{id} [GET]"
        )

    @task(4)
    @tag("faces", "history")
    def get_face_history(self):
        """
        Get face detection history (weight: 4)

        Common operation - browsing face detections
        """
        page = random.randint(1, 3)
        page_size = random.choice([20, 50])
        hours = random.choice([24, 48, 168])  # 1 day, 2 days, 1 week

        self.client.get(
            f"/api/faces/history/detections?page={page}&page_size={page_size}&hours={hours}",
            headers=self.get_headers(),
            name="/api/faces/history/detections [LIST]"
        )

    @task(2)
    @tag("motion", "list")
    def list_motion_events(self):
        """
        List motion detection events (weight: 2)

        Moderate frequency - checking motion alerts
        """
        page = random.randint(1, 3)
        page_size = random.choice([50, 100])

        self.client.get(
            f"/api/motion-events/?page={page}&page_size={page_size}",
            headers=self.get_headers(),
            name="/api/motion-events/ [LIST]"
        )

    @task(1)
    @tag("clusters", "list")
    def list_clusters(self):
        """
        List face clusters (weight: 1)

        Less frequent - reviewing unknown faces
        """
        page = random.randint(1, 2)

        self.client.get(
            f"/api/clusters/?page={page}&page_size=20",
            headers=self.get_headers(),
            name="/api/clusters/ [LIST]"
        )

    @task(2)
    @tag("analytics", "summary")
    def get_analytics_summary(self):
        """
        Get analytics summary (weight: 2)

        Cached endpoint - tests cache performance
        """
        self.client.get(
            "/api/analytics/summary",
            headers=self.get_headers(),
            name="/api/analytics/summary [CACHED]"
        )

    @task(1)
    @tag("analytics", "hourly")
    def get_hourly_activity(self):
        """
        Get hourly activity breakdown (weight: 1)

        Cached endpoint - tests cache performance
        """
        days = random.choice([7, 14, 30])

        self.client.get(
            f"/api/analytics/activity/hourly?days={days}",
            headers=self.get_headers(),
            name="/api/analytics/activity/hourly [CACHED]"
        )

    @task(1)
    @tag("metrics", "performance")
    def get_performance_metrics(self):
        """
        Get performance metrics (weight: 1)

        Monitor system performance during load test
        """
        self.client.get(
            "/api/metrics/performance/summary",
            headers=self.get_headers(),
            name="/api/metrics/performance/summary"
        )


class HeavyUser(HttpUser):
    """
    Simulates a heavy user performing expensive operations

    Use this to test system behavior under stress
    """

    wait_time = between(2, 5)
    token = None

    def on_start(self):
        """Authenticate user"""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"}
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")

    def get_headers(self):
        """Get authentication headers"""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(3)
    @tag("recordings", "stats")
    def get_recording_stats(self):
        """Get storage statistics (expensive operation)"""
        self.client.get(
            "/api/recordings/storage/stats",
            headers=self.get_headers(),
            name="/api/recordings/storage/stats [EXPENSIVE]"
        )

    @task(2)
    @tag("motion", "stats")
    def get_motion_statistics(self):
        """Get motion statistics (expensive operation)"""
        days = random.choice([7, 30])

        self.client.get(
            f"/api/motion-events/statistics/summary?days={days}",
            headers=self.get_headers(),
            name="/api/motion-events/statistics/summary [EXPENSIVE]"
        )

    @task(1)
    @tag("faces", "stats")
    def get_face_statistics(self):
        """Get face detection statistics (expensive operation)"""
        days = random.choice([7, 30])

        self.client.get(
            f"/api/faces/history/statistics?days={days}",
            headers=self.get_headers(),
            name="/api/faces/history/statistics [EXPENSIVE]"
        )


class ReadOnlyUser(HttpUser):
    """
    Simulates a read-only user (e.g., mobile app user checking status)

    Fast, lightweight operations only
    """

    wait_time = between(0.5, 2)
    token = None

    def on_start(self):
        """Authenticate user"""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"}
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")

    def get_headers(self):
        """Get authentication headers"""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(10)
    @tag("cameras", "status")
    def check_camera_status(self):
        """Quick camera status check"""
        self.client.get(
            "/api/cameras/",
            headers=self.get_headers(),
            name="/api/cameras/ [QUICK]"
        )

    @task(5)
    @tag("analytics", "summary")
    def quick_summary(self):
        """Quick analytics summary (cached)"""
        self.client.get(
            "/api/analytics/summary",
            headers=self.get_headers(),
            name="/api/analytics/summary [QUICK]"
        )

    @task(3)
    @tag("metrics", "health")
    def health_check(self):
        """System health check"""
        self.client.get(
            "/api/health",
            name="/api/health [QUICK]"
        )
