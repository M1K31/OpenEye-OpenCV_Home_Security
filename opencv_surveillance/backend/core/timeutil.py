# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
One clock for the whole application.

Timestamps were written by two different calls that look interchangeable and
are not. Every column default said `datetime.utcnow`, but the capture pipeline
passed `datetime.now()` explicitly, so an installation held both:

    face_detection_events.detected_at    local
    motion_detection_events.detected_at  local
    recording_events.started_at/ended_at local
    everything else                      UTC

Within one table: face_clusters.last_seen_at was local while trained_at beside
it was UTC. Any comparison across that boundary is wrong by the UTC offset —
four hours in New York, and silently zero in a Docker container running UTC,
which is the worst version because it means the bug cannot be reproduced where
it is most often deployed.

The rule is: **store UTC, display local**. Storage has no opinion about where
the viewer is; only rendering does. That also survives daylight saving, which
local storage does not — an hour repeats every autumn, so two distinct events
can be written with identical local timestamps and nothing can order them.

Use `utcnow()` for anything persisted or compared against something persisted.
`datetime.now()` remains correct for elapsed-time measurement inside a single
process, where the clock never leaves memory.
"""

from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """
    The current UTC time, naive.

    Naive rather than aware because the columns are naive: SQLite has no
    timezone type, and handing SQLAlchemy an aware datetime here would store
    the same digits while making every in-process comparison against a naive
    value raise TypeError. The tzinfo is attached at the API boundary instead,
    by `as_utc_iso`, which is the only place a client can see it.

    Replaces `datetime.utcnow()`, deprecated in 3.12, with the documented
    equivalent.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc_iso(value: Optional[datetime]) -> Optional[str]:
    """
    Serialise for a client, marked as UTC.

    The marker is the entire point. JavaScript parses "2026-08-19T23:44:09" as
    LOCAL time and "2026-08-19T23:44:09Z" as UTC, so an unmarked UTC timestamp
    is rendered by the browser as though it were already local and appears
    shifted by the offset. Storing UTC without saying so is worse than storing
    local, because it looks right in exactly one timezone.

    With the marker, `new Date(...).toLocaleString()` in the frontend converts
    to the viewer's own zone with no change needed at the call sites.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def local_to_utc(value: datetime) -> datetime:
    """
    Reinterpret a naive local timestamp as UTC. For migrating stored history.

    Uses the offset in effect at THAT instant, not the current one. A row from
    January carries a different offset than one from July in any zone that
    observes daylight saving, so a flat subtraction corrupts half the year.
    `astimezone()` on a naive value consults the system zone for that date,
    which is what makes this correct.
    """
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.astimezone().astimezone(timezone.utc).replace(tzinfo=None)
