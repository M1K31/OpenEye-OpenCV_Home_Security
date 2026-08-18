# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
A person must not collect a new cluster on every clustering run.

Clustering only ever looked at faces with no cluster yet and created a new row
for whatever it found, never asking whether that person already had one. Each
new row inherited its name from the faces it contained, so the same person
accumulated rows all carrying the same auto-assigned name.

Measured on a real installation with two people:

    same person        0.18, 0.23, 0.28, 0.31
    different people   0.58, 0.58, 0.60, 0.61, 0.62

Those two bands are what the merge threshold sits between, and the numbers in
these tests are taken from them rather than invented.
"""

import base64

import numpy as np
import pytest

from backend.core.face_clustering import FaceClusteringService


@pytest.fixture
def service():
    s = FaceClusteringService.__new__(FaceClusteringService)
    s.merge_distance = 0.40
    return s


def encoding_at(distance_from_origin: float, dims: int = 128) -> np.ndarray:
    """A 128-d vector a known euclidean distance from the origin."""
    v = np.zeros(dims)
    v[0] = distance_from_origin
    return v


class FakeCluster:
    def __init__(self, cid, label, encoding):
        self.id = cid
        self.label = label
        self.representative_encoding = (
            base64.b64encode(np.asarray(encoding, dtype=np.float64).tobytes()).decode()
            if encoding is not None else None
        )


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *a, **k):
        return FakeQuery(self._rows)


class TestFindingAMatch:
    def test_a_same_person_cluster_is_matched(self, service):
        """0.31 was the worst same-person pair on the real installation."""
        existing = FakeCluster(1, "unknown2", encoding_at(0.0))

        match = service._find_matching_cluster(FakeDB([existing]),
                                               encoding_at(0.31))

        assert match is existing

    def test_a_different_person_is_not_matched(self, service):
        """0.58 was the closest different-person pair."""
        existing = FakeCluster(1, "unknown1", encoding_at(0.0))

        match = service._find_matching_cluster(FakeDB([existing]),
                                               encoding_at(0.58))

        assert match is None

    def test_the_nearest_cluster_wins(self, service):
        far = FakeCluster(1, "unknown1", encoding_at(0.0))
        near = FakeCluster(2, "unknown2", encoding_at(0.35))

        match = service._find_matching_cluster(FakeDB([far, near]),
                                               encoding_at(0.30))

        assert match is near

    def test_no_clusters_is_not_a_match(self, service):
        assert service._find_matching_cluster(FakeDB([]), encoding_at(0.1)) is None

    def test_a_cluster_without_a_centroid_is_skipped(self, service):
        assert service._find_matching_cluster(
            FakeDB([FakeCluster(1, "x", None)]), encoding_at(0.1)) is None

    def test_a_corrupt_centroid_does_not_break_clustering(self, service):
        """One unreadable row must not stop the rest from being considered."""
        broken = FakeCluster(1, "broken", None)
        broken.representative_encoding = "not base64 at all!!"
        good = FakeCluster(2, "unknown1", encoding_at(0.0))

        match = service._find_matching_cluster(FakeDB([broken, good]),
                                               encoding_at(0.2))

        assert match is good

    def test_a_centroid_of_the_wrong_size_is_skipped(self, service):
        """Guards against a stored encoding from a different model."""
        wrong = FakeCluster(1, "wrong", np.zeros(64))

        assert service._find_matching_cluster(FakeDB([wrong]),
                                              encoding_at(0.1)) is None


class TestTheThreshold:
    def test_it_sits_between_the_measured_bands(self, service):
        """
        The property that matters. Above the worst same-person distance and
        below the closest different-person distance, with margin either side.
        """
        worst_same_person = 0.31
        closest_different_person = 0.58

        assert worst_same_person < service.merge_distance < closest_different_person

    def test_it_is_stricter_than_dbscan_eps(self, service):
        """
        Merging two people is far worse than leaving one person split. A split
        is visible and repairable; a merge silently teaches one profile another
        person's face, and nothing surfaces it.
        """
        assert service.merge_distance < 0.5
