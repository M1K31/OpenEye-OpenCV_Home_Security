# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Loading configuration without depending on how the process was launched.

Configuration currently reaches the application through the shell: `start.sh`
exports `OPENEYE_*`, `DATABASE_URL`, `SECRET_KEY`, the `CORS_*` settings and the
`ECOSYSTEM_*` settings, and `load_dotenv()` reads a `.env` found relative to the
working directory. Both of those are properties of being started from a script
in a particular directory.

A launch agent, a systemd unit, a login item or a double-clicked application
bundle has none of that. It inherits a minimal environment and an arbitrary
working directory. Under any of them the application would come up with no
signing key — logging every user out — and no ecosystem secret, which breaks peer
authentication quietly rather than visibly.

So configuration lives in a file inside the data root, where it belongs with the
rest of the installation's state, and the process environment still wins over it
so Docker and CI are unaffected.
"""

import logging
import os
import stat
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "config.env"

# Values that must never be world- or group-readable, and must survive a
# migration intact. Losing SECRET_KEY or JWT_SECRET_KEY invalidates every issued
# token; losing ECOSYSTEM_HMAC_SECRET breaks peer authentication without any
# obvious error.
SECRET_KEYS = (
    "SECRET_KEY",
    "JWT_SECRET_KEY",
    "ECOSYSTEM_HMAC_SECRET",
)


def config_file_path(data_root: Optional[Path] = None) -> Path:
    """
    Where this installation's configuration lives.

    Coerces rather than assuming a Path: a data root arrives from environment
    variables and command-line arguments as often as from Python, and a bare
    string used to fail here with an unhelpful TypeError about dividing strings.
    """
    from backend.core.paths import DATA_ROOT

    return Path(data_root or DATA_ROOT) / CONFIG_FILENAME


def _candidate_files(data_root: Optional[Path]) -> List[Path]:
    """
    Configuration sources, most authoritative first.

    The legacy `.env` beside the code is still read so an install that has not
    been migrated keeps working, but it is a fallback rather than the real
    location — and migration copies it into the data root.
    """
    from backend.core.paths import APP_ROOT

    return [config_file_path(data_root), APP_ROOT / ".env"]


def check_permissions(path: Path) -> bool:
    """
    True if `path` is not readable by anyone but its owner.

    Reported rather than enforced on load: silently changing the permissions of
    a file the user wrote is worse than telling them about it.
    """
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return True
    return not (mode & (stat.S_IRWXG | stat.S_IRWXO))


def secure_permissions(path: Path) -> None:
    """Restrict `path` to its owner. Used when *we* create the file."""
    try:
        os.chmod(path, 0o600)
    except OSError as e:
        logger.warning("Could not restrict permissions on %s: %s", path, e)


def load_configuration(data_root: Optional[Path] = None) -> List[Path]:
    """
    Load configuration files into the environment. Returns those actually read.

    The real process environment always wins: `override=False` means a value
    already set is left alone, so `docker run -e`, a systemd `Environment=`, and
    CI all keep working exactly as before. Among files, the data root's config
    wins over the legacy `.env`, because the first loader to set a name owns it.

    Note that `OPENEYE_DATA_ROOT` cannot usefully be set *inside* the config
    file, since the data root is what tells us where that file is. It has to come
    from the real environment.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - python-dotenv is a hard dependency
        logger.warning("python-dotenv not installed; skipping configuration files")
        return []

    loaded: List[Path] = []
    for candidate in _candidate_files(data_root):
        if not candidate.is_file():
            continue

        load_dotenv(candidate, override=False)
        loaded.append(candidate)

        if not check_permissions(candidate):
            has_secret = False
            try:
                content = candidate.read_text(errors="ignore")
                has_secret = any(f"{k}=" in content for k in SECRET_KEYS)
            except OSError:
                pass
            if has_secret:
                logger.warning(
                    "%s contains secrets and is readable by other users. "
                    "Restrict it with: chmod 600 %s", candidate, candidate,
                )

    if loaded:
        logger.info("Configuration loaded from: %s",
                    ", ".join(str(p) for p in loaded))
    else:
        logger.info("No configuration file found; using environment only")

    return loaded
