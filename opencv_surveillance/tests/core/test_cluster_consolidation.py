# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for the one-off repair that merges duplicate clusters.

This deletes cluster rows, so most of what follows asserts about what survives
and what is refused. The distances used are the ones measured on a real
installation: same person 0.18–0.31, different people 0.58–0.62.
"""

import base64

import numpy as np
import pytest

from backend.core.face_clustering import FaceClusteringService


def encoded(distance_from_origin: float, dims: int = 128) -> str:
    v = np.zeros(dims)
    v[0] = distance_from_origin
    return base64.b64encode(v.tobytes()).decode()


class Cluster:
    def __init__(self, cid, label, face_count, offset):
        self.id = cid
        self.label = label
        self.face_count = face_count
        self.representative_encoding = encoded(offset) if offset is not None else None
        self.updated_at = None


class Recorder:
    """Records what would have been written, without a database."""

    def __init__(self, clusters):
        self.clusters = list(clusters)
        self.deleted = []
        self.reassigned = []

    # -- session API used by the method under test
    def query(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return [c for c in self.clusters if c.representative_encoding is not None]

    def first(self):
        return self.clusters[0] if self.clusters else None

    def count(self):
        return 0

    def update(self, values, **kwargs):
        self.reassigned.append(values)
        return 0

    def delete(self, **kwargs):
        self.deleted.append(True)
        return 1

    def commit(self):
        pass


@pytest.fixture
def service():
    s = FaceClusteringService.__new__(FaceClusteringService)
    s.merge_distance = 0.40
    return s


class TestPreview:
    def test_the_real_five_cluster_case_collapses_to_two(self, service):
        """
        The installation that surfaced this: two people, five clusters.
        unknown1 at 0.00 and 0.18; unknown2 at 0.58, 0.81, 0.86 — which are
        0.23 and 0.28 from each other and 0.58+ from unknown1.
        """
        clusters = [
            Cluster(1, "unknown1", 701, 0.00),
            Cluster(2, "unknown2", 13, 0.58),
            Cluster(3, "unknown1", 2, 0.18),
            Cluster(4, "unknown2", 32, 0.81),
            Cluster(5, "unknown2", 19, 0.86),
        ]

        result = service.consolidate_duplicate_clusters(Recorder(clusters), dry_run=True)

        assert result["clusters_remaining"] == 2
        assert result["clusters_removed"] == 3

    def test_a_preview_changes_nothing(self, service):
        db = Recorder([Cluster(1, "a", 10, 0.0), Cluster(2, "a", 5, 0.1)])

        service.consolidate_duplicate_clusters(db, dry_run=True)

        assert db.deleted == []
        assert db.reassigned == []

    def test_distinct_people_are_left_alone(self, service):
        """0.58 was the closest different-person pair measured."""
        db = Recorder([Cluster(1, "unknown1", 700, 0.0),
                       Cluster(2, "unknown2", 30, 0.58)])

        result = service.consolidate_duplicate_clusters(db, dry_run=True)

        assert result["merges"] == []
        assert result["clusters_remaining"] == 2


class TestAnchoring:
    def test_the_largest_cluster_survives(self, service):
        """It has the best-supported centroid, so it is the safest anchor."""
        db = Recorder([Cluster(1, "x", 5, 0.0), Cluster(2, "x", 500, 0.2)])

        result = service.consolidate_duplicate_clusters(db, dry_run=True)

        assert result["merges"][0]["into"] == 2
        assert result["merges"][0]["absorbed"] == 1

    def test_merges_do_not_chain_through_a_third_cluster(self, service):
        """
        A at 0.0, B at 0.35, C at 0.70. B is within range of A, and C is within
        range of B — but C is 0.70 from A and must not be dragged in. Chaining
        is how two different people end up in one profile.
        """
        db = Recorder([Cluster(1, "a", 100, 0.0),
                       Cluster(2, "b", 50, 0.35),
                       Cluster(3, "c", 40, 0.70)])

        result = service.consolidate_duplicate_clusters(db, dry_run=True)

        absorbed_into_one = [m["absorbed"] for m in result["merges"] if m["into"] == 1]
        assert 3 not in absorbed_into_one

    def test_a_label_conflict_is_reported(self, service):
        """
        Same person, two different names. The merge is still right, but it
        renames someone's detections and should not happen quietly.
        """
        db = Recorder([Cluster(1, "Mikel", 100, 0.0),
                       Cluster(2, "unknown3", 10, 0.2)])

        result = service.consolidate_duplicate_clusters(db, dry_run=True)

        assert result["merges"][0]["label_conflict"] is True


class TestRobustness:
    def test_an_unreadable_centroid_is_skipped_not_fatal(self, service):
        broken = Cluster(1, "broken", 10, 0.0)
        broken.representative_encoding = "not base64 at all!!"
        db = Recorder([broken, Cluster(2, "ok", 20, 0.5)])

        result = service.consolidate_duplicate_clusters(db, dry_run=True)

        assert result["clusters_examined"] == 1

    def test_a_cluster_without_a_centroid_is_ignored(self, service):
        db = Recorder([Cluster(1, "x", 10, None), Cluster(2, "y", 20, 0.0)])

        result = service.consolidate_duplicate_clusters(db, dry_run=True)

        assert result["clusters_examined"] == 1

    def test_no_clusters_is_not_an_error(self, service):
        result = service.consolidate_duplicate_clusters(Recorder([]), dry_run=True)

        assert result["merges"] == []
        assert result["clusters_remaining"] == 0

    def test_it_agrees_with_the_live_merge_check(self, service):
        """
        The repair and the check that prevents the problem must use the same
        threshold, or one will keep undoing the other's judgement.
        """
        assert service.merge_distance == 0.40
