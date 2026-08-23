# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Storage thinning must never delete an unknown person's only photograph.

Thinning protects two things: profile galleries wholesale, and cluster
representative snapshots. A detection snapshot for someone not yet identified is
neither, so with `image_retention_days` set it would be deleted like any other
old image.

That deletes the one thing that makes an unknown sighting useful. Reducing what
is retained for a person who already has a profile is the point of thinning —
their gallery holds plenty and their identity is settled. Someone unidentified
has exactly one route to becoming identified, and it runs through the picture.

Thinning is off by default, so this was latent rather than active. It is the
kind of latent that only shows up once somebody turns the feature on and their
unassigned faces quietly stop being assignable.
"""

import pytest

from backend.core.storage_thinning import protected_paths


class _Row:
    """Minimal stand-in for a query result row."""
    def __init__(self, value):
        self._value = value
    def __iter__(self):
        return iter((self._value,))


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
    def filter(self, *a, **kw):
        return self
    def all(self):
        return self._rows


class _FakeDB:
    """Answers the two queries protected_paths makes, keyed by model."""
    def __init__(self, cluster_reps=(), unknown_snapshots=()):
        self.cluster_reps = list(cluster_reps)
        self.unknown_snapshots = list(unknown_snapshots)
    def query(self, column):
        owner = getattr(column, "class_", None)
        name = getattr(owner, "__name__", "")
        if name == "FaceCluster":
            return _FakeQuery([_Row(p) for p in self.cluster_reps])
        return _FakeQuery([_Row(p) for p in self.unknown_snapshots])


def test_an_unknown_persons_snapshot_is_protected(tmp_path, monkeypatch):
    """The requirement: an unidentified face keeps the image that identifies it."""
    from backend.core import paths as paths_module

    snapshots = tmp_path / "snapshots"
    snapshots.mkdir(exist_ok=True)
    img = snapshots / "face_cam1_20260823_190500.jpg"
    img.write_bytes(b"jpeg")

    monkeypatch.setattr(paths_module.paths, "snapshots_dir", snapshots, raising=False)
    faces = tmp_path / "faces"
    faces.mkdir(exist_ok=True)
    monkeypatch.setattr(paths_module.paths, "faces_dir", faces, raising=False)

    db = _FakeDB(unknown_snapshots=[f"/data/snapshots/{img.name}"])
    protected = protected_paths(db=db)

    assert img.resolve() in protected, (
        "an unknown person's snapshot was not protected, so enabling retention "
        "would delete the only image that could identify them"
    )


def test_protection_survives_a_missing_database(tmp_path, monkeypatch):
    """Thinning must still work, conservatively, without a session."""
    from backend.core import paths as paths_module
    monkeypatch.setattr(paths_module.paths, "snapshots_dir", tmp_path / "s", raising=False)
    monkeypatch.setattr(paths_module.paths, "faces_dir", tmp_path / "f", raising=False)
    assert isinstance(protected_paths(db=None), set)
