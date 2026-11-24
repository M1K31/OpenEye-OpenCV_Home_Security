# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Which OpenCV capture API to open a local camera with.

Left to itself, OpenCV picks a backend per platform. That choice is right on
macOS and Linux and wrong on Windows, where it selects Media Foundation (MSMF):

  * MSMF is slow to open — often seconds per device. Discovery probes indices in
    a loop, so the cost multiplies: an eight-index scan that should take under a
    second can take most of a minute, which reads as a hang.
  * It fails outright on a number of common UVC webcams that DirectShow drives
    without complaint, so a camera that works in every other application appears
    broken here.

DirectShow is the older API and the one that works. It is what OBS, Zoom and
most capture software use on Windows for exactly these reasons.

macOS and Linux are deliberately left on the default. On macOS the default
resolves to AVFoundation and handles capture-by-index correctly, whereas naming
CAP_AVFOUNDATION explicitly logs "can't be used to capture by index" and falls
back here anyway. On Linux the default V4L2 is already correct. Only Windows is
steered.

This applies to opening a device BY INDEX. A network stream opened by URL uses
CAP_FFMPEG and is unaffected — a separate decision, made at those call sites.
"""

import sys

import cv2

__all__ = ["local_device_backend", "open_local_device", "backend_name"]


def local_device_backend() -> int:
    """The cv2 capture API to use when opening a camera by index."""
    if sys.platform == "win32":
        return cv2.CAP_DSHOW
    return cv2.CAP_ANY


def backend_name() -> str:
    """Human-readable name for logs and diagnostics."""
    return "DirectShow" if sys.platform == "win32" else "platform default"


def open_local_device(index: int) -> "cv2.VideoCapture":
    """
    Open a local camera by index using the right backend for this platform.

    A single function rather than a constant passed around, so that a future
    platform quirk has one place to live and every call site inherits it. There
    were five of these before it existed, and a fix applied to some of them is
    the kind that looks done and is not.
    """
    return cv2.VideoCapture(index, local_device_backend())
