# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for keeping the face gallery bounded.

Recognition compares every detected face against the whole gallery on every
frame, so the size of the gallery is a per-frame CPU cost on the oldest hardware
this project supports. Training used to append without limit, which meant the
daily refresh — the rule that keeps a likeness current — steadily eroded the CPU
saving the capture policy exists to deliver.

What is asserted here is that the gallery stops growing without losing the
variety that makes recognition work: redundant encodings are refused, and when
the cap is reached it is the *most redundant* encoding that goes, not the
oldest.
"""

import numpy as np
import pytest

pytest.importorskip("face_recognition")

from backend.core import face_recognition as fr


@pytest.fixture
def manager():
    m = fr.FaceRecognitionManager.__new__(fr.FaceRecognitionManager)
    m.known_face_encodings = []
    m.known_face_names = []
    return m


def enc(seed, scale=1.0):
    """A deterministic 128-d encoding; `scale` moves it away from the origin."""
    rng = np.random.default_rng(seed)
    v = rng.normal(size=128)
    return v / np.linalg.norm(v) * scale


class TestRedundancy:
    def test_an_encoding_close_to_an_existing_one_is_redundant(self, manager):
        base = enc(1)
        manager.known_face_encodings = [base]
        manager.known_face_names = ["Mikel"]

        nudge = base + np.random.default_rng(2).normal(size=128) * 0.0005
        assert manager._is_redundant(nudge, manager._indices_for("Mikel")) is True

    def test_a_genuinely_different_encoding_is_kept(self, manager):
        manager.known_face_encodings = [enc(1)]
        manager.known_face_names = ["Mikel"]

        far = enc(99)
        distance = np.linalg.norm(far - manager.known_face_encodings[0])
        assert distance > fr.DUPLICATE_DISTANCE, "test premise"
        assert manager._is_redundant(far, manager._indices_for("Mikel")) is False

    def test_the_first_encoding_for_a_person_is_never_redundant(self, manager):
        assert manager._is_redundant(enc(1), []) is False

    def test_redundancy_is_judged_per_person(self, manager):
        """Yala's encodings must not suppress a capture of Mikel."""
        base = enc(1)
        manager.known_face_encodings = [base]
        manager.known_face_names = ["Yala"]

        assert manager._is_redundant(base, manager._indices_for("Mikel")) is False


class TestTheCap:
    def test_nothing_is_evicted_below_the_cap(self, manager):
        manager.known_face_encodings = [enc(i) for i in range(10)]
        manager.known_face_names = ["Mikel"] * 10

        assert manager._evict_to_cap("Mikel") == 0
        assert len(manager.known_face_encodings) == 10

    def test_eviction_stops_exactly_at_the_cap(self, manager):
        over = fr.MAX_ENCODINGS_PER_PERSON + 12
        manager.known_face_encodings = [enc(i) for i in range(over)]
        manager.known_face_names = ["Mikel"] * over

        removed = manager._evict_to_cap("Mikel")

        assert removed == 12
        assert len(manager._indices_for("Mikel")) == fr.MAX_ENCODINGS_PER_PERSON

    def test_eviction_removes_the_redundant_not_the_oldest(self, manager):
        """
        The property that makes the cap safe.

        A rare capture — one night-time shot among many daytime ones — is worth
        more than any of the ones that resemble each other, and it is usually
        the oldest. Dropping by age would throw away exactly the coverage that
        makes recognition work in unusual conditions.
        """
        cap = fr.MAX_ENCODINGS_PER_PERSON
        rare = enc(7, scale=40.0)          # far from everything, added FIRST
        crowd = [enc(1) + np.random.default_rng(i).normal(size=128) * 0.01
                 for i in range(cap + 5)]  # a tight cluster of near-identicals

        manager.known_face_encodings = [rare] + crowd
        manager.known_face_names = ["Mikel"] * (len(crowd) + 1)

        manager._evict_to_cap("Mikel")

        survivors = [manager.known_face_encodings[i]
                     for i in manager._indices_for("Mikel")]
        assert any(np.array_equal(rare, s) for s in survivors), \
            "the rare encoding was evicted; eviction is dropping coverage"

    def test_eviction_leaves_other_people_alone(self, manager):
        over = fr.MAX_ENCODINGS_PER_PERSON + 5
        manager.known_face_encodings = [enc(i) for i in range(over)] + [enc(9001)]
        manager.known_face_names = ["Mikel"] * over + ["Yala"]

        manager._evict_to_cap("Mikel")

        assert len(manager._indices_for("Yala")) == 1
        assert len(manager._indices_for("Mikel")) == fr.MAX_ENCODINGS_PER_PERSON


class TestTheThresholdItself:
    def test_redundancy_is_stricter_than_recognition(self):
        """
        Dedupe asks "does this teach us anything new?", which must be a far
        stricter question than "is this the same person?". If the two were
        close, dedupe would start refusing genuinely different views of a face.
        """
        assert fr.DUPLICATE_DISTANCE < 0.4
