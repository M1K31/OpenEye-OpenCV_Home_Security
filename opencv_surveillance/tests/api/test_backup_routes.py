# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The backup and restore endpoints.

Restore is the most destructive action the application offers: it replaces the
database and the face galleries with the contents of a file somebody uploads.
Most of what follows is about who may do that and what is refused.
"""

import io
import json
import tarfile

import pytest


def _archive(members: dict) -> bytes:
    """A tar.gz built in memory from {name: bytes}."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


class TestWhoMayDoThis:
    """
    Admin only, every route.

    Listing reveals what a system holds and when it last worked. Creating reads
    the whole database. Restoring replaces it. None of that belongs to an
    ordinary user, and an unauthenticated caller must not learn whether backups
    exist at all.
    """

    @pytest.mark.parametrize("method,path", [
        ("get", "/api/backups"),
        ("post", "/api/backups"),
        ("post", "/api/backups/restore"),
        ("post", "/api/backups/anything/restore"),
    ])
    def test_an_anonymous_caller_is_refused(self, client, method, path):
        response = getattr(client, method)(path)
        assert response.status_code in (401, 403), (
            f"{path} answered {response.status_code} without credentials"
        )

    @pytest.mark.parametrize("path", ["/api/backups"])
    def test_an_ordinary_user_is_refused(self, client, auth_headers, path):
        # auth_headers is a viewer.
        response = client.get(path, headers=auth_headers)
        assert response.status_code == 403


class TestListing:
    def test_an_admin_sees_the_listing(self, client, admin_auth_headers):
        response = client.get("/api/backups", headers=admin_auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert "backups" in body and "directory" in body


class TestRefusingAnUpload:
    def test_a_file_that_is_not_a_backup(self, client, admin_auth_headers):
        payload = _archive({"holiday.jpg": b"not a database"})

        response = client.post(
            "/api/backups/inspect",
            files={"file": ("holiday.tar.gz", payload, "application/gzip")},
            headers=admin_auth_headers,
        )

        assert response.status_code == 400
        assert "not an OpenEye backup" in response.json()["detail"]

    def test_a_backup_from_an_unreadable_format(self, client, admin_auth_headers):
        payload = _archive({
            "openeye-backup.json": json.dumps({"format": 99}).encode(),
            "surveillance.db": b"",
        })

        response = client.post(
            "/api/backups/inspect",
            files={"file": ("future.tar.gz", payload, "application/gzip")},
            headers=admin_auth_headers,
        )

        assert response.status_code == 400
        assert "format" in response.json()["detail"]

    def test_restoring_a_bad_upload_reports_rather_than_breaks(
            self, client, admin_auth_headers):
        """
        A refusal must arrive as a clear 400, not a 500 — and nothing may be
        replaced on the way to deciding that.
        """
        payload = _archive({"holiday.jpg": b"not a database"})

        response = client.post(
            "/api/backups/restore",
            files={"file": ("holiday.tar.gz", payload, "application/gzip")},
            headers=admin_auth_headers,
        )

        assert response.status_code == 400


class TestRestoringSomethingStored:
    def test_an_unknown_name_is_a_404(self, client, admin_auth_headers):
        response = client.post(
            "/api/backups/no-such-backup.tar.gz/restore",
            headers=admin_auth_headers)
        assert response.status_code == 404

    def test_a_crafted_name_cannot_escape_the_backup_directory(
            self, client, admin_auth_headers):
        """
        Two things stop this, and either alone would be enough.

        A path parameter does not match a slash, so a name containing one fails
        to route and never reaches the handler — which is the 405 below. And if
        it did reach it, the name is matched against the listing rather than
        joined onto a path, so it would find nothing.

        What matters is that no status in the 2xx range is possible.
        """
        response = client.post(
            "/api/backups/..%2F..%2F..%2Fetc%2Fpasswd/restore",
            headers=admin_auth_headers)
        assert response.status_code in (400, 404, 405), response.status_code
        assert not response.is_success

    def test_a_plain_name_that_is_not_listed_is_refused(self, client, admin_auth_headers):
        # The handler's own check, reached this time because the name routes.
        response = client.post(
            "/api/backups/etc-passwd/restore", headers=admin_auth_headers)
        assert response.status_code == 404
