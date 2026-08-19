# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for giving every existing person a row.

The migration reads three unlinked stores — detection names, cluster labels, and
gallery folders — and produces one row per person. What matters most is what it
does NOT do: invent a person out of "Unknown", lose a hand-made gallery, or
misfile provenance in a way that later stops snapshots being kept.

Origin is inferred from the name here and ONLY here. Nothing recorded it at the
time, so history has to be guessed once; afterwards it is a stored fact.
"""

import pytest

from backend.core.person_migration import (
    AUTO_NAME_PATTERN,
    ORIGIN_CLUSTER,
    ORIGIN_USER,
    build_plan,
)


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def group_by(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows


class FakeDB:
    """Answers the three queries the planner makes, in the order it makes them."""

    def __init__(self, detections=(), clusters=(), persons=()):
        self.detections = list(detections)   # (person_name, count)
        self.clusters = list(clusters)       # (id, label)
        self.persons = list(persons)
        self._call = 0

    def query(self, *args):
        self._call += 1
        if self._call == 1:
            return FakeQuery(self.persons)
        if self._call == 2:
            return FakeQuery(self.detections)
        return FakeQuery(self.clusters)


@pytest.fixture(autouse=True)
def no_galleries(monkeypatch):
    monkeypatch.setattr("backend.core.person_migration._gallery_counts", lambda: {})


class TestOriginIsInferredOnce:
    @pytest.mark.parametrize("name", ["unknown1", "unknown2", "UNKNOWN17"])
    def test_auto_generated_names_are_cluster_origin(self, name):
        plan = build_plan(FakeDB(detections=[(name, 10)]))

        assert plan.people[0].origin == ORIGIN_CLUSTER

    @pytest.mark.parametrize("name", ["Mikel", "Yalena", "unknown", "Unknown Person"])
    def test_everything_else_is_user_origin(self, name):
        plan = build_plan(FakeDB(detections=[(name, 5)]))

        assert plan.people[0].origin == ORIGIN_USER

    def test_the_pattern_requires_a_number(self):
        """
        "unknown" alone is not an auto-generated name — those always carry a
        number. Treating it as one would misfile a person genuinely called that.
        """
        assert AUTO_NAME_PATTERN.match("unknown1")
        assert not AUTO_NAME_PATTERN.match("unknown")


class TestUnknownIsNotAPerson:
    def test_it_never_becomes_a_row(self):
        """
        "Unknown" is the absence of an identity, not an identity. A row for it
        would make every unrecognised face in the system the same person.
        """
        plan = build_plan(FakeDB(detections=[("Unknown", 143), ("Mikel", 10)]))

        assert [p.name for p in plan.people] == ["Mikel"]

    def test_its_detections_are_counted_separately(self):
        plan = build_plan(FakeDB(detections=[("Unknown", 143)]))

        assert plan.unnamed_detections == 143
        assert plan.detections_to_link == 0

    def test_empty_and_null_names_are_ignored(self):
        plan = build_plan(FakeDB(detections=[("", 5), (None, 3), ("Mikel", 1)]))

        assert [p.name for p in plan.people] == ["Mikel"]


class TestItFindsPeopleWhereverTheyAre:
    def test_a_person_known_only_from_a_cluster_label(self):
        plan = build_plan(FakeDB(clusters=[(1, "unknown1")]))

        assert plan.people[0].name == "unknown1"
        assert plan.people[0].clusters == [1]

    def test_a_person_known_only_from_a_gallery_folder(self, monkeypatch):
        """
        Somebody made this person by hand and uploaded photographs. There are no
        detections and no cluster, and losing them here would be the migration
        quietly deleting the most deliberate data present.
        """
        monkeypatch.setattr("backend.core.person_migration._gallery_counts",
                            lambda: {"test": 0, "Grandma": 12})

        plan = build_plan(FakeDB())

        names = {p.name for p in plan.people}
        assert "Grandma" in names and "test" in names

    def test_a_hand_made_person_is_user_origin(self, monkeypatch):
        monkeypatch.setattr("backend.core.person_migration._gallery_counts",
                            lambda: {"Grandma": 12})

        plan = build_plan(FakeDB())

        assert plan.people[0].origin == ORIGIN_USER

    def test_one_person_across_all_three_stores_is_one_row(self, monkeypatch):
        monkeypatch.setattr("backend.core.person_migration._gallery_counts",
                            lambda: {"unknown1": 701})

        plan = build_plan(FakeDB(detections=[("unknown1", 400)],
                                 clusters=[(1, "unknown1")]))

        assert len(plan.people) == 1
        person = plan.people[0]
        assert person.detections == 400
        assert person.clusters == [1]
        assert person.gallery_files == 701


class TestThePlanIsReadOnly:
    def test_building_a_plan_is_a_preview(self):
        plan = build_plan(FakeDB(detections=[("Mikel", 10)]))

        assert plan.dry_run is True

    def test_it_reports_what_it_would_link(self):
        plan = build_plan(FakeDB(detections=[("Mikel", 300), ("unknown1", 400)],
                                 clusters=[(1, "unknown1")]))

        assert plan.detections_to_link == 700
        assert plan.clusters_to_link == 1

    def test_the_summary_is_safe_to_print(self):
        text = build_plan(FakeDB(detections=[("Mikel", 3)])).describe()

        assert "nothing changed" in text
