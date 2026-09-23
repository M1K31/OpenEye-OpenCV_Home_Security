# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Opening a local camera must not leave the backend to OpenCV on Windows.

Left to itself OpenCV picks Media Foundation there, which is slow to open —
often seconds per device, and discovery probes indices in a loop, so an
eight-index scan that should take under a second can take most of a minute and
read as a hang. It also fails outright on a number of common UVC webcams that
DirectShow drives without complaint, so a camera working in every other
application appears broken here.

macOS and Linux are deliberately left on the default: on macOS it resolves to
AVFoundation and handles capture-by-index correctly, while naming
CAP_AVFOUNDATION explicitly logs "can't be used to capture by index" and falls
back anyway; on Linux the default V4L2 is already right.

There were FIVE by-index call sites. The second test is the one that matters
long-term — a fix applied to some of them is the kind that looks complete and
is not, and one of the five runs inside the capture isolation subprocess where
it is easy to miss.
"""

import ast
import pathlib
import sys

import cv2
import pytest

from backend.core import capture_backend

BACKEND = pathlib.Path(__file__).resolve().parents[1] / "backend"


def test_windows_gets_directshow(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert capture_backend.local_device_backend() == cv2.CAP_DSHOW
    assert capture_backend.backend_name() == "DirectShow"


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_posix_keeps_the_default(monkeypatch, platform):
    """
    Forcing a backend here would be a regression, not a fix.

    CAP_AVFOUNDATION cannot capture by index and falls back with a warning;
    V4L2 is already what the default selects.
    """
    monkeypatch.setattr(sys, "platform", platform)
    assert capture_backend.local_device_backend() == cv2.CAP_ANY


def test_no_call_site_opens_a_device_without_the_helper():
    """
    Every by-index open must route through open_local_device().

    Checked with the AST rather than by grepping, so the docstrings that
    describe the old `cv2.VideoCapture(index)` form are not mistaken for code —
    a substring search has already produced that false positive twice in this
    codebase.
    """
    offenders = []

    for path in sorted(BACKEND.rglob("*.py")):
        if path.name == "capture_backend.py":
            continue                                # the helper itself
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if getattr(func, "attr", None) != "VideoCapture":
                continue
            if not node.args:
                continue

            first = node.args[0]
            # A bare name or literal int is a device index. A string, an
            # attribute or a str() call is a URL or path and correctly uses
            # CAP_FFMPEG instead.
            by_index = (
                isinstance(first, ast.Constant) and isinstance(first.value, int)
            ) or (
                isinstance(first, ast.Name)
                and first.id in {"index", "device_index", "camera_index"}
            )
            if by_index and len(node.args) < 2:
                offenders.append(
                    f"{path.relative_to(BACKEND.parent)}:{node.lineno} opens a device "
                    "by index without naming a backend"
                )

    assert not offenders, (
        "these will use Media Foundation on Windows:\n  " + "\n  ".join(offenders)
        + "\n\nUse backend.core.capture_backend.open_local_device(index)."
    )


def test_the_scan_finds_the_call_sites_it_is_meant_to():
    """A scanner matching nothing would pass the test above forever."""
    total = 0
    for path in BACKEND.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        total += sum(
            1 for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "VideoCapture"
        )
    assert total >= 5, f"only {total} VideoCapture calls found; the scan looks broken"


def test_open_local_device_passes_the_backend_through(monkeypatch):
    """The helper must actually hand the backend to OpenCV, not just compute it."""
    seen = {}

    def fake(index, backend=None):
        seen["index"], seen["backend"] = index, backend
        return object()

    monkeypatch.setattr(cv2, "VideoCapture", fake)
    monkeypatch.setattr(sys, "platform", "win32")
    capture_backend.open_local_device(3)

    assert seen["index"] == 3
    assert seen["backend"] == cv2.CAP_DSHOW
