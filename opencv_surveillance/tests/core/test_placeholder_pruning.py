# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
A placeholder that describes nobody must stop being able to match anybody.

The defect
----------
An `unknownN` gallery holds faces nobody has identified yet. Once those
detections are assigned to a real person the placeholder describes nothing —
but its folder survived, and so did the encodings trained from it.

Measured on a live install: `unknown1` had **no detections, no person record,
and twelve images**, and the recogniser still carried twelve encodings under
that name. Those were pictures of somebody since identified as Mikel. The
placeholder could therefore win a match against the very person whose
detections had been moved out of it, and be recreated from them.

What must not be pruned
-----------------------
Two guards, both load-bearing:

- A placeholder that still HAS detections is still doing its job.
- A gallery with anything in `uploaded/` was authored by a person. Somebody put
  those photographs there deliberately, which makes it a real person under an
  unfortunate name, not a placeholder.

Only `detected/` is removed, and only for auto-generated names. That directory
is derived from detections by definition, so for a person with none the correct
contents are none — this makes derived data agree with its source rather than
discarding anything anyone authored.
"""

import pytest

from backend.core.person_reassignment import prune_orphaned_placeholders


@pytest.fixture
def gallery(tmp_path, monkeypatch):
    """A faces directory the pruner will look at."""
    from backend.core import paths as paths_module

    faces = tmp_path / "faces"
    faces.mkdir(exist_ok=True)
    monkeypatch.setattr(paths_module.paths, "faces_dir", faces, raising=False)
    return faces


def _person(faces, name, detected=0, uploaded=0):
    for sub, count in (("detected", detected), ("uploaded", uploaded)):
        directory = faces / name / sub
        directory.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            (directory / f"{i}.jpg").write_bytes(b"not really a jpeg")
    return faces / name


class _FakeQuery:
    def __init__(self, counts):
        self._counts = counts
        self._name = None

    def filter(self, criterion):
        # The pruner filters on person_name == <name>; the comparison object
        # carries the value on its right-hand side.
        self._name = criterion.right.value
        return self

    def count(self):
        return self._counts.get(self._name, 0)


class _FakeDB:
    def __init__(self, counts=None):
        self._counts = counts or {}

    def query(self, _model):
        return _FakeQuery(self._counts)


class TestPruning:
    def test_a_placeholder_with_no_detections_is_removed(self, gallery):
        _person(gallery, "unknown1", detected=12)

        result = prune_orphaned_placeholders(_FakeDB(), dry_run=False)

        assert any("unknown1" in line for line in result["pruned"])
        assert not (gallery / "unknown1").exists(), "the folder should be gone"

    def test_a_placeholder_that_still_has_detections_is_kept(self, gallery):
        _person(gallery, "unknown1", detected=12)

        result = prune_orphaned_placeholders(
            _FakeDB({"unknown1": 7}), dry_run=False)

        assert result["pruned"] == []
        assert any("still has 7" in line for line in result["kept"])
        assert (gallery / "unknown1" / "detected" / "0.jpg").exists()

    def test_a_gallery_with_uploaded_photographs_is_never_touched(self, gallery):
        """
        Somebody put those there. The name may be unfortunate, but the content
        is authored, and this function does not delete authored content.
        """
        _person(gallery, "unknown2", detected=3, uploaded=1)

        result = prune_orphaned_placeholders(_FakeDB(), dry_run=False)

        assert result["pruned"] == []
        assert any("uploaded" in line for line in result["kept"])
        assert (gallery / "unknown2" / "detected" / "0.jpg").exists()

    def test_real_people_are_not_examined_at_all(self, gallery):
        """Only auto-generated names qualify. Mikel is not a placeholder."""
        _person(gallery, "Mikel", detected=700)

        result = prune_orphaned_placeholders(_FakeDB(), dry_run=False)

        assert result["examined"] == []
        assert (gallery / "Mikel" / "detected" / "0.jpg").exists()

    def test_a_name_that_merely_starts_with_unknown_is_not_a_placeholder(self, gallery):
        _person(gallery, "Unknown Person", detected=2)

        result = prune_orphaned_placeholders(_FakeDB(), dry_run=False)

        assert result["examined"] == []
        assert (gallery / "Unknown Person" / "detected" / "0.jpg").exists()

    def test_a_dry_run_changes_nothing(self, gallery):
        _person(gallery, "unknown1", detected=4)

        result = prune_orphaned_placeholders(_FakeDB(), dry_run=True)

        assert any("would remove 4" in line for line in result["pruned"])
        assert (gallery / "unknown1" / "detected" / "0.jpg").exists()

    def test_a_missing_faces_directory_is_not_an_error(self, tmp_path, monkeypatch):
        from backend.core import paths as paths_module
        monkeypatch.setattr(
            paths_module.paths, "faces_dir", tmp_path / "nope", raising=False)

        result = prune_orphaned_placeholders(_FakeDB(), dry_run=False)

        assert result["examined"] == []
