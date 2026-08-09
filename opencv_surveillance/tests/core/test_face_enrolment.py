# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for enrolment and the startup repair that makes people recognisable.

The bug these guard against is quiet: a person gains detections and a folder but
no encodings, so nothing errors and nothing works. Every assertion here is about
encodings existing, not about calls returning success.
"""

import sys
import types
from datetime import datetime
from pathlib import Path

import pytest

from backend.core import face_enrolment


class _FakeFaceManager:
    """Stands in for FaceRecognitionManager, counting what got encoded."""

    def __init__(self, faces_dir: Path, encodable=True):
        self.faces_dir = faces_dir
        self.known_face_names = []
        self.encodable = encodable
        self.trained_calls = []

    def train_person(self, person_name):
        self.trained_calls.append(person_name)
        folder = self.faces_dir / person_name
        photos = (
            [f for f in folder.iterdir() if f.suffix.lower() in (".jpg", ".png")]
            if folder.is_dir() else []
        )
        added = len(photos) if self.encodable else 0
        # Mirror the real trainer: replace this person's encodings wholesale.
        self.known_face_names = [n for n in self.known_face_names if n != person_name]
        self.known_face_names.extend([person_name] * added)
        # And mirror its most surprising behaviour — success even when nothing
        # encoded, which is the case the repair has to notice.
        return {"success": True, "encodings_added": added}


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Point paths, the snapshot resolver and the face manager at tmp_path."""
    faces_dir = tmp_path / "gallery"
    snaps_dir = tmp_path / "snaps"
    faces_dir.mkdir(exist_ok=True)
    snaps_dir.mkdir(exist_ok=True)

    fake_paths = types.SimpleNamespace(faces_dir=faces_dir, snapshots_dir=snaps_dir)
    monkeypatch.setitem(
        sys.modules, "backend.core.paths",
        types.SimpleNamespace(paths=fake_paths),
    )

    manager = _FakeFaceManager(faces_dir)
    monkeypatch.setitem(
        sys.modules, "backend.core.face_recognition",
        types.SimpleNamespace(get_face_manager=lambda *a, **k: manager),
    )
    monkeypatch.setitem(
        sys.modules, "backend.core.face_clustering",
        types.SimpleNamespace(_resolve_snapshot_path=lambda p: str(snaps_dir / p) if p else None),
    )
    return types.SimpleNamespace(
        faces_dir=faces_dir, snaps_dir=snaps_dir, manager=manager
    )


class _FakeDetection:
    def __init__(self, id, person_name, snapshot_path, camera_id="cam0"):
        self.id = id
        self.person_name = person_name
        self.snapshot_path = snapshot_path
        self.camera_id = camera_id
        self.detected_at = datetime(2026, 8, 9, 12, id % 60)


