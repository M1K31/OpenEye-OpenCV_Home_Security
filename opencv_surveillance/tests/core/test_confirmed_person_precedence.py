# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for a cluster recognising somebody the user already named.

Recognition compares a single face against every encoding and takes the
nearest, so a new face is measured against named people. What never happened
was the comparison between identities: nothing asked whether a whole cluster
was a person who already exists.

The result was a placeholder that could not be dislodged. One installation
held:

    unknown1   503 faces, trained
    Mikel      205 images of the same face, trained

Every new sighting matched the larger pile, so the placeholder grew and the
real profile starved. Renaming did not help, because the next clustering run
minted the placeholder again from the same faces.

Confirmed people are deliberately excluded from clustering input — that stops a
cluster stealing their detections — which also means a cluster can never meet
them by accident. These tests cover the deliberate meeting, and its limits: a
cluster that is NOT a known person must still become a new person, because
handing a stranger's face to a real profile trains that profile on the wrong
person and is the worse of the two errors.
"""

import numpy as np
import pytest

from backend.core.face_clustering import FaceClusteringService


class FakePerson:
    def __init__(self, name, origin="user", confirmed_at=None):
        self.name = name
        self.origin = origin
        self.confirmed_at = confirmed_at

    @property
    def is_confirmed(self):
        return self.origin == "user" or self.confirmed_at is not None


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, people):
        self._people = people

    def query(self, *a, **k):
        return FakeQuery(self._people)


class FakeManager:
    def __init__(self, names, encodings):
        self.known_face_names = names
        self.known_face_encodings = encodings


@pytest.fixture
def engine():
    return FaceClusteringService()


def encodings_near(base, n, spread, seed=0):
    """n encodings scattered `spread` away from base, deterministically."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        step = rng.normal(size=128)
        step /= np.linalg.norm(step)
        out.append(base + step * spread)
    return out


def a_different_face(base, distance=0.60, seed=0):
    """
    Another person, at a realistic remove.

    Two independent random 128-d vectors sit about 16 apart, which no threshold
    could fail to separate — a test built that way passes even when the
    comparison is broken. Real different-person distances were measured at
    0.58-0.62, so a stranger is placed deliberately at that remove.
    """
    rng = np.random.default_rng(seed)
    step = rng.normal(size=128)
    step /= np.linalg.norm(step)
    return base + step * distance


@pytest.fixture
def mikel_base():
    rng = np.random.default_rng(42)
    return rng.normal(size=128)


class TestAKnownPersonIsRecognised:
    def test_a_cluster_of_the_same_face_adopts_their_name(
            self, engine, mikel_base, monkeypatch):
        gallery = encodings_near(mikel_base, 40, 0.20, seed=1)
        monkeypatch.setattr("backend.core.face_recognition.get_face_manager",
                            lambda: FakeManager(["Mikel"] * 40, gallery))

        centroid = np.mean(encodings_near(mikel_base, 10, 0.20, seed=2), axis=0)
        db = FakeDB([FakePerson("Mikel")])

        assert engine._match_confirmed_person(db, centroid) == "Mikel"

    def test_the_nearest_person_wins_when_several_are_known(
            self, engine, mikel_base, monkeypatch):
        rng = np.random.default_rng(7)
        other_base = rng.normal(size=128)

        names = ["Mikel"] * 30 + ["Yalena"] * 30
        gallery = (encodings_near(mikel_base, 30, 0.20, seed=3)
                   + encodings_near(other_base, 30, 0.20, seed=4))
        monkeypatch.setattr("backend.core.face_recognition.get_face_manager",
                            lambda: FakeManager(names, gallery))

        centroid = np.mean(encodings_near(mikel_base, 10, 0.20, seed=5), axis=0)
        db = FakeDB([FakePerson("Mikel"), FakePerson("Yalena")])

        assert engine._match_confirmed_person(db, centroid) == "Mikel"


