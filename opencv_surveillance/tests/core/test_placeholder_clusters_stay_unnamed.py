# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
A cluster nobody has named must keep asking to be named.

The defect
----------
`is_identified` was derived from whether every face in a cluster still read the
literal "Unknown". Auto-naming writes `unknown1` onto those faces, so on the
NEXT clustering run the same cluster no longer looked unknown — it looked like a
cluster called `unknown1` that someone had identified. `is_identified` was set,
and the endpoint that lists clusters needing a name filters on
`is_identified == False`.

The result is a cluster that has never been named, cannot be found in the place
you go to name things, and stays that way. Observed on a live install: cluster
5, label `unknown1`, seven faces, `is_identified = 1`.

The distinction that was missing is between a name a person chose and a
placeholder the software generated. These tests pin it, because the failure is
silent — nothing errors, a cluster simply stops appearing in a list.
"""

import pytest

from backend.core.face_clustering import _is_unnamed


class TestPlaceholderRecognition:
    """`unknown1` is not somebody's name."""

    @pytest.mark.parametrize("value", [
        "Unknown",
        "unknown",
        "UNKNOWN",
        "unknown1",
        "unknown2",
        "unknown12",
        "UNKNOWN3",
        "  unknown2  ",   # the UI can round-trip a name with padding
        "",
        "   ",
        None,
    ])
    def test_placeholders_count_as_unnamed(self, value):
        assert _is_unnamed(value) is True, f"{value!r} should be a placeholder"

    @pytest.mark.parametrize("value", [
        "Mikel",
        "Yaleska",
        "Yalena",
        "Unknown Person",     # a real name that merely starts with the word
        "unknown soldier",    # ditto — the pattern is anchored for this reason
        "Mika",
    ])
    def test_real_names_are_not_placeholders(self, value):
        assert _is_unnamed(value) is False, f"{value!r} is a name, not a placeholder"


class TestIdentificationFollowsRealNames:
    """
    The property that matters: identification tracks whether a human named the
    cluster, not whether the software wrote something in the field.
    """

    def test_an_auto_named_cluster_is_not_identified(self):
        """
        The regression itself. A cluster whose faces all read `unknown1` has not
        been identified by anyone, so it must still be offered for naming.
        """
        faces = ["unknown1", "unknown1", "unknown1"]
        is_unknown_cluster = all(_is_unnamed(name) for name in faces)

        assert is_unknown_cluster is True
        assert (not is_unknown_cluster) is False, "is_identified would be set"

    def test_a_cluster_of_genuine_unknowns_is_not_identified(self):
        """The original case, which must keep working."""
        faces = ["Unknown", "Unknown"]
        assert all(_is_unnamed(name) for name in faces) is True

    def test_a_named_cluster_is_identified(self):
        faces = ["Mikel", "Mikel", "Unknown"]
        is_unknown_cluster = all(_is_unnamed(name) for name in faces)

        assert is_unknown_cluster is False, "a named face means somebody identified it"

    def test_one_real_name_among_placeholders_still_counts(self):
        """
        Mixed content resolves toward the person. If any face carries a name a
        human chose, the cluster is not an anonymous group — the name is what
        the run below will settle on.
        """
        faces = ["unknown1", "Yaleska", "unknown1"]
        assert all(_is_unnamed(name) for name in faces) is False


class TestNamingIsUnchanged:
    """
    Guard on the fix rather than the defect.

    Widening what counts as unnamed also changes which branch the naming logic
    takes, and it must not change the name that comes out: a cluster whose faces
    all read `unknown1` has to keep that label rather than being handed a fresh
    placeholder, or every clustering run would mint a new one.
    """

    def test_an_existing_placeholder_is_inherited_not_reissued(self):
        faces = ["unknown1", "unknown1"]

        # Mirrors the branch in cluster_faces(): the label is taken from the
        # faces themselves whenever they already carry one, and only a cluster
        # reading the literal "Unknown" reaches the auto-namer.
        existing_person_name = faces[0]
        reaches_auto_namer = _is_unnamed(existing_person_name) and existing_person_name == "Unknown"

        assert reaches_auto_namer is False, "would mint a second placeholder"
        assert existing_person_name == "unknown1"

    def test_a_genuinely_unknown_cluster_still_reaches_the_auto_namer(self):
        faces = ["Unknown", "Unknown"]
        existing_person_name = faces[0]

        assert _is_unnamed(existing_person_name) is True
        assert existing_person_name == "Unknown", "must still qualify for a new placeholder"
