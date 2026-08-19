# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for splitting a gallery into what may be regenerated and what may not.

    detected/   exported from camera snapshots, automatically — derived
    uploaded/   chosen and uploaded by a person, deliberately — authored

The split exists so that rebuilding a person's gallery from their detections —
the only reliable way to move training data when detections are reassigned,
since gallery filenames cannot be traced back to their detections — cannot
destroy the photographs somebody chose. Those are usually far better than a
144x144 camera crop, which makes them exactly the wrong ones to lose.

The rule the tests defend: when in doubt, treat a file as uploaded. Misfiling a
camera export means it survives a rebuild; misfiling somebody's photograph means
it is deleted.
"""

import pytest

from backend.core import gallery


@pytest.fixture
def faces(tmp_path, monkeypatch):
    class FakePaths:
        faces_dir = tmp_path

    monkeypatch.setattr("backend.core.paths.paths", FakePaths)
    return tmp_path


def write(path, name):
    path.mkdir(parents=True, exist_ok=True)
    (path / name).write_bytes(b"\xff\xd8\xff")   # a plausible jpeg header
    return path / name


class TestClassification:
    @pytest.mark.parametrize("name", [
        "20260815_212624_usb_camera_0_0.jpg",
        "20260817_194228_usb_camera_0_12.jpg",
        "20260101_000000_front_door_3.PNG",
    ])
    def test_camera_exports_are_recognised(self, name):
        assert gallery.EXPORTED_NAME.match(name)

    @pytest.mark.parametrize("name", [
        "grandma.jpg", "IMG_4821.jpeg", "mikel-passport.png",
        "20260815_212624.jpg",          # no camera or index
        "holiday_2026_1.jpg",           # no timestamp
    ])
    def test_anything_else_is_not(self, name):
        assert not gallery.EXPORTED_NAME.match(name)


class TestMigration:
    def test_camera_exports_move_to_detected(self, faces):
        write(faces / "Mikel", "20260815_212624_usb_camera_0_0.jpg")

        gallery.migrate_person("Mikel", dry_run=False)

        assert (faces / "Mikel" / "detected" / "20260815_212624_usb_camera_0_0.jpg").exists()

    def test_an_unrecognised_name_goes_to_uploaded(self, faces):
        """
        The safe direction. A file we cannot classify must survive a rebuild,
        because the alternative is deleting a photograph somebody chose.
        """
        write(faces / "Mikel", "grandma.jpg")

        gallery.migrate_person("Mikel", dry_run=False)

        assert (faces / "Mikel" / "uploaded" / "grandma.jpg").exists()

    def test_a_preview_moves_nothing(self, faces):
        original = write(faces / "Mikel", "20260815_212624_usb_camera_0_0.jpg")

        result = gallery.migrate_person("Mikel", dry_run=True)

        assert original.exists()
        assert result["to_detected"] == 1

    def test_migrating_twice_is_harmless(self, faces):
        write(faces / "Mikel", "20260815_212624_usb_camera_0_0.jpg")

        gallery.migrate_person("Mikel", dry_run=False)
        second = gallery.migrate_person("Mikel", dry_run=False)

        assert second["to_detected"] == 0
        assert second["already"] == 1

    def test_an_empty_gallery_is_not_an_error(self, faces):
        (faces / "test").mkdir()

        result = gallery.migrate_person("test", dry_run=False)

        assert result["to_detected"] == 0 and result["to_uploaded"] == 0


class TestReadingSpansBoth:
    def test_training_sees_detected_and_uploaded(self, faces):
        """
        The split governs what may be DELETED, not what counts. A person's face
        is their face however the picture arrived.
        """
        write(faces / "Mikel" / "detected", "20260815_212624_usb_camera_0_0.jpg")
        write(faces / "Mikel" / "uploaded", "grandma.jpg")

        assert gallery.count_images("Mikel") == 2

    def test_a_flat_legacy_gallery_is_still_read(self, faces):
        """An installation that has not been migrated must keep working."""
        write(faces / "Mikel", "anything.jpg")

        assert gallery.count_images("Mikel") == 1

    def test_a_mixed_layout_is_read_whole(self, faces):
        write(faces / "Mikel", "loose.jpg")
        write(faces / "Mikel" / "detected", "20260815_212624_usb_camera_0_0.jpg")
        write(faces / "Mikel" / "uploaded", "chosen.jpg")

        assert gallery.count_images("Mikel") == 3

    def test_non_images_are_ignored(self, faces):
        write(faces / "Mikel" / "detected", "20260815_212624_usb_camera_0_0.jpg")
        (faces / "Mikel" / "notes.txt").write_text("hello")

        assert gallery.count_images("Mikel") == 1

    def test_a_missing_person_reads_as_empty(self, faces):
        assert gallery.count_images("Nobody") == 0
        assert list(gallery.iter_images("Nobody")) == []


class TestLayout:
    def test_ensure_layout_creates_both(self, faces):
        gallery.ensure_layout("Mikel")

        assert (faces / "Mikel" / "detected").is_dir()
        assert (faces / "Mikel" / "uploaded").is_dir()

    def test_ensure_layout_is_idempotent(self, faces):
        gallery.ensure_layout("Mikel")
        write(faces / "Mikel" / "uploaded", "keep.jpg")
        gallery.ensure_layout("Mikel")

        assert (faces / "Mikel" / "uploaded" / "keep.jpg").exists()
