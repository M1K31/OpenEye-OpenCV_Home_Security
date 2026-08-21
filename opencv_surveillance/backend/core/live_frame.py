# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The one way an HTTP handler obtains a camera frame.

Why this module exists
----------------------
OpenEye segfaulted twice on 2026-08-19/20 inside OpenCV's AVFoundation backend.
Both crashes were ``cv2.VideoCapture.read()`` called from a request thread
against a capture whose device had gone away. A segfault is not a Python
exception — the process is simply gone — so this cannot be handled defensively.

An audit of the fix found **seven** request-thread callers of
``camera.get_frame()``, spread across three route modules, not the one the
original crash report named. Fixing them individually would have left the eighth
to be written next month. Route handlers therefore call ``get_live_frame()``
here and nothing else, so the rule lives in one place.

The project has learned this shape before: "two writers with one rule between
them is exactly how the rename bug recurred four times."
"""

import logging

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# How old a published frame may be before it is no longer "live".
DEFAULT_MAX_AGE_SECONDS = 2.0


def get_live_frame(camera, camera_id: str, max_age: float = DEFAULT_MAX_AGE_SECONDS):
    """
    Return the camera's most recent published frame.

    Never touches the capture: the camera's own capture loop is the only thing
    that reads from the device, and it publishes what it produces.

    Raises HTTPException(503) when no frame is available or the newest one is
    stale. Reporting staleness matters as much as avoiding the crash — an
    endpoint that returns a frozen image looks identical to a working camera,
    which is what made the original fault take two days to identify.
    """
    published = camera.get_published_frame()
    if published is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Camera '{camera_id}' has not delivered a frame yet. It may be "
                "starting up, or the device may be disconnected."
            ),
        )

    frame, _motion, _seq = published

    age = camera.seconds_since_last_frame()
    if age is not None and age > max_age:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Camera '{camera_id}' last delivered a frame {int(age)}s ago. "
                "Refusing to return a stale frame as if it were live."
            ),
        )

    return frame


def try_live_frame(camera, camera_id: str, max_age: float = DEFAULT_MAX_AGE_SECONDS):
    """
    Same as get_live_frame, but returns None instead of raising.

    For callers that already have their own not-available handling and would
    otherwise have to catch the HTTPException they just asked for.
    """
    try:
        return get_live_frame(camera, camera_id, max_age)
    except HTTPException:
        return None
