# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
One-time conversion of locally-stored timestamps to UTC.

Four columns were written with `datetime.now()` while every other column used
the `datetime.utcnow` default, so an existing installation holds both clocks:

    face_detection_events.detected_at      local
    motion_detection_events.detected_at    local
    recording_events.started_at            local
    recording_events.ended_at              local

Now that the writers use UTC, those columns would hold local history and UTC
new rows in the same column — worse than the original bug, because the two are
indistinguishable once mixed and no later migration could separate them.

This must run BEFORE the new code writes its first row, and exactly once. It is
not idempotent — it cannot be, since a converted value is indistinguishable from
an unconverted one — so it records completion in `system_settings` and refuses
to run twice.

Conversion uses the offset in effect at each row's own instant, via
`local_to_utc`, not today's offset. In any zone observing daylight saving those
differ by an hour for half the year, and a flat shift would corrupt that half.

Rows in a UTC-configured container are unaffected in value: local IS UTC there,
so the conversion is a no-op, which is the correct outcome.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List

from backend.core.timeutil import local_to_utc

logger = logging.getLogger(__name__)

MARKER = "timezone_migration_utc_v1"

# column -> table. Only what was demonstrably written with datetime.now().
LOCAL_COLUMNS = [
    ("face_detection_events", "detected_at"),
    ("motion_detection_events", "detected_at"),
    ("recording_events", "started_at"),
    ("recording_events", "ended_at"),
]


@dataclass
class MigrationPlan:
    dry_run: bool = True
    already_done: bool = False
    converted: Dict[str, int] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.converted.values())

    def describe(self) -> str:
        head = "would convert" if self.dry_run else "converted"
        if self.already_done:
            return "already migrated — nothing to do"
        lines = [f"{head} {self.total} timestamp(s) from local to UTC"]
        for key, n in sorted(self.converted.items()):
            lines.append(f"  {key:<44} {n}")
        lines.extend(f"  note: {n}" for n in self.notes)
        return "\n".join(lines)


def _already_migrated(db) -> bool:
    from backend.database.models import SystemSettings
    row = db.query(SystemSettings).filter(
        SystemSettings.setting_key == MARKER).first()
    return row is not None


def _mark_migrated(db) -> None:
    from backend.database.models import SystemSettings
    from backend.core.timeutil import utcnow
    db.add(SystemSettings(
        setting_key=MARKER,
        setting_value=utcnow().isoformat(),
        setting_type="string",
        description="Local timestamps converted to UTC; must not repeat"))
    db.commit()


def migrate(db, dry_run: bool = True) -> MigrationPlan:
    """
    Shift the four local columns to UTC. Runs once; a second call is a no-op.
    """
    plan = MigrationPlan(dry_run=dry_run)

    if _already_migrated(db):
        plan.already_done = True
        plan.notes.append("marker present in system_settings")
        return plan

    for table, column in LOCAL_COLUMNS:
        key = f"{table}.{column}"
        try:
            rows = db.execute(
                _select(table, column)
            ).fetchall()
        except Exception as exc:                      # table may not exist yet
            plan.notes.append(f"{key}: skipped ({exc.__class__.__name__})")
            continue

        changed = 0
        for row_id, value in rows:
            if value is None:
                continue
            parsed = _parse(value)
            if parsed is None:
                continue
            converted = local_to_utc(parsed)
            if converted == parsed:
                continue                              # UTC host: nothing to do
            if not dry_run:
                db.execute(_update(table, column),
                           {"v": converted.isoformat(sep=" "), "i": row_id})
            changed += 1

        plan.converted[key] = changed

    if not dry_run:
        db.commit()
        _mark_migrated(db)
        logger.info("Timezone migration complete: %d timestamp(s) moved to UTC",
                    plan.total)

    return plan


def _select(table: str, column: str):
    from sqlalchemy import text
    return text(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL")


def _update(table: str, column: str):
    from sqlalchemy import text
    return text(f"UPDATE {table} SET {column} = :v WHERE id = :i")


def _parse(value):
    from datetime import datetime
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value)[:26])
    except (ValueError, TypeError):
        return None
