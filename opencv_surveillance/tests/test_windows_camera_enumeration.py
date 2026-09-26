# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Windows must be able to say which cameras are attached.

`_enumerate_platform_cameras()` branched on Darwin and Linux and fell through to
`[]` for everything else. On Windows that meant discovery reported "no cameras"
whether one was attached or not — and, worse, could not tell that apart from a
device it had been refused access to. Distinguishing those two is the stated
reason the method exists at all:

    "The OS will list a device even when it refuses to let this process open
     it, which is what lets discovery tell 'nothing plugged in' apart from
     'access denied'."

Tested by faking the PowerShell output rather than by running it, since this
suite runs on Linux. What is being checked is the parsing and the contract —
that a name list becomes the {"name", "index"} shape the callers expect, that
duplicates across the two device classes collapse, and that an empty or failed
call degrades to [] instead of raising.
"""

import platform
import subprocess
from types import SimpleNamespace

import pytest

from backend.core.camera_discovery import discovery_service


def _fake_powershell(stdout, returncode=0):
    def run(cmd, *args, **kwargs):
        assert cmd[0] == "powershell", f"expected powershell, got {cmd[0]!r}"
        assert "-NonInteractive" in cmd, (
            "must be non-interactive; a background service cannot answer a prompt"
        )
        assert "-NoProfile" in cmd, "a user profile should not affect enumeration"
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)
    return run


def test_windows_cameras_are_listed(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_powershell(
        "Integrated Webcam\r\nLogitech StreamCam\r\n"))

    cameras = discovery_service._list_windows_cameras()

    assert cameras == [
        {"name": "Integrated Webcam", "index": 0},
        {"name": "Logitech StreamCam", "index": 1},
    ]


def test_a_device_in_both_classes_is_listed_once(monkeypatch):
    """
    Camera and Image are queried together, and can report the same device.

    Some UVC webcams still enumerate under Image on Windows 10, which is why
    both are asked for — but a duplicate would shift every later index by one
    and mislabel the cameras after it.
    """
    monkeypatch.setattr(subprocess, "run", _fake_powershell(
        "Integrated Webcam\r\nIntegrated Webcam\r\nBrio 500\r\n"))

    cameras = discovery_service._list_windows_cameras()

    assert [c["name"] for c in cameras] == ["Integrated Webcam", "Brio 500"]
    assert [c["index"] for c in cameras] == [0, 1]


def test_blank_lines_do_not_become_cameras(monkeypatch):
    """PowerShell pads its output; a blank line is not a device."""
    monkeypatch.setattr(subprocess, "run", _fake_powershell(
        "\r\n\r\nIntegrated Webcam\r\n   \r\n"))

    assert discovery_service._list_windows_cameras() == [
        {"name": "Integrated Webcam", "index": 0}]


def test_no_cameras_returns_empty_not_an_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_powershell(""))
    assert discovery_service._list_windows_cameras() == []


def test_the_branch_is_reachable_on_windows(monkeypatch):
    """
    The implementation is useless if the dispatcher never calls it.

    This is the actual defect being fixed: the method could exist and Windows
    would still fall through to [].
    """
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        discovery_service, "_list_windows_cameras",
        lambda: [{"name": "sentinel", "index": 0}])

    assert discovery_service._enumerate_platform_cameras() == [
        {"name": "sentinel", "index": 0}]


def test_a_failing_powershell_does_not_raise(monkeypatch):
    """
    Enumeration is a diagnostic aid, not a critical path.

    The caller's try/except already treats failure as "unavailable"; this
    confirms the behaviour rather than assuming it.
    """
    def explode(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="powershell", timeout=20)

    monkeypatch.setattr(subprocess, "run", explode)
    monkeypatch.setattr(platform, "system", lambda: "Windows")

    assert discovery_service._enumerate_platform_cameras() == []


def test_windows_gets_a_permission_hint(monkeypatch):
    """
    The generic fallback was unhelpful on the platform that needs it most.

    Windows has a second, separate switch for desktop applications, and it is
    the one that blocks a Python process while the main toggle looks enabled.
    """
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    hint = discovery_service._permission_hint()

    assert "Windows" in hint
    assert "desktop apps" in hint, "the separate desktop-app switch must be named"
