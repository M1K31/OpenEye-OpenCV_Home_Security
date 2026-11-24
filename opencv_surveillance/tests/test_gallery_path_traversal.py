# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
A request-supplied name must not decide where a file is written.

Two unchecked values reached the filesystem on the photo-upload path:

  * `person_name`, a URL path parameter on six routes. Starlette decodes
    percent-escapes after matching, so "%2E%2E%2F" arrives as "../".
  * `file.filename`, taken straight from the multipart body.

Both were passed to os.path.join/pathlib against the gallery directory. Joining
an absolute path discards the base entirely, and "../.." walks out of it. The
extension filter on uploads constrains the suffix, not the prefix, so
"../../../x.jpg" satisfied it.

The `os.path.exists(person_path)` check that looked like a guard was not one:
`ensure_layout()` runs first and creates the traversed directory.

These assert refusal, not sanitisation. Rewriting "../../x.jpg" to "x.jpg"
stores a real person's photograph somewhere nobody asked for and reports
success.
"""

import pytest

from backend.utils.safe_paths import UnsafePathError, is_contained, safe_child, safe_component


ESCAPES = [
    "../evil",
    "../../etc/passwd",
    "..",
    "../",
    "/etc/cron.d/x",
    "/absolute/path.jpg",
    "sub/dir",
    "back\\slash",
    "..\\..\\windows",
    "nul\x00byte",
]


@pytest.mark.parametrize("name", ESCAPES)
def test_escaping_names_are_refused(name, tmp_path):
    with pytest.raises(UnsafePathError):
        safe_child(tmp_path, name)


@pytest.mark.parametrize("name", ["", "   ", None])
def test_empty_names_are_refused(name):
    with pytest.raises(UnsafePathError):
        safe_component(name)


@pytest.mark.parametrize("name", [
    "alice.jpg", "Alice Smith.jpg", "photo_2026-01-01.png",
    "ünïcode.jpg", "with spaces and-dashes.jpeg", "Jean-Luc O'Brien",
])
def test_ordinary_names_are_allowed(name, tmp_path):
    """The guard must not reject legitimate names — people have real names."""
    result = safe_child(tmp_path, name)
    assert result.parent == tmp_path
    assert result.name == name


def test_a_symlink_pointing_out_of_the_tree_is_refused(tmp_path):
    """
    The check that string inspection cannot make.

    A component with no separator in it can still resolve outside the gallery
    if it is a symlink, which is why containment is tested after resolution.
    """
    outside = tmp_path.parent / "outside_target"
    outside.mkdir(exist_ok=True)
    base = tmp_path / "gallery"
    base.mkdir()
    (base / "sneaky").symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafePathError):
        safe_child(base, "sneaky")


def test_is_contained_rejects_a_sibling_with_a_shared_prefix(tmp_path):
    """
    `/var/media-backup` starts with `/var/media` and is not inside it.

    A prefix comparison on the joined string gets this wrong; resolving and
    asking is_relative_to does not.
    """
    allowed = tmp_path / "media"
    allowed.mkdir()
    sibling = tmp_path / "media-backup"
    sibling.mkdir()
    assert is_contained(allowed / "file.jpg", allowed) is True
    assert is_contained(sibling / "file.jpg", allowed) is False


class TestGalleryChokepoint:
    """person_dir is where every caller converges, so it is where this is enforced."""

    @pytest.mark.parametrize("name", ["../escape", "../../etc", "/absolute"])
    def test_person_dir_refuses_a_traversing_name(self, name):
        from backend.core import gallery

        with pytest.raises(UnsafePathError):
            gallery.person_dir(name)

    def test_person_dir_still_builds_an_ordinary_path(self):
        from backend.core import gallery
        from backend.core.paths import paths

        result = gallery.person_dir("Alice Smith")
        assert result.parent == paths.faces_dir
        assert result.name == "Alice Smith"

    def test_ensure_layout_cannot_create_a_traversed_directory(self):
        """
        The specific bug: ensure_layout() ran before the existence check and
        created whatever directory the name described.
        """
        from backend.core import gallery

        with pytest.raises(UnsafePathError):
            gallery.ensure_layout("../../../tmp/created-by-traversal")
