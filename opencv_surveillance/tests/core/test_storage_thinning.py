# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for the storage thinning planner.

Two things are being defended here, and only one of them is "does it free
space". The other is that it never frees the wrong thing: this deletes footage
the user cannot get back, and the cleanup that already shipped shows how quietly
a protection rule can be wrong — it preserves any filename containing "face",
which is every detection snapshot, while never looking at the profile galleries
it was presumably meant to save.

So most of what follows asserts about what is *kept*.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.core import storage_thinning as st
from backend.core.storage_thinning import (
    ACTION_DELETE,
    ACTION_TRANSCODE,
    ThinningSettings,
    apply_plan,
    build_plan,
)

NOW = datetime(2026, 8, 17, 12, 0, 0)


def write(path: Path, size: int, age_days: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)
    when = (NOW - timedelta(days=age_days)).timestamp()
    os.utime(path, (when, when))
    return path


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A miniature data root with recordings, snapshots and a profile gallery."""
    class FakePaths:
        data_dir = tmp_path
        recordings_dir = tmp_path / "recordings"
        snapshots_dir = tmp_path / "snapshots"
        thumbnails_dir = tmp_path / "thumbnails"
        faces_dir = tmp_path / "faces"

    monkeypatch.setattr("backend.core.paths.paths", FakePaths)

    write(FakePaths.recordings_dir / "old.mp4", 1000, age_days=60)
    write(FakePaths.recordings_dir / "recent.mp4", 1000, age_days=2)
    write(FakePaths.snapshots_dir / "face_cam_old.jpg", 100, age_days=60)
    write(FakePaths.snapshots_dir / "face_cam_recent.jpg", 100, age_days=2)
    write(FakePaths.faces_dir / "Mikel" / "1.jpg", 100, age_days=400)
    write(FakePaths.faces_dir / "Mikel" / "2.jpg", 100, age_days=400)
    return FakePaths


class TestNothingHappensByDefault:
    def test_default_settings_plan_nothing(self, library):
        plan = build_plan(ThinningSettings(), now=NOW, free_bytes=0)

        assert plan.items == []
        assert "disabled" in " ".join(plan.notes)

    def test_enabled_but_unconfigured_plans_nothing(self, library):
        """Enabling the feature is not the same as asking for deletions."""
        plan = build_plan(ThinningSettings(enabled=True), now=NOW, free_bytes=0)

        assert plan.items == []

    def test_zero_days_means_forever_not_immediately(self, library):
        """
        A zero read as "delete everything older than zero days" would destroy an
        entire library the moment someone ticked the box.
        """
        settings = ThinningSettings(enabled=True, video_retention_days=0,
                                    image_retention_days=0, free_space_floor_gb=0)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        assert plan.items == []


class TestProtection:
    def test_profile_galleries_are_never_touched(self, library):
        """They are 400 days old and every retention rule is aggressive."""
        settings = ThinningSettings(enabled=True, image_retention_days=1,
                                    video_retention_days=1)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        planned = {i.path.name for i in plan.items}
        assert "1.jpg" not in planned and "2.jpg" not in planned

    def test_a_gallery_image_is_not_even_scanned_as_a_candidate(self, library):
        settings = ThinningSettings(enabled=True, image_retention_days=1)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        for item in plan.items:
            assert "faces" not in item.path.parts

    def test_the_floor_cannot_reach_protected_material(self, library):
        """An impossible floor must not start eating the training data."""
        settings = ThinningSettings(enabled=True, free_space_floor_gb=100.0)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        for item in plan.items:
            assert "faces" not in item.path.parts
        assert not plan.meets_floor
        assert any("cannot be met" in n for n in plan.notes)

    def test_protection_is_not_by_filename(self, library):
        """
        The bug in the shipped cleanup: it preserves anything named *face*, so
        every detection snapshot is spared and nothing is ever freed. These
        snapshots are named face_* and must still be eligible.
        """
        settings = ThinningSettings(enabled=True, image_retention_days=30)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        planned = {i.path.name for i in plan.items}
        assert "face_cam_old.jpg" in planned

    def test_a_cluster_representative_stored_as_a_url_is_protected(self, library):
        """
        The representative is stored as the URL the frontend fetches —
        "/data/snapshots/face_cam_....jpg" — not as a filesystem path. That
        string is absolute, so treating it as a path resolves to a location that
        does not exist and the real file goes unprotected while the code looks
        correct. Exactly the quiet protection failure this planner exists to
        avoid, found only by running it against a real database.
        """
        target = library.snapshots_dir / "face_cam_old.jpg"

        class DB:
            def query(self, *a, **k):
                return self
            def all(self):
                return [("/data/snapshots/face_cam_old.jpg",)]

        settings = ThinningSettings(enabled=True, image_retention_days=1)
        plan = build_plan(settings, db=DB(), now=NOW, free_bytes=0)

        assert target.name not in {i.path.name for i in plan.items}

    def test_protected_material_is_counted_even_when_never_scanned(self, library):
        """
        Gallery files are protected by not being scanned at all, so counting
        only scanned-and-skipped files reports "protected: 0" on an install
        holding hundreds of gallery images — the opposite of the reassurance
        someone needs before switching deletion on.
        """
        settings = ThinningSettings(enabled=True, image_retention_days=1,
                                    video_retention_days=1)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        assert plan.protected_count == 2   # Mikel/1.jpg and Mikel/2.jpg
        assert plan.protected_bytes == 200

    def test_a_database_failure_refuses_to_plan(self, library):
        """
        A planner that cannot see its protections must not produce a plan that
        looks authoritative. Failing loudly is the only safe direction.
        """
        class ExplodingDB:
            def query(self, *a, **k):
                raise RuntimeError("database unavailable")

        with pytest.raises(RuntimeError):
            build_plan(ThinningSettings(enabled=True, image_retention_days=1),
                       db=ExplodingDB(), now=NOW, free_bytes=0)


class TestRetention:
    def test_only_material_past_its_age_is_deleted(self, library):
        settings = ThinningSettings(enabled=True, video_retention_days=30,
                                    image_retention_days=30)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        planned = {i.path.name for i in plan.items}
        assert planned == {"old.mp4", "face_cam_old.jpg"}

    def test_images_and_video_age_independently(self, library):
        """A snapshot is KBs and worth keeping far longer than its video."""
        settings = ThinningSettings(enabled=True, video_retention_days=30,
                                    image_retention_days=0)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        planned = {i.path.name for i in plan.items}
        assert planned == {"old.mp4"}


class TestTranscoding:
    def test_old_video_is_transcoded_not_deleted(self, library):
        settings = ThinningSettings(enabled=True, transcode_enabled=True,
                                    transcode_after_days=30)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        assert [i.path.name for i in plan.by_action(ACTION_TRANSCODE)] == ["old.mp4"]
        assert plan.by_action(ACTION_DELETE) == []

    def test_deletion_wins_over_transcoding_for_the_same_file(self, library):
        """Re-encoding something that is about to be deleted is wasted CPU."""
        settings = ThinningSettings(enabled=True, video_retention_days=30,
                                    transcode_enabled=True, transcode_after_days=10)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        assert [i.path.name for i in plan.by_action(ACTION_DELETE)] == ["old.mp4"]
        assert plan.by_action(ACTION_TRANSCODE) == []

    def test_images_are_never_transcoded(self, library):
        settings = ThinningSettings(enabled=True, transcode_enabled=True,
                                    transcode_after_days=1)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        for item in plan.by_action(ACTION_TRANSCODE):
            assert item.path.suffix == ".mp4"

    def test_a_transcode_claims_only_partial_savings(self, library):
        settings = ThinningSettings(enabled=True, transcode_enabled=True,
                                    transcode_after_days=30)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        item = plan.by_action(ACTION_TRANSCODE)[0]
        assert 0 < item.bytes_freed < item.size_bytes


class TestTheFloor:
    def test_the_floor_is_not_applied_when_space_is_ample(self, library):
        settings = ThinningSettings(enabled=True, free_space_floor_gb=1.0)
        plan = build_plan(settings, now=NOW, free_bytes=10 * 1024 ** 3)

        assert plan.items == []

    def test_the_floor_thins_recent_material_when_space_is_tight(self, library):
        """The point of a floor: a small drive is protected even inside the
        retention window."""
        settings = ThinningSettings(enabled=True, free_space_floor_gb=0.000001)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        assert plan.items, "nothing was reclaimed despite the floor being unmet"
        assert plan.meets_floor

    def test_the_floor_stops_as_soon_as_it_is_met(self, library):
        """It is an emergency measure, not an excuse to clear the drive."""
        floor = 1500  # bytes; one 1000-byte recording is not enough, two are
        settings = ThinningSettings(enabled=True,
                                    free_space_floor_gb=floor / 1024 ** 3)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        assert plan.meets_floor
        assert len(plan.items) < plan.scanned_count

    def test_the_floor_takes_the_oldest_first(self, library):
        settings = ThinningSettings(enabled=True,
                                    free_space_floor_gb=1000 / 1024 ** 3)
        plan = build_plan(settings, now=NOW, free_bytes=0)

        assert plan.items[0].path.name == "old.mp4"


class TestThePlanIsReadOnly:
    def test_building_a_plan_deletes_nothing(self, library):
        before = {p for p in Path(library.data_dir).rglob("*") if p.is_file()}

        settings = ThinningSettings(enabled=True, image_retention_days=1,
                                    video_retention_days=1,
                                    free_space_floor_gb=50.0)
        build_plan(settings, now=NOW, free_bytes=0)

        after = {p for p in Path(library.data_dir).rglob("*") if p.is_file()}
        assert before == after

    def test_describe_is_safe_to_print(self, library):
        settings = ThinningSettings(enabled=True, video_retention_days=30)
        text = build_plan(settings, now=NOW, free_bytes=0).describe()

        assert "nothing has been changed" in text


class TestApplyingAPlan:
    """
    Enforcement consumes a plan rather than re-deciding what to remove, so the
    preview a user reads and the action taken are the same computation. What is
    asserted here is mostly what survives.
    """

    def _plan(self, **kwargs):
        settings = ThinningSettings(enabled=True, **kwargs)
        return build_plan(settings, now=NOW, free_bytes=0)

    def test_it_deletes_what_the_plan_named(self, library):
        plan = self._plan(video_retention_days=30, image_retention_days=30)

        result = apply_plan(plan)

        assert result.deleted == 2
        assert not (library.recordings_dir / "old.mp4").exists()
        assert (library.recordings_dir / "recent.mp4").exists()

    def test_a_dry_run_removes_nothing(self, library):
        plan = self._plan(video_retention_days=1, image_retention_days=1)

        result = apply_plan(plan, dry_run=True)

        assert result.deleted > 0
        assert (library.recordings_dir / "old.mp4").exists()

    def test_a_disabled_plan_does_nothing(self, library):
        plan = build_plan(ThinningSettings(), now=NOW, free_bytes=0)

        result = apply_plan(plan)

        assert result.deleted == 0

    def test_protections_are_rechecked_at_apply_time(self, library):
        """
        A plan can be built, held, and applied later — after a cluster has gained
        a representative, or a person has been enrolled. Trusting the plan's
        view of what is protected would delete something that became protected
        in between, and that is not recoverable.
        """
        plan = self._plan(image_retention_days=1, video_retention_days=1)
        target = library.snapshots_dir / "face_cam_old.jpg"
        assert target.name in {i.path.name for i in plan.items}, "test premise"

        class DB:  # now claims the file as a cluster representative
            def query(self, *a, **k):
                return self
            def all(self):
                return [("/data/snapshots/face_cam_old.jpg",)]

        result = apply_plan(plan, db=DB())

        assert target.exists(), "a newly protected file was deleted anyway"
        assert any("protected" in e for e in result.errors)

    def test_it_refuses_to_act_when_protections_cannot_be_read(self, library):
        """Better to free nothing than to delete without knowing what to keep."""
        plan = self._plan(image_retention_days=1, video_retention_days=1)

        class ExplodingDB:
            def query(self, *a, **k):
                raise RuntimeError("database unavailable")

        result = apply_plan(plan, db=ExplodingDB())

        assert result.deleted == 0
        assert any("refusing to act" in e for e in result.errors)
        assert (library.recordings_dir / "old.mp4").exists()

    def test_transcoding_is_reported_as_unimplemented_not_done(self, library):
        """
        Saying a re-encode happened when it did not would be a lie, and silently
        deleting instead of re-encoding would be much worse.
        """
        plan = self._plan(transcode_enabled=True, transcode_after_days=30)

        result = apply_plan(plan)

        assert result.transcoded == 0
        assert result.deleted == 0
        assert (library.recordings_dir / "old.mp4").exists()
        assert any("transcoding not implemented" in e for e in result.errors)

    def test_a_file_already_gone_is_not_a_failure(self, library):
        plan = self._plan(video_retention_days=30)
        (library.recordings_dir / "old.mp4").unlink()

        result = apply_plan(plan)

        assert result.failed == 0

    def test_bytes_freed_is_measured_not_estimated(self, library):
        plan = self._plan(video_retention_days=30)

        result = apply_plan(plan)

        assert result.bytes_freed == 1000
