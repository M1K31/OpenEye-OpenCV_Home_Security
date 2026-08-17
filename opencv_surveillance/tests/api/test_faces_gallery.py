# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for the gallery summary endpoint.

The endpoint exists so that a bounded gallery is visibly a decision. Once
near-duplicate encodings are refused and a cap evicts the least distinctive,
"photos stopped increasing" is correct behaviour — and without somewhere to see
the numbers it is indistinguishable from training having quietly broken, which
is the same defect as the blank detection cards.
"""

from unittest.mock import patch

import pytest


@pytest.fixture
def gallery(monkeypatch):
    """A face manager holding two people with different gallery sizes."""
    from backend.core import face_recognition as fr

    class FakeManager:
        known_face_names = ["Mikel"] * 250 + ["Yala"] * 12

    monkeypatch.setattr("backend.api.routes.faces.get_face_manager",
                        lambda: FakeManager())
    return fr


class TestGallerySummary:
    def test_reports_encodings_per_person(self, client, auth_headers, gallery):
        response = client.get("/api/faces/gallery", headers=auth_headers)

        assert response.status_code == 200
        people = {p["name"]: p for p in response.json()["people"]}
        assert people["Mikel"]["encodings"] == 250
        assert people["Yala"]["encodings"] == 12

    def test_flags_a_person_at_the_cap(self, client, auth_headers, gallery):
        """
        The one number that explains why a gallery stopped growing. Without it a
        user sees a count that never moves and no reason for it.
        """
        response = client.get("/api/faces/gallery", headers=auth_headers)
        people = {p["name"]: p for p in response.json()["people"]}

        assert people["Mikel"]["at_cap"] is True
        assert people["Yala"]["at_cap"] is False

    def test_reports_the_cap_itself(self, client, auth_headers, gallery):
        response = client.get("/api/faces/gallery", headers=auth_headers)
        body = response.json()

        assert body["max_per_person"] == gallery.MAX_ENCODINGS_PER_PERSON
        assert body["total_encodings"] == 262

    def test_orders_by_size_so_the_largest_is_first(self, client, auth_headers, gallery):
        response = client.get("/api/faces/gallery", headers=auth_headers)
        names = [p["name"] for p in response.json()["people"]]

        assert names[0] == "Mikel"

    def test_requires_authentication(self, client, gallery):
        assert client.get("/api/faces/gallery").status_code in (401, 403)

    def test_an_empty_gallery_is_not_an_error(self, client, auth_headers, monkeypatch):
        class Empty:
            known_face_names = []

        monkeypatch.setattr("backend.api.routes.faces.get_face_manager", lambda: Empty())
        response = client.get("/api/faces/gallery", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["people"] == []
        assert response.json()["total_encodings"] == 0