class TestAStrangerStaysAStranger:
    def test_a_different_face_is_not_claimed(self, engine, mikel_base, monkeypatch):
        """
        The error that matters. Claiming a stranger for a real profile trains
        that profile on somebody else's face, which is silent and compounding —
        far worse than leaving a new placeholder the user can rename.
        """
        gallery = encodings_near(mikel_base, 40, 0.20, seed=6)
        monkeypatch.setattr("backend.core.face_recognition.get_face_manager",
                            lambda: FakeManager(["Mikel"] * 40, gallery))

        stranger = a_different_face(mikel_base, seed=99)
        centroid = np.mean(encodings_near(stranger, 10, 0.10, seed=7), axis=0)

        assert engine._match_confirmed_person(FakeDB([FakePerson("Mikel")]),
                                              centroid) is None

    def test_one_lucky_frame_cannot_hand_over_a_cluster(
            self, engine, mikel_base, monkeypatch):
        """
        Scoring on the single nearest encoding would let one coincidental frame
        claim a whole cluster, so the score is the mean of the ten nearest.
        Here a stranger's gallery contains exactly one near-perfect match.
        """
        stranger = a_different_face(mikel_base, seed=5)
        centroid = np.mean(encodings_near(stranger, 10, 0.10, seed=8), axis=0)

        gallery = encodings_near(mikel_base, 40, 0.20, seed=9)
        gallery.append(centroid + np.full(128, 0.001))   # the lucky frame
        monkeypatch.setattr("backend.core.face_recognition.get_face_manager",
                            lambda: FakeManager(["Mikel"] * len(gallery), gallery))

        assert engine._match_confirmed_person(FakeDB([FakePerson("Mikel")]),
                                              centroid) is None


class TestOnlyConfirmedPeopleQualify:
    def test_an_auto_placeholder_is_never_adopted(
            self, engine, mikel_base, monkeypatch):
        """
        unknown1 is exactly what this exists to stop creating. Adopting it
        would reinstate the loop rather than break it.
        """
        gallery = encodings_near(mikel_base, 40, 0.20, seed=10)
        monkeypatch.setattr("backend.core.face_recognition.get_face_manager",
                            lambda: FakeManager(["unknown1"] * 40, gallery))

        centroid = np.mean(encodings_near(mikel_base, 10, 0.20, seed=11), axis=0)
        db = FakeDB([FakePerson("unknown1", origin="cluster")])

        assert engine._match_confirmed_person(db, centroid) is None

    def test_an_unconfirmed_cluster_person_is_not_adopted(
            self, engine, mikel_base, monkeypatch):
        gallery = encodings_near(mikel_base, 40, 0.20, seed=12)
        monkeypatch.setattr("backend.core.face_recognition.get_face_manager",
                            lambda: FakeManager(["Someone"] * 40, gallery))

        centroid = np.mean(encodings_near(mikel_base, 10, 0.20, seed=13), axis=0)
        db = FakeDB([FakePerson("Someone", origin="cluster")])

        assert engine._match_confirmed_person(db, centroid) is None


class TestDegradesQuietly:
    def test_no_people_at_all(self, engine, monkeypatch):
        monkeypatch.setattr("backend.core.face_recognition.get_face_manager",
                            lambda: FakeManager([], []))
        assert engine._match_confirmed_person(FakeDB([]), np.zeros(128)) is None

    def test_a_person_with_no_encodings_yet(self, engine, monkeypatch):
        monkeypatch.setattr("backend.core.face_recognition.get_face_manager",
                            lambda: FakeManager([], []))
        db = FakeDB([FakePerson("Mikel")])
        assert engine._match_confirmed_person(db, np.zeros(128)) is None

    def test_mismatched_manager_state_is_refused(self, engine, monkeypatch):
        """Names and encodings out of step means nothing can be trusted."""
        monkeypatch.setattr("backend.core.face_recognition.get_face_manager",
                            lambda: FakeManager(["Mikel", "Yalena"],
                                                [np.zeros(128)]))
        db = FakeDB([FakePerson("Mikel")])
        assert engine._match_confirmed_person(db, np.zeros(128)) is None
