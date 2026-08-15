# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Serving recordings whose stored path predates the current storage layout.

A recording_path comes out of the database, not out of the request, so a value
pointing outside the media directory means stale history — a file written before
storage moved, or by a build that resolved paths differently — rather than an
attack. Treating it as an intrusion produced a 403 that both misdescribed the
situation and told the interface "refused" when the truth was "gone".
"""

import types

import pytest
from fastapi import HTTPException

from backend.api.routes import recordings


@pytest.fixture
def media_dir(tmp_path, monkeypatch):
    """A recordings directory that PathManager points at."""
    # exist_ok: a session fixture already provisions this name under tmp_path.
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir(exist_ok=True)

    fake_paths = types.SimpleNamespace(
        recordings_dir=recordings_dir,
        resolve_path=lambda value: (
            recordings_dir.parent / value if not str(value).startswith("/")
            else __import__("pathlib").Path(value)
        ),
    )
    monkeypatch.setattr(recordings, "paths", fake_paths)
    return recordings_dir


class TestStalePaths:
    def test_a_recording_moved_since_it_was_recorded_is_still_served(self, media_dir):
        """
        The file exists where recordings live now; only the stored path is old.
        Refusing that is a bug, not security.
        """
        clip = media_dir / "usb_camera_0_motion_20260815.mp4"
        clip.write_bytes(b"video")

        response = recordings.safe_file_response(
            file_path="/somewhere/that/no/longer/exists/usb_camera_0_motion_20260815.mp4",
            allowed_dir=media_dir,
            media_type="video/mp4",
        )

        assert str(response.path) == str(clip)

    def test_a_recording_whose_file_is_gone_reports_gone_not_forbidden(self, media_dir):
        """
        403 told the user access was refused. The file had been deleted with the
        application bundle it was mistakenly written into.
        """
        with pytest.raises(HTTPException) as raised:
            recordings.safe_file_response(
                file_path="/old/bundle/path/vanished.mp4",
                allowed_dir=media_dir,
                media_type="video/mp4",
            )

        assert raised.value.status_code == 404
        assert "no longer available" in raised.value.detail

    def test_a_normal_recording_is_unaffected(self, media_dir):
        clip = media_dir / "current.mp4"
        clip.write_bytes(b"video")

        response = recordings.safe_file_response(
            file_path="recordings/current.mp4",
            allowed_dir=media_dir,
            media_type="video/mp4",
        )

        assert str(response.path) == str(clip)

    def test_it_never_serves_a_file_from_outside_the_media_directory(self, media_dir, tmp_path):
        """
        Recovery is by *name inside the allowed directory* only. A stored path
        elsewhere must never cause that other file to be served, however it got
        into the database.
        """
        outside = tmp_path / "secrets.mp4"
        outside.write_bytes(b"not yours")

        with pytest.raises(HTTPException) as raised:
            recordings.safe_file_response(
                file_path=str(outside),
                allowed_dir=media_dir,
                media_type="video/mp4",
            )

        assert raised.value.status_code == 404
