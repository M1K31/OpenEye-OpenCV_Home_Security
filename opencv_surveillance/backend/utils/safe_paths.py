# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Building filesystem paths out of values that came from a request.

Two rules, and they are not interchangeable.

**Reject, do not rewrite.** Silently turning "../../etc/passwd" into "passwd"
stores the file somewhere the caller did not ask for, under a name they did not
choose, and reports success. The caller cannot tell that happened, and neither
can anyone reading the logs later. Refusing is the only answer that stays true.

**Check the resolved path, not the string.** `os.path.join(base, name)` with an
absolute `name` discards `base` entirely, and `pathlib`'s `/` behaves the same
way::

    Path('/app/data/clips') / '/etc/cron.d/x'  ->  Path('/etc/cron.d/x')

A prefix comparison on the joined string is also wrong: with `/var/openeye/media`
allowed, `/var/openeye/media-backup` starts with it and is not inside it. Only
resolving both sides and asking `is_relative_to` gets this right, and resolving
is what catches a symlink pointing out of the tree.
"""

from pathlib import Path
from typing import Union

__all__ = ["UnsafePathError", "safe_component", "safe_child", "is_contained"]


class UnsafePathError(ValueError):
    """A request-supplied name would have escaped the directory it belongs in."""


def safe_component(name: str, *, what: str = "name") -> str:
    """
    Return `name` if it is a single, ordinary path component; otherwise refuse.

    Used for values that are *supposed* to be one segment — a person's name, an
    uploaded file's name. A separator or a parent reference in one of those is
    never a legitimate value, so this rejects rather than trims: the caller
    asked for something impossible and should be told.

    Note the separators are checked explicitly rather than via `os.sep`. A
    backslash is a separator on Windows and an ordinary character on POSIX, so
    a POSIX-only check would let "..\\..\\x" through on the server that stores
    the file and have it escape on the one that later reads it.
    """
    if not isinstance(name, str) or not name.strip():
        raise UnsafePathError(f"{what} must be a non-empty string")

    if "/" in name or "\\" in name:
        raise UnsafePathError(f"{what} may not contain a path separator")

    if name in (".", "..") or name.startswith(".."):
        raise UnsafePathError(f"{what} may not reference a parent directory")

    # A NUL truncates the path inside the C library underneath os.open, so a
    # name like "ok.jpg\0../../evil" can validate here and open elsewhere.
    if "\x00" in name:
        raise UnsafePathError(f"{what} may not contain a null byte")

    return name


def is_contained(candidate: Union[str, Path], allowed_dir: Union[str, Path]) -> bool:
    """True when `candidate` resolves to something inside `allowed_dir`."""
    try:
        return Path(candidate).resolve().is_relative_to(Path(allowed_dir).resolve())
    except (OSError, ValueError):
        # A path that cannot be resolved is not inside anything we allow.
        return False


def safe_child(base: Union[str, Path], name: str, *, what: str = "name") -> Path:
    """
    Resolve `name` directly inside `base`, or refuse.

    Both checks are needed and neither implies the other: `safe_component`
    rejects the obvious payloads before any filesystem call, and the
    containment test below catches what survives — most importantly a symlink
    inside `base` that points out of it, which no amount of string inspection
    can see.
    """
    safe_component(name, what=what)

    base_path = Path(base)
    candidate = base_path / name

    if not is_contained(candidate, base_path):
        raise UnsafePathError(f"{what} resolves outside the permitted directory")

    return candidate
