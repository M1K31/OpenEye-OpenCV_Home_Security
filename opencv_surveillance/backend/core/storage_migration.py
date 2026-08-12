# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Bringing an installation's data under one root, in either direction.

Installs created before the data root existed have their media wherever the old
path resolution happened to put it — some beside the code, some at whatever the
environment named — which is how one machine ended up with its database, faces
and recordings under the application directory and 16 GB of snapshots somewhere
else entirely.

This module moves all of it under the data root, and moves it back out again.
Both directions matter: an application bundle has to be able to hand an
installation back to a source install, so migration is an explicit operation
rather than a one-way thing that happens on first run.

Two rules shape everything here:

- **Never delete before verifying.** A move across filesystems copies, checks
  what arrived, and only then removes the source.
- **Refuse rather than half-finish.** Every check happens before the first byte
  moves, and a failure leaves the installation exactly as it was.
"""

import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MARKER_FILENAME = ".migration-state.json"
MARKER_VERSION = 1

# Media directories, by the attribute PathManager exposes them as. The value is
# where each belongs relative to the data root.
MEDIA_LAYOUT: Dict[str, str] = {
    "faces_dir": "faces",
    "recordings_dir": "recordings",
    "snapshots_dir": "data/snapshots",
    "thumbnails_dir": "data/thumbnails",
}

# SQLite writes two sidecar files; moving the database without them loses any
# not-yet-checkpointed transactions.
DATABASE_SUFFIXES = ("", "-wal", "-shm")

# Distinguishes "work out which database is in use" from "there is no database
# to move". Passing None had meant both, so a caller that explicitly said "no
# database" silently got the live one instead.
AUTODETECT = object()


@dataclass
class MoveItem:
    """One directory or file to relocate."""

    label: str
    source: Path
    destination: Path
    file_count: int = 0
    total_bytes: int = 0
    same_filesystem: bool = True

    @property
    def needs_free_space(self) -> int:
        """A rename costs nothing; a copy needs room for a second copy."""
        return 0 if self.same_filesystem else self.total_bytes


@dataclass
class MigrationPlan:
    data_root: Path
    items: List[MoveItem] = field(default_factory=list)
    config_source: Optional[Path] = None
    problems: List[str] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        return not self.items and self.config_source is None

    @property
    def total_bytes(self) -> int:
        return sum(i.total_bytes for i in self.items)

    @property
    def total_files(self) -> int:
        return sum(i.file_count for i in self.items)

    def describe(self) -> str:
        if self.is_noop:
            return "Nothing to migrate; storage is already under the data root."
        lines = [f"Migrating into {self.data_root}:"]
        for item in self.items:
            how = "rename" if item.same_filesystem else "copy + verify + delete"
            lines.append(
                f"  {item.label}: {item.source} -> {item.destination} "
                f"({item.file_count} files, {_human(item.total_bytes)}, {how})"
            )
        if self.config_source:
            lines.append(f"  config: {self.config_source} -> "
                         f"{self.data_root / 'config.env'}")
        return "\n".join(lines)


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _tree_stats(path: Path) -> Tuple[int, int]:
    """(file count, total bytes) for a directory tree."""
    count = total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
                count += 1
            except OSError:
                count += 1
    return count, total


def _nearest_existing(path: Path) -> Path:
    """The closest ancestor that exists, for asking which filesystem it is on."""
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _same_filesystem(source: Path, destination: Path) -> bool:
    """
    True when a rename would work, meaning the move is instant and atomic.

    Worth knowing before starting: 22 GB moved by rename takes no time and no
    extra space, while the same 22 GB copied needs both.
    """
    try:
        return os.stat(source).st_dev == os.stat(_nearest_existing(destination)).st_dev
    except OSError:
        return False


def _has_content(path: Path) -> bool:
    try:
        return path.is_dir() and any(path.iterdir())
    except OSError:
        return False


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def marker_path(data_root: Path) -> Path:
    return data_root / MARKER_FILENAME


def read_marker(data_root: Path) -> Optional[dict]:
    try:
        return json.loads(marker_path(data_root).read_text())
    except (OSError, ValueError):
        return None


def write_marker(data_root: Path, plan: MigrationPlan, status: str = "complete") -> None:
    payload = {
        "version": MARKER_VERSION,
        "status": status,
        "completed_at": datetime.utcnow().isoformat(),
        "moved": [
            {"label": i.label, "from": str(i.source), "to": str(i.destination),
             "files": i.file_count, "bytes": i.total_bytes}
            for i in plan.items
        ],
    }
    try:
        data_root.mkdir(parents=True, exist_ok=True)
        marker_path(data_root).write_text(json.dumps(payload, indent=2))
    except OSError as e:
        logger.warning("Could not write migration marker: %s", e)


def build_plan(
    data_root: Optional[Path] = None,
    current_paths: Optional[object] = None,
    app_root: Optional[Path] = None,
    database_path=AUTODETECT,
) -> MigrationPlan:
    """
    Work out what is not yet under the data root.

    Considers both where the application is *currently* reading from and the
    pre-data-root locations beside the code, because those are not the same
    place. On the install that motivated this, the database and galleries were
    beside the code while the snapshots were at the location the environment
    named — so looking at only one of the two would have missed most of the data.
    """
    from backend.core.paths import APP_ROOT, DATA_ROOT, paths as default_paths

    data_root = Path(data_root or DATA_ROOT)
    app_root = Path(app_root or APP_ROOT)
    current = current_paths if current_paths is not None else default_paths

    plan = MigrationPlan(data_root=data_root)

    if data_root == app_root:
        # A source checkout: data already lives beside the code by design.
        return plan

    for attribute, relative in MEDIA_LAYOUT.items():
        destination = data_root / relative

        candidates = []
        configured = getattr(current, attribute, None)
        if configured:
            candidates.append(Path(configured))
        candidates.append(app_root / relative)

        # Consider every candidate rather than stopping at the first populated
        # one. The configuration can name a near-empty directory while the real
        # media sits elsewhere: on the install this was built for, the faces
        # setting pointed at a stub holding a single stale file while the actual
        # gallery of 23,943 images was beside the code. Taking the first hit
        # would have migrated the stub and left the gallery behind.
        populated = []
        seen = set()
        for source in candidates:
            source = Path(os.path.normpath(str(source)))
            if source in seen:
                continue
            seen.add(source)

            if source == destination or _is_within(source, data_root):
                continue
            if not _has_content(source):
                continue

            count, size = _tree_stats(source)
            populated.append((count, size, source))

        if not populated:
            continue

        # Richest wins, so a stub can never displace the real thing.
        populated.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
        count, size, source = populated[0]

        label = attribute.replace("_dir", "")
        plan.items.append(MoveItem(
            label=label,
            source=source,
            destination=destination,
            file_count=count,
            total_bytes=size,
            same_filesystem=_same_filesystem(source, destination),
        ))

        # More than one populated location means data would be left behind
        # wherever we did not look. That is the failure this module exists to
        # prevent, so it is reported rather than resolved by guesswork.
        for other_count, _other_size, other in populated[1:]:
            plan.problems.append(
                f"{label}: found data in more than one place. Migrating "
                f"{source} ({count} files) but {other} still holds "
                f"{other_count} file(s). Move or remove it, then run again."
            )

    # The database, with its sidecar files. Omitting the argument means "find
    # the one in use"; passing None explicitly means "there is none to move".
    if database_path is AUTODETECT:
        db_source = _current_database_path()
    else:
        db_source = Path(database_path) if database_path else None
    if db_source and db_source.exists() and not _is_within(db_source, data_root):
        for suffix in DATABASE_SUFFIXES:
            candidate = Path(str(db_source) + suffix)
            if not candidate.exists():
                continue
            plan.items.append(MoveItem(
                label=f"database{suffix or ''}",
                source=candidate,
                destination=data_root / candidate.name,
                file_count=1,
                total_bytes=candidate.stat().st_size,
                same_filesystem=_same_filesystem(candidate, data_root),
            ))

    legacy_config = app_root / ".env"
    if legacy_config.is_file() and not (data_root / "config.env").exists():
        plan.config_source = legacy_config

    return plan


def _current_database_path() -> Optional[Path]:
    try:
        from backend.database.session import SQLALCHEMY_DATABASE_URL

        if not SQLALCHEMY_DATABASE_URL.startswith("sqlite:"):
            return None  # A server database is not ours to move.
        _prefix, _, raw = SQLALCHEMY_DATABASE_URL.partition("///")
        return Path(raw) if raw else None
    except Exception:  # pragma: no cover - defensive
        return None


def preflight(plan: MigrationPlan) -> List[str]:
    """
    Everything that must be true before the first byte moves.

    Returned rather than raised so a caller can show the whole list at once
    instead of one problem per attempt.
    """
    problems: List[str] = list(plan.problems)

    if plan.is_noop:
        return problems

    for item in plan.items:
        if not item.source.exists():
            problems.append(f"{item.label}: source no longer exists ({item.source})")
            continue
        if item.destination.exists() and _has_content(item.destination):
            problems.append(
                f"{item.label}: destination already holds data ({item.destination}). "
                "Refusing to merge two sets of files."
            )
        if item.destination.is_file():
            problems.append(f"{item.label}: destination is a file ({item.destination})")

    needed = sum(i.needs_free_space for i in plan.items)
    if needed:
        try:
            free = shutil.disk_usage(_nearest_existing(plan.data_root)).free
            # A margin, because filling the disk exactly is its own failure.
            if free < needed * 1.1:
                problems.append(
                    f"Not enough free space: {_human(needed)} needed "
                    f"(plus margin), {_human(free)} available"
                )
        except OSError as e:
            problems.append(f"Could not check free space: {e}")

    return problems


def _move_tree(item: MoveItem) -> None:
    """
    Relocate one item, verifying before anything is removed.

    A same-filesystem rename is atomic and needs no verification. A cross-device
    move is a copy, a comparison of what arrived, and only then a delete — if the
    counts or sizes disagree, the source is left untouched and the caller is told.
    """
    item.destination.parent.mkdir(parents=True, exist_ok=True)

    if item.same_filesystem:
        os.rename(item.source, item.destination)
        return

    if item.source.is_dir():
        shutil.copytree(item.source, item.destination, dirs_exist_ok=True)
        count, size = _tree_stats(item.destination)
        if count != item.file_count or size != item.total_bytes:
            raise RuntimeError(
                f"{item.label}: copy verification failed "
                f"(expected {item.file_count} files / {item.total_bytes} bytes, "
                f"found {count} / {size}). Source left in place."
            )
        shutil.rmtree(item.source)
    else:
        shutil.copy2(item.source, item.destination)
        if item.destination.stat().st_size != item.total_bytes:
            raise RuntimeError(
                f"{item.label}: copy verification failed. Source left in place."
            )
        item.source.unlink()


# Configuration keys that name a storage location. After a migration these all
# point at directories that no longer exist.
_STORAGE_KEYS = (
    "OPENEYE_DATA_DIR",
    "OPENEYE_RECORDINGS_DIR",
    "OPENEYE_SNAPSHOTS_DIR",
    "OPENEYE_THUMBNAILS_DIR",
    "OPENEYE_FACES_DIR",
    "DATABASE_URL",
)


def _retire_storage_keys(text: str, data_root: Path) -> Tuple[str, List[str]]:
    """
    Comment out settings that name a storage location, returning the new text.

    Commented rather than deleted: the original intent stays visible and the
    change is trivially reversible, while the values stop taking effect.
    """
    output, retired = [], []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in _STORAGE_KEYS:
                retired.append(key)
                output.append(
                    f"# Retired by the storage migration on "
                    f"{datetime.utcnow().date()}: this named a location that no "
                    f"longer holds data. Paths now resolve under {data_root}."
                )
                output.append(f"# {line}")
                continue
        output.append(line)

    return "\n".join(output) + "\n", retired


def _write_migrated_config(plan: MigrationPlan, destination: Path) -> None:
    """
    Copy the configuration, retiring the settings that named the old locations.

    Copying it verbatim would be worse than not copying it at all: every
    OPENEYE_*_DIR and DATABASE_URL in it points at a directory this migration
    just emptied, and those values take precedence over the data root. The
    application would come up configured to look exactly where its data is not.

    The legacy file is retired in place as well, and that half matters more than
    it looks. The start script sources it and exports the result, and the process
    environment outranks the config file — so leaving the original intact would
    have meant the retired settings won anyway, and the migration would appear to
    have lost every gallery and recording the moment the service restarted.
    """
    source_text = plan.config_source.read_text()

    migrated, retired = _retire_storage_keys(source_text, plan.data_root)
    destination.write_text(migrated)

    if retired:
        logger.info("Retired stale storage settings in config: %s",
                    ", ".join(retired))
        try:
            legacy_text, _ = _retire_storage_keys(source_text, plan.data_root)
            plan.config_source.write_text(legacy_text)
            logger.info("Retired the same settings in %s, which the start "
                        "script exports into the environment.",
                        plan.config_source)
        except OSError as e:
            logger.error(
                "Could not retire storage settings in %s: %s. That file is "
                "exported by the start script and will override the data root — "
                "comment out %s by hand before starting the service.",
                plan.config_source, e, ", ".join(retired),
            )


def migrate(plan: Optional[MigrationPlan] = None, dry_run: bool = False) -> dict:
    """
    Execute a plan. Returns a summary; raises only if the caller must intervene.
    """
    from backend.core.config_loader import secure_permissions

    plan = plan if plan is not None else build_plan()

    if plan.is_noop:
        return {"migrated": False, "reason": "nothing to migrate", "items": []}

    problems = preflight(plan)
    if problems:
        for problem in problems:
            logger.error("Migration blocked: %s", problem)
        return {"migrated": False, "reason": "preflight failed", "problems": problems}

    logger.info("%s", plan.describe())
    if dry_run:
        return {"migrated": False, "reason": "dry run",
                "items": [i.label for i in plan.items],
                "plan": plan.describe()}

    plan.data_root.mkdir(parents=True, exist_ok=True)
    write_marker(plan.data_root, plan, status="in-progress")

    moved: List[str] = []
    for item in plan.items:
        logger.info("Moving %s (%s files, %s)...",
                    item.label, item.file_count, _human(item.total_bytes))
        _move_tree(item)
        moved.append(item.label)

    if plan.config_source:
        destination = plan.data_root / "config.env"
        _write_migrated_config(plan, destination)
        # Secrets: readable by the owner only, wherever they came from.
        secure_permissions(destination)
        moved.append("config")

    write_marker(plan.data_root, plan, status="complete")
    logger.info("Migration complete: %s", ", ".join(moved))

    return {"migrated": True, "items": moved,
            "files": plan.total_files, "bytes": plan.total_bytes}


# --------------------------------------------------------------------------
# The two-way door
# --------------------------------------------------------------------------

def export_data(destination: Path, data_root: Optional[Path] = None) -> dict:
    """
    Copy an installation's data into a portable directory.

    Copies rather than moves: an export is a thing you take somewhere, not a
    thing that empties the place you took it from. That also makes it usable as
    the backup taken before a local install's files are retired.
    """
    from backend.core.paths import DATA_ROOT

    source_root = Path(data_root or DATA_ROOT)
    destination = Path(destination)

    if _is_within(destination, source_root):
        raise ValueError(
            f"Refusing to export into {destination}: it is inside the data root "
            "being exported, which would copy the export into itself."
        )

    destination.mkdir(parents=True, exist_ok=True)
    copied = []

    for relative in list(MEDIA_LAYOUT.values()) + ["logs"]:
        source = source_root / relative
        if not _has_content(source):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, dirs_exist_ok=True)
        copied.append(relative)

    for name in ("surveillance.db", "surveillance.db-wal", "surveillance.db-shm",
                 "config.env"):
        source = source_root / name
        if source.is_file():
            shutil.copy2(source, destination / name)
            copied.append(name)

    if (destination / "config.env").is_file():
        from backend.core.config_loader import secure_permissions

        secure_permissions(destination / "config.env")

    logger.info("Exported %s to %s", ", ".join(copied) or "nothing", destination)
    return {"exported": copied, "destination": str(destination)}


def import_data(source: Path, data_root: Optional[Path] = None,
                overwrite: bool = False) -> dict:
    """
    Adopt a previously exported directory as this installation's data.

    The reverse of export_data, and the return path from an application bundle
    to a source install. Refuses to overwrite populated directories unless asked,
    because merging two installations' media is not something to do by accident.
    """
    from backend.core.paths import DATA_ROOT

    source = Path(source)
    target_root = Path(data_root or DATA_ROOT)

    if not source.is_dir():
        raise ValueError(f"No such export directory: {source}")

    conflicts = [
        relative for relative in list(MEDIA_LAYOUT.values()) + ["logs"]
        if _has_content(source / relative) and _has_content(target_root / relative)
    ]
    if conflicts and not overwrite:
        raise ValueError(
            "Refusing to import over existing data: "
            + ", ".join(conflicts)
            + ". Pass overwrite=True to replace it."
        )

    target_root.mkdir(parents=True, exist_ok=True)
    imported = []

    for relative in list(MEDIA_LAYOUT.values()) + ["logs"]:
        incoming = source / relative
        if not _has_content(incoming):
            continue
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(incoming, target, dirs_exist_ok=True)
        imported.append(relative)

    for name in ("surveillance.db", "surveillance.db-wal", "surveillance.db-shm",
                 "config.env"):
        incoming = source / name
        if incoming.is_file():
            shutil.copy2(incoming, target_root / name)
            imported.append(name)

    if (target_root / "config.env").is_file():
        from backend.core.config_loader import secure_permissions

        secure_permissions(target_root / "config.env")

    logger.info("Imported %s from %s", ", ".join(imported) or "nothing", source)
    return {"imported": imported, "data_root": str(target_root)}


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    """
    Run storage operations from a shell.

    Deliberately a command rather than something that happens on first launch.
    Moving tens of gigabytes is not a side effect a user should discover after
    the fact, and an explicit invocation is what makes the reverse direction —
    handing an installation back to a source install — a supported thing rather
    than an emergency.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m backend.core.storage_migration",
        description="Move OpenEye's data under the data root, or back out again.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    plan_cmd = sub.add_parser("plan", help="show what would move, and change nothing")
    run_cmd = sub.add_parser("migrate", help="move storage under the data root")
    run_cmd.add_argument("--yes", action="store_true",
                         help="skip the confirmation prompt")
    exp = sub.add_parser("export", help="copy the data root to a portable directory")
    exp.add_argument("destination")
    imp = sub.add_parser("import", help="adopt a previously exported directory")
    imp.add_argument("source")
    imp.add_argument("--overwrite", action="store_true",
                     help="replace populated directories")

    for p in (plan_cmd, run_cmd, exp, imp):
        p.add_argument("--data-root", default=None,
                       help="override the data root (default: this install's)")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data_root = Path(args.data_root) if args.data_root else None

    if args.command == "plan":
        plan = build_plan(data_root=data_root)
        print(plan.describe())
        problems = preflight(plan)
        if problems:
            # Showing these here rather than only on the real run is the point
            # of a dry run: the user finds out what blocks them before they have
            # stopped the service.
            print("\nBlocking problems:")
            for problem in problems:
                print(f"  - {problem}")
        return 0

    if args.command == "migrate":
        plan = build_plan(data_root=data_root)
        print(plan.describe())
        if plan.is_noop:
            return 0

        problems = preflight(plan)
        if problems:
            print("\nCannot proceed:")
            for problem in problems:
                print(f"  - {problem}")
            return 1

        if not args.yes:
            print(f"\nThis moves {plan.total_files} files ({_human(plan.total_bytes)}). "
                  "Stop the OpenEye service first.")
            if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
                print("Aborted; nothing was moved.")
                return 1

        result = migrate(plan)
        print(f"\n{result}")
        return 0 if result.get("migrated") else 1

    if args.command == "export":
        print(export_data(Path(args.destination), data_root=data_root))
        return 0

    if args.command == "import":
        print(import_data(Path(args.source), data_root=data_root,
                          overwrite=args.overwrite))
        return 0

    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
