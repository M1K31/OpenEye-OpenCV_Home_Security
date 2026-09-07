# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The clip exporter must not write outside the clips directory.

`output_name` arrived as an unvalidated Optional[str] in the request body and
was joined onto the clips directory with pathlib's "/", which does not
sanitise. Two payload shapes escaped:

    clips_dir / "../../data/openeye.db"   walks out of the directory
    clips_dir / "/etc/cron.d/x"           discards clips_dir entirely

ffmpeg was then invoked with -y, so it overwrote whatever was at the resulting
path without asking. The route requires only get_current_active_user, which
does not check role — the lowest-privilege account could reach it.

The equivalence below is the whole finding in one line, and is why a string
check on the joined result is not enough.
"""

from pathlib import Path

import pytest

from backend.utils.safe_paths import UnsafePathError, safe_child


def test_an_absolute_name_would_have_discarded_the_base():
    """Pin the pathlib behaviour the vulnerability depended on."""
    assert Path("/app/data/clips") / "/etc/cron.d/x" == Path("/etc/cron.d/x")


@pytest.mark.parametrize("payload", [
    "../../data/openeye.db",
    "../../../etc/cron.d/x",
    "/etc/cron.d/x",
    "/app/data/secret.key",
    "C:/Windows/Temp/x.mp4",
    "..\\..\\windows\\x.mp4",
    "sub/dir/clip.mp4",
])
def test_escaping_output_names_are_refused(payload, tmp_path):
    with pytest.raises(UnsafePathError):
        safe_child(tmp_path, payload, what="output_name")


@pytest.mark.parametrize("name", [
    "clip.mp4", "my export 2026-01-01.mp4", "front-door_incident.mp4",
])
def test_ordinary_output_names_still_work(name, tmp_path):
    """Refusing traversal must not break naming an export."""
    result = safe_child(tmp_path, name, what="output_name")
    assert result.parent == tmp_path
    assert result.name == name


def test_the_error_names_the_field():
    """A 400 that does not say which field was wrong is not actionable."""
    with pytest.raises(UnsafePathError, match="output_name"):
        safe_child(Path("/tmp"), "../x.mp4", what="output_name")


def test_ffmpeg_stderr_is_not_returned_to_the_client():
    """
    The failure message must not carry ffmpeg's stderr.

    It contains absolute server paths and reveals the filesystem layout, which
    does not belong in an API response. Asserted against the source because
    reaching the branch needs a real ffmpeg failure.
    """
    source = Path(__file__).resolve().parents[1] / "backend/api/routes/timeline.py"
    text = source.read_text()
    assert 'message=f"FFmpeg error: {result.stderr}"' not in text
    assert "See the server log for details" in text
