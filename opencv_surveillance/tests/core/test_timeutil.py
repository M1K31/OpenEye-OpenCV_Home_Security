# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for the single clock.

Two calls that look interchangeable are not. Column defaults said
`datetime.utcnow` while the capture pipeline passed `datetime.now()`, so one
installation stored detection times in local and everything else in UTC —
inside `face_clusters`, `last_seen_at` was local and `trained_at` beside it was
UTC.

What these tests defend is mostly the boundary: stored values are naive so
in-process comparisons keep working, serialised values carry the UTC marker so
a browser cannot mistake them for local, and the migration of stored history
uses the offset in effect at the time rather than the offset today.
"""

from datetime import datetime, timedelta, timezone

from backend.core.timeutil import utcnow, as_utc_iso, local_to_utc


class TestUtcnow:
    def test_it_is_utc(self):
        assert abs((utcnow() - datetime.utcnow()).total_seconds()) < 2

    def test_it_is_naive(self):
        """
        SQLite has no timezone type. An aware value would store the same digits
        while making every comparison against a naive one raise TypeError.
        """
        assert utcnow().tzinfo is None

    def test_it_can_be_compared_with_stored_values(self):
        stored = utcnow() - timedelta(hours=1)
        assert (utcnow() - stored).total_seconds() > 3500   # no TypeError


class TestSerialisation:
    def test_a_naive_value_is_marked_as_utc(self):
        """
        The marker is the whole point: JavaScript reads an unmarked timestamp
        as local, so unmarked UTC renders shifted by the offset.
        """
        assert as_utc_iso(datetime(2026, 8, 19, 23, 44, 9)) == "2026-08-19T23:44:09Z"

    def test_an_aware_value_is_converted_not_relabelled(self):
        aware = datetime(2026, 8, 19, 23, 44, 9,
                         tzinfo=timezone(timedelta(hours=-4)))
        assert as_utc_iso(aware) == "2026-08-20T03:44:09Z"

    def test_none_survives(self):
        assert as_utc_iso(None) is None

    def test_the_output_is_what_javascript_parses_as_utc(self):
        """
        Guards the format itself. A space separator or a missing Z sends the
        browser back to local-time parsing and reintroduces the bug.
        """
        out = as_utc_iso(datetime(2026, 1, 2, 3, 4, 5))
        assert out.endswith("Z")
        assert "T" in out and " " not in out


class TestMigratingStoredHistory:
    def test_a_local_timestamp_moves_forward_to_utc(self):
        """Western zones are behind UTC, so the stored value increases."""
        local = datetime(2026, 8, 19, 23, 44, 9)
        converted = local_to_utc(local)

        offset = local.astimezone().utcoffset()
        assert converted == local - offset

    def test_the_offset_is_the_one_in_effect_at_that_moment(self):
        """
        The trap. In any zone observing daylight saving, January and July have
        different offsets, so a flat subtraction of today's offset corrupts
        half the stored history. Skipped where the host has no DST, since
        there is then nothing to distinguish.
        """
        winter = datetime(2026, 1, 15, 12, 0, 0)
        summer = datetime(2026, 7, 15, 12, 0, 0)

        winter_offset = winter.astimezone().utcoffset()
        summer_offset = summer.astimezone().utcoffset()
        if winter_offset == summer_offset:
            import pytest
            pytest.skip("host timezone does not observe daylight saving")

        assert (winter - local_to_utc(winter)) == winter_offset
        assert (summer - local_to_utc(summer)) == summer_offset
        assert local_to_utc(winter) - winter != local_to_utc(summer) - summer

    def test_an_already_aware_value_is_handled(self):
        aware = datetime(2026, 8, 19, 23, 44, 9, tzinfo=timezone.utc)
        assert local_to_utc(aware) == datetime(2026, 8, 19, 23, 44, 9)

    def test_converting_is_not_idempotent_and_must_run_once(self):
        """
        Documents why the migration needs a guard rather than being safe to
        repeat: each pass shifts the value again.
        """
        once = local_to_utc(datetime(2026, 8, 19, 12, 0, 0))
        twice = local_to_utc(once)
        if datetime(2026, 8, 19, 12).astimezone().utcoffset():
            assert twice != once
