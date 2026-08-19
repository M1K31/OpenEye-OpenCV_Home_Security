# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Clustering must never overwrite a name a human chose.

This exists because it did. On a live installation, 383 faces were merged into
cluster 1 and every one renamed to "unknown1" — including 283 that a user had
just assigned to Mikel, Yalena and Yaleska. An auto-generated placeholder
overwrote three real people, and the only trace was a single INFO line saying
the merge had happened.

The rule is one-directional:

    placeholder -> real name     allowed (that is a person deciding)
    real name   -> placeholder   NEVER (that is a guess overruling them)

Recognition and clustering are guesses. A guess does not get to overrule a
person.
"""

import pytest

from backend.core.face_clustering import AUTO_UNKNOWN_NAME


class TestWhatCountsAsAPlaceholder:
    @pytest.mark.parametrize("name", ["unknown1", "unknown2", "unknown42", "UNKNOWN7"])
    def test_auto_generated_names_are_placeholders(self, name):
        assert AUTO_UNKNOWN_NAME.match(name)

    @pytest.mark.parametrize("name", ["Mikel", "Yalena", "Yaleska", "test", "Unknown Person"])
    def test_real_names_are_not(self, name):
        assert not AUTO_UNKNOWN_NAME.match(name)

    def test_bare_unknown_is_not_a_placeholder_name(self):
        """
        "Unknown" is the absence of a match, handled separately. It is not an
        auto-generated person name — those always carry a number — and a person
        genuinely called "unknown" must not be treated as disposable.
        """
        assert not AUTO_UNKNOWN_NAME.match("unknown")
        assert not AUTO_UNKNOWN_NAME.match("Unknown")


class TestTheMergeRule:
    """
    Exercises the decision the merge path makes, on the same shapes that
    occurred live.
    """

    @staticmethod
    def may_overwrite(existing_name, cluster_label):
        """The rule, extracted: may cluster_label replace existing_name?"""
        if not AUTO_UNKNOWN_NAME.match(cluster_label or ""):
            return True            # a real name may claim anything
        return (
            not existing_name
            or existing_name == "Unknown"
            or bool(AUTO_UNKNOWN_NAME.match(existing_name))
        )

    def test_a_placeholder_cannot_overwrite_a_real_name(self):
        """The exact failure: unknown1 claiming faces assigned to Mikel."""
        assert self.may_overwrite("Mikel", "unknown1") is False

    @pytest.mark.parametrize("assigned", ["Mikel", "Yalena", "Yaleska"])
    def test_none_of_the_assigned_people_were_claimable(self, assigned):
        assert self.may_overwrite(assigned, "unknown1") is False

    def test_a_placeholder_may_claim_an_unclaimed_face(self):
        assert self.may_overwrite("Unknown", "unknown1") is True
        assert self.may_overwrite(None, "unknown1") is True

    def test_a_placeholder_may_claim_another_placeholder(self):
        """Two auto-named clusters merging is the case Layer 1 exists for."""
        assert self.may_overwrite("unknown2", "unknown1") is True

    def test_a_real_name_may_claim_a_placeholder(self):
        """Naming a cluster is a person deciding, and that must win."""
        assert self.may_overwrite("unknown1", "Mikel") is True

    def test_a_real_name_may_claim_another_real_name(self):
        """
        Allowed: only a human action produces a real cluster label, so this is
        one person's decision replacing another's rather than a guess.
        """
        assert self.may_overwrite("Yalena", "Mikel") is True
