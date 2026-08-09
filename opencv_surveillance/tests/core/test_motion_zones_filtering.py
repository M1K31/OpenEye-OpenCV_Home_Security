# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Zone filtering behaviour for MotionDetector.

These are the tests whose absence let two real defects survive in the detection
path. `_filter_motion_by_zones` is a pure function over synthetic contours — no
camera, no database, no frames from hardware — so there was never a technical
reason not to cover it, and the bugs it hid were exactly the kind unit tests
catch:

  * membership decided by the contour centroid while being documented as an
    intersection test, so motion straddling a boundary was classified by where
    its centre happened to land;
  * a `break` outside the threshold check, so with overlapping inclusion zones
    only the first zone was ever consulted — and "first" came from an unordered
    query, making the result vary between runs for an identical scene.
"""
import numpy as np
import pytest

from backend.core.motion_detector import MotionDetector


FRAME_W, FRAME_H = 640, 480


def rect_contour(x1, y1, x2, y2):
    """Axis-aligned rectangular contour in OpenCV's Nx1x2 int32 layout."""
    return np.array(
        [[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]], dtype=np.int32)


def zone(zone_id, x1, y1, x2, y2, *, exclusion=False, multiplier=1.0):
    """Zone dict in the detector's internal format, coordinates normalised."""
    return {
        "id": zone_id,
        "name": f"zone-{zone_id}",
        "coordinates": [
            {"x": x1 / FRAME_W, "y": y1 / FRAME_H},
            {"x": x2 / FRAME_W, "y": y1 / FRAME_H},
            {"x": x2 / FRAME_W, "y": y2 / FRAME_H},
            {"x": x1 / FRAME_W, "y": y2 / FRAME_H},
        ],
        "is_exclusion_zone": exclusion,
        "sensitivity_multiplier": multiplier,
        "color": "#00FF00",
    }


@pytest.fixture
def detector():
    d = MotionDetector()
    d.polygon_zones = []
    d._zone_mask_cache = {}
    return d


def filter_(detector, contours, min_area=100):
    return detector._filter_motion_by_zones(contours, FRAME_W, FRAME_H, min_area)


# --- baseline -------------------------------------------------------------

def test_no_zones_keeps_contours_above_threshold(detector):
    kept, triggered = filter_(detector, [rect_contour(10, 10, 100, 100)])
    assert len(kept) == 1
    assert triggered == []


def test_no_zones_drops_contours_below_threshold(detector):
    kept, _ = filter_(detector, [rect_contour(0, 0, 5, 5)], min_area=100)
    assert kept == []


# --- exclusion zones ------------------------------------------------------

def test_motion_fully_inside_exclusion_zone_is_dropped(detector):
    detector.polygon_zones = [zone(1, 0, 0, 320, 240, exclusion=True)]
    kept, _ = filter_(detector, [rect_contour(50, 50, 150, 150)])
    assert kept == []


def test_motion_straddling_an_exclusion_edge_is_still_dropped(detector):
    """
    The centroid regression, stated as a test.

    This contour spans x=270..370 against a zone ending at x=320, so its centre
    sits at x=320 — right on the boundary, the case the old point test decided
    by rounding. Half its area is inside an area the user asked to ignore, so it
    must be excluded regardless of where the middle pixel falls.
    """
    detector.polygon_zones = [zone(1, 0, 0, 320, 480, exclusion=True)]
    kept, _ = filter_(detector, [rect_contour(270, 100, 370, 200)])
    assert kept == [], "motion overlapping an exclusion zone must be suppressed"


def test_motion_barely_clipping_an_exclusion_zone_is_dropped(detector):
    """A small overlap is enough: clipping the ignored area still means the
    ignored area is involved."""
    detector.polygon_zones = [zone(1, 0, 0, 200, 480, exclusion=True)]
    kept, _ = filter_(detector, [rect_contour(180, 100, 280, 200)])   # 20% inside
    assert kept == []


def test_motion_clear_of_the_exclusion_zone_is_kept(detector):
    detector.polygon_zones = [zone(1, 0, 0, 200, 480, exclusion=True)]
    kept, _ = filter_(detector, [rect_contour(300, 100, 400, 200)])
    assert len(kept) == 1


