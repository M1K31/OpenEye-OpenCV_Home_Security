# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for moving detections between people, and their training data with them.

Assignment used to relabel records and stop. After assigning 300 detections to
Mikel, one installation held:

    unknown1   400 detections   701 gallery images   701 encodings
    Mikel      300 detections   205 gallery images   205 encodings

The same face trained under two identities, so new faces matched whichever was
nearer and the placeholder kept collecting — a loop that does not resolve on its
own.

The fix treats detected/ as DERIVED from detections and rebuilds it on both
sides of a move. What these tests defend is mostly the boundaries: uploaded/ is
never touched, both sides are rebuilt rather than only the one being named, and
a preview changes nothing.
"""

import pytest

from backend.core import person_reassignment


class TestThePlanIsHonest:
    def test_a_preview_reports_without_writing(self, monkeypatch):
        calls = []
        monkeypatch.setattr(person_reassignment, "rebuild_gallery",
                            lambda *a, **k: calls.append(a) or 0)

        class Row:
            def __init__(self, i, name, snap="x.jpg"):
                self.id, self.person_name, self.snapshot_path = i, name, snap

        class Query:
            def __init__(self, rows): self._rows = rows
            def filter(self, *a, **k): return self
            def all(self): return self._rows
            def count(self): return len(self._rows)
            def first(self): return None

        class DB:
            def query(self, *a, **k): return Query([Row(1, "unknown1")])

        plan = person_reassignment.reassign(DB(), [1], "Mikel", dry_run=True)

        assert plan.dry_run is True
        assert calls == [], "a preview must not rebuild anything"

    def test_an_empty_target_name_is_refused(self):
        class DB:
            def query(self, *a, **k):
                raise AssertionError("should not reach the database")

        plan = person_reassignment.reassign(DB(), [1], "   ", dry_run=True)

        assert plan.detections_moved == 0
        assert any("no target person" in n for n in plan.notes)

    def test_no_matching_detections_is_not_an_error(self):
        class Query:
            def filter(self, *a, **k): return self
            def all(self): return []

        class DB:
            def query(self, *a, **k): return Query()

        plan = person_reassignment.reassign(DB(), [999], "Mikel", dry_run=True)

        assert plan.detections_moved == 0
        assert any("no matching detections" in n for n in plan.notes)


class TestBothSidesAreRebuilt:
    def test_the_person_losing_detections_is_rebuilt_too(self, monkeypatch):
        """
        A cluster can genuinely hold two people. Separating them must leave BOTH
        correct — rebuilding only the person being named would leave the other
        still trained on faces that are no longer theirs, which is the loop this
        exists to break.
        """
        rebuilt = []
        monkeypatch.setattr(person_reassignment, "rebuild_gallery",
                            lambda person, db, dry_run=True: rebuilt.append(person) or 0)

        class Row:
            def __init__(self, i, name):
                self.id, self.person_name, self.snapshot_path = i, name, "x.jpg"

        class Query:
            def __init__(self, rows): self._rows = rows
            def filter(self, *a, **k): return self
            def all(self): return self._rows
            def count(self): return 0
            def first(self):
                return type('P', (), {'id': 7})()   # person already exists
            def update(self, *a, **k): return len(self._rows)

        class DB:
            def query(self, *a, **k): return Query([Row(1, "unknown1")])
            def commit(self): pass
            def add(self, obj): pass
            def flush(self): pass

        person_reassignment.reassign(DB(), [1], "Mikel",
                                     dry_run=False, retrain=False)

        assert "unknown1" in rebuilt, "the person losing detections was not rebuilt"
        assert "Mikel" in rebuilt

    def test_unknown_is_not_treated_as_a_person_losing_detections(self, monkeypatch):
        rebuilt = []
        monkeypatch.setattr(person_reassignment, "rebuild_gallery",
                            lambda person, db, dry_run=True: rebuilt.append(person) or 0)

        class Row:
            def __init__(self, i, name):
                self.id, self.person_name, self.snapshot_path = i, name, "x.jpg"

        class Query:
            def __init__(self, rows): self._rows = rows
            def filter(self, *a, **k): return self
            def all(self): return self._rows
            def count(self): return 0
            def first(self):
                return type('P', (), {'id': 7})()
            def update(self, *a, **k): return len(self._rows)

        class DB:
            def query(self, *a, **k): return Query([Row(1, "Unknown")])
            def commit(self): pass
            def add(self, obj): pass
            def flush(self): pass

        person_reassignment.reassign(DB(), [1], "Mikel",
                                     dry_run=False, retrain=False)

        assert "Unknown" not in rebuilt


class TestRebuildBoundaries:
    def test_only_detected_is_rebuilt(self):
        """
        uploaded/ holds photographs a person chose, and no automatic process
        gets to remove them. Without this separation the rebuild would delete
        the best training images a person has.
        """
        import inspect
        source = inspect.getsource(person_reassignment.rebuild_gallery)

        assert "detected_dir" in source
        assert "uploaded" not in source.replace("uploaded/ is authored", "")

    def test_filenames_are_stable_so_a_rebuild_is_idempotent(self):
        """
        Running a rebuild twice must not produce a second copy of everything,
        so the name has to be derived from the detection rather than a counter.
        """
        import inspect
        source = inspect.getsource(person_reassignment.rebuild_gallery)

        assert "row.id" in source


class TestRebuildCannotEmptyAGallery:
    """
    A rebuild deletes images whose detection has gone. That is correct — the
    gallery is derived — but it must never be the whole gallery on the strength
    of finding nothing to replace it with.

    This happened: a rebuild ran while Mikel's detections had just been renamed
    away by a clustering bug, found no snapshot-carrying detections for him, and
    took his gallery from 205 images to 0.
    """

    @pytest.fixture
    def person(self, tmp_path, monkeypatch):
        class FakePaths:
            faces_dir = tmp_path
        monkeypatch.setattr("backend.core.paths.paths", FakePaths)
        gallery = tmp_path / "Mikel" / "detected"
        gallery.mkdir(parents=True)
        for i in range(3):
            (gallery / f"20260815_21260{i}_cam_{i}.jpg").write_bytes(b"\xff\xd8\xff")
        return tmp_path

    def test_it_refuses_when_there_is_nothing_to_replace_them_with(self, person):
        """No detections, but images present — that is a mistake, not a command."""
        class Query:
            def filter(self, *a, **k): return self
            def all(self): return []

        class DB:
            def query(self, *a, **k): return Query()

        from backend.core.person_reassignment import rebuild_gallery

        remaining = rebuild_gallery("Mikel", DB(), dry_run=False)

        assert remaining == 3, "the gallery was emptied"
        assert len(list((person / "Mikel" / "detected").iterdir())) == 3

    def test_an_empty_gallery_and_no_detections_is_fine(self, person):
        """Nothing to protect, so nothing to refuse."""
        class Query:
            def filter(self, *a, **k): return self
            def all(self): return []

        class DB:
            def query(self, *a, **k): return Query()

        from backend.core.person_reassignment import rebuild_gallery

        assert rebuild_gallery("Nobody", DB(), dry_run=False) == 0

    def test_copies_happen_before_deletions(self):
        """
        Ordering, not just outcome. Deleting first means a source that cannot be
        read leaves a hole; copying first means the worst case is a stale extra.
        """
        import inspect
        from backend.core import person_reassignment

        source = inspect.getsource(person_reassignment.rebuild_gallery)
        copy_at = source.index("shutil.copy2")
        delete_at = source.index("path.unlink()")

        assert copy_at < delete_at, "deletion still happens before copying"
