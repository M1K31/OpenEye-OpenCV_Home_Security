# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Path containment must compare path components, not string prefixes.

Audit finding M-1. Two checks in recordings.py asked

    str(full_path).startswith(str(allowed_dir))

which is true for a SIBLING directory whose name merely begins with the allowed
one. With an allowed directory of `/var/openeye/media`, the path
`/var/openeye/media-backup/secret.mp4` passes, and so does
`/var/openeye/media.old/…` — neither is inside the media directory.

Exploitability is low today: both values come from the database rather than from
the request, which is why this is defence in depth rather than an open door. It
is still the wrong test, and the cost of getting it right is one method call.

`Path.is_relative_to()` compares resolved components, so a sibling can never
satisfy it. Available since Python 3.9; the shipped runtime is 3.12.
"""

from pathlib import Path

import pytest

from backend.api.routes.recordings import is_within_directory


@pytest.fixture
def media_dir(tmp_path):
    d = tmp_path / "media"
    d.mkdir()
    return d


def test_a_file_inside_the_directory_is_allowed(media_dir):
    assert is_within_directory(media_dir / "clip.mp4", media_dir) is True


def test_a_file_in_a_nested_subdirectory_is_allowed(media_dir):
    assert is_within_directory(media_dir / "2026" / "08" / "clip.mp4", media_dir) is True


def test_the_directory_itself_is_allowed(media_dir):
    assert is_within_directory(media_dir, media_dir) is True


def test_a_sibling_directory_sharing_a_name_prefix_is_refused(tmp_path, media_dir):
    """
    The actual defect. `/media-backup` is not inside `/media`, but a string
    prefix comparison says it is.
    """
    sibling = tmp_path / "media-backup"
    sibling.mkdir()
    assert is_within_directory(sibling / "secret.mp4", media_dir) is False


def test_a_dotted_sibling_is_refused(tmp_path, media_dir):
    """`/media.old` is the same trap with different punctuation."""
    sibling = tmp_path / "media.old"
    sibling.mkdir()
    assert is_within_directory(sibling / "clip.mp4", media_dir) is False


def test_a_traversal_out_of_the_directory_is_refused(tmp_path, media_dir):
    """The case the check was written for in the first place."""
    assert is_within_directory(media_dir / ".." / "etc" / "passwd", media_dir) is False


def test_an_unrelated_absolute_path_is_refused(media_dir):
    assert is_within_directory(Path("/etc/passwd"), media_dir) is False


def test_the_old_prefix_test_would_have_accepted_the_sibling(tmp_path, media_dir):
    """
    Pins the reason this change exists.

    If someone reverts to a prefix comparison, this documents precisely what
    that reintroduces rather than leaving a future reader to wonder why
    is_relative_to was worth a helper.
    """
    sibling = tmp_path / "media-backup" / "secret.mp4"
    assert str(sibling).startswith(str(media_dir)), (
        "test premise is wrong: these paths no longer share a prefix"
    )
    assert is_within_directory(sibling, media_dir) is False