class _FakeQuery:
    """Minimal stand-in for the two query shapes the module uses."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def distinct(self):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        return _FakeQuery(self._rows[:n])

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, detections, id_filter=None):
        self.detections = detections
        self._id_filter = id_filter

    def query(self, *entities):
        # enrol_detections queries whole rows; the repair queries single columns.
        first = entities[0]
        name = getattr(first, "key", None) or getattr(first, "__name__", "")
        if name == "person_name":
            return _FakeQuery([(d.person_name,) for d in self.detections])
        if name == "id":
            return _FakeQuery([(d.id,) for d in self.detections])
        return _FakeQuery(self.detections)


def _write_snapshot(snaps_dir, name):
    (snaps_dir / name).write_bytes(b"not-a-real-jpeg")
    return name


# ---------------------------------------------------------------- name policy

@pytest.mark.parametrize("name", ["unknown", "unknown1", "unknown42", "UNKNOWN7", "", "  "])
def test_placeholder_names_are_not_people(name):
    assert face_enrolment.is_real_person_name(name) is False


@pytest.mark.parametrize("name", ["Mikel", "Yala", "unknown person", "Unknown Rider"])
def test_real_names_are_people(name):
    assert face_enrolment.is_real_person_name(name) is True


def test_enrolment_refuses_placeholder_names(wired):
    db = _FakeDB([])
    result = face_enrolment.enrol_detections(db, [1], "unknown1")
    assert result["enrolled"] == 0
    assert result["trained"] is False
    assert wired.manager.trained_calls == []


# ------------------------------------------------------------------ enrolment

def test_enrolment_copies_snapshots_and_trains(wired):
    snaps = [_write_snapshot(wired.snaps_dir, f"s{i}.jpg") for i in range(3)]
    dets = [_FakeDetection(i, "Mikel", s) for i, s in enumerate(snaps)]

    result = face_enrolment.enrol_detections(_FakeDB(dets), [0, 1, 2], "Mikel")

    assert result["enrolled"] == 3
    assert result["trained"] is True
    assert result["encodings"] == 3
    assert len(list((wired.faces_dir / "Mikel").iterdir())) == 3


def test_enrolment_reports_untrained_when_nothing_encodes(wired):
    """Photos on disk but zero encodings is the failure that used to hide."""
    wired.manager.encodable = False
    _write_snapshot(wired.snaps_dir, "s0.jpg")
    dets = [_FakeDetection(0, "Mikel", "s0.jpg")]

    result = face_enrolment.enrol_detections(_FakeDB(dets), [0], "Mikel")

    assert result["enrolled"] == 1        # the copy happened
    assert result["trained"] is False     # but the person is still unrecognisable
    assert result["encodings"] == 0


def test_enrolment_skips_missing_snapshot_files(wired):
    dets = [_FakeDetection(0, "Mikel", "vanished.jpg")]
    result = face_enrolment.enrol_detections(_FakeDB(dets), [0], "Mikel")
    assert result["enrolled"] == 0
    assert result["trained"] is False


def test_enrolment_is_idempotent(wired):
    _write_snapshot(wired.snaps_dir, "s0.jpg")
    dets = [_FakeDetection(0, "Mikel", "s0.jpg")]
    db = _FakeDB(dets)

    face_enrolment.enrol_detections(db, [0], "Mikel")
    second = face_enrolment.enrol_detections(db, [0], "Mikel")

    assert second["enrolled"] == 0
    assert second["skipped"] == 1
    assert len(list((wired.faces_dir / "Mikel").iterdir())) == 1


# --------------------------------------------------------------------- repair

def test_repair_is_a_no_op_when_everyone_is_encoded(wired):
    (wired.faces_dir / "Mikel").mkdir()
    wired.manager.known_face_names = ["Mikel"]

    summary = face_enrolment.repair_people_missing_encodings(_FakeDB([]))

    assert summary["checked"] == 0
    assert summary["repaired"] == []
    assert wired.manager.trained_calls == []


def test_repair_retrains_a_person_whose_photos_never_encoded(wired):
    """Mikel's case: gallery present, encodings absent."""
    person = wired.faces_dir / "Mikel"
    person.mkdir()
    (person / "a.jpg").write_bytes(b"x")
    (person / "b.jpg").write_bytes(b"x")

    summary = face_enrolment.repair_people_missing_encodings(_FakeDB([]))

    assert [r["person"] for r in summary["repaired"]] == ["Mikel"]
    assert wired.manager.known_face_names.count("Mikel") == 2


def test_repair_enrols_a_person_who_has_only_detections(wired):
    """Yala's case: detections attributed to her, no gallery at all."""
    _write_snapshot(wired.snaps_dir, "s0.jpg")
    dets = [_FakeDetection(0, "Yala", "s0.jpg")]

    summary = face_enrolment.repair_people_missing_encodings(_FakeDB(dets))

    assert [r["person"] for r in summary["repaired"]] == ["Yala"]
    assert (wired.faces_dir / "Yala").is_dir()
    assert "Yala" in wired.manager.known_face_names


def test_repair_ignores_auto_generated_unknown_clusters(wired):
    for label in ("unknown1", "unknown8"):
        folder = wired.faces_dir / label
        folder.mkdir()
        (folder / "a.jpg").write_bytes(b"x")

    summary = face_enrolment.repair_people_missing_encodings(_FakeDB([]))

    assert summary["checked"] == 0
    assert wired.manager.trained_calls == []


def test_repair_reports_people_it_could_not_fix(wired):
    wired.manager.encodable = False
    person = wired.faces_dir / "Mikel"
    person.mkdir()
    (person / "a.jpg").write_bytes(b"x")

    summary = face_enrolment.repair_people_missing_encodings(_FakeDB([]))

    assert summary["repaired"] == []
    assert [f["person"] for f in summary["failed"]] == ["Mikel"]


def test_repair_bounds_how_many_detections_it_enrols(wired, monkeypatch):
    """
    A person with thousands of detections must not stall the caller while every
    one of them is copied and encoded.
    """
    snaps = [_write_snapshot(wired.snaps_dir, f"s{i}.jpg") for i in range(10)]
    dets = [_FakeDetection(i, "Yala", s) for i, s in enumerate(snaps)]

    seen = {}

    def _spy(db, face_ids, person_name):
        seen[person_name] = list(face_ids)
        return {"enrolled": len(face_ids), "trained": True}

    monkeypatch.setattr(face_enrolment, "enrol_detections", _spy)

    face_enrolment.repair_people_missing_encodings(_FakeDB(dets), limit_per_person=4)

    assert len(seen["Yala"]) == 4