# --- inclusion zones ------------------------------------------------------

def test_motion_inside_inclusion_zone_is_kept_and_attributed(detector):
    detector.polygon_zones = [zone(7, 0, 0, 320, 240)]
    kept, triggered = filter_(detector, [rect_contour(50, 50, 150, 150)])
    assert len(kept) == 1
    assert triggered == [7]


def test_motion_outside_every_inclusion_zone_is_dropped(detector):
    detector.polygon_zones = [zone(7, 0, 0, 200, 200)]
    kept, triggered = filter_(detector, [rect_contour(400, 300, 500, 400)])
    assert kept == []
    assert triggered == []


def test_large_blob_overlapping_an_inclusion_edge_is_kept(detector):
    """The mirror of the exclusion case: a big contour whose centroid falls
    outside the watched area used to be discarded, losing real motion."""
    detector.polygon_zones = [zone(7, 0, 0, 200, 480)]
    kept, triggered = filter_(detector, [rect_contour(100, 100, 400, 200)])
    assert len(kept) == 1, "motion substantially inside a watched zone must be kept"
    assert triggered == [7]


# --- overlapping inclusion zones (the `break` defect) ---------------------

def test_second_zone_can_accept_what_the_first_rejects(detector):
    """
    Zone 1 is deliberately insensitive (multiplier 50) and zone 2 is normal.
    Both cover the motion. The old loop stopped at whichever zone came first and,
    if that one rejected on its threshold, the contour was dropped — so the
    outcome depended on database ordering rather than on the zones' settings.
    """
    detector.polygon_zones = [
        zone(1, 0, 0, 640, 480, multiplier=50.0),   # rejects: threshold 5000
        zone(2, 0, 0, 640, 480, multiplier=1.0),    # accepts: threshold 100
    ]
    kept, triggered = filter_(detector, [rect_contour(0, 0, 50, 50)], min_area=100)
    assert len(kept) == 1, "a later zone must still be able to accept the motion"
    assert 2 in triggered


def test_zone_order_does_not_change_the_outcome(detector):
    """The same scene must classify identically whichever order zones arrive in."""
    a = zone(1, 0, 0, 640, 480, multiplier=50.0)
    b = zone(2, 0, 0, 640, 480, multiplier=1.0)
    contour = [rect_contour(0, 0, 50, 50)]

    detector.polygon_zones = [a, b]
    detector._zone_mask_cache = {}
    kept_ab, trig_ab = filter_(detector, contour, min_area=100)

    detector.polygon_zones = [b, a]
    detector._zone_mask_cache = {}
    kept_ba, trig_ba = filter_(detector, contour, min_area=100)

    assert len(kept_ab) == len(kept_ba) == 1
    assert set(trig_ab) == set(trig_ba)


def test_every_matching_zone_is_recorded_not_just_the_first(detector):
    """Zone statistics and 'which zones fired' must not under-count."""
    detector.polygon_zones = [
        zone(1, 0, 0, 640, 480),
        zone(2, 0, 0, 640, 480),
    ]
    _, triggered = filter_(detector, [rect_contour(10, 10, 200, 200)])
    assert set(triggered) == {1, 2}


# --- exclusion wins over inclusion ---------------------------------------

def test_exclusion_beats_an_overlapping_inclusion_zone(detector):
    """An ignored area stays ignored even where a watched area covers it."""
    detector.polygon_zones = [
        zone(1, 0, 0, 640, 480),                    # watch everything
        zone(2, 0, 0, 320, 480, exclusion=True),    # except the left half
    ]
    kept, _ = filter_(detector, [rect_contour(50, 50, 150, 150)])
    assert kept == []


# --- mask cache -----------------------------------------------------------

def test_zone_mask_cache_is_reused_for_repeat_lookups(detector):
    z = zone(1, 0, 0, 320, 240)
    detector.polygon_zones = [z]
    first = detector._zone_mask(z, FRAME_W, FRAME_H)
    second = detector._zone_mask(z, FRAME_W, FRAME_H)
    assert first is second, "identical geometry should not be rasterised twice"
