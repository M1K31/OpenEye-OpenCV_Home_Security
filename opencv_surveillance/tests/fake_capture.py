# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
A fake capture device the capture worker can load in a spawned child process.

Lives in its own importable module rather than inside the test file because the
worker runs under the 'spawn' start method: the child is a fresh interpreter
that re-imports by name, so a fixture or monkeypatch in the parent never reaches
it. The worker resolves this module through OPENEYE_CAPTURE_FACTORY.

Behaviour is configured through the environment for the same reason — the child
inherits the environment, but not the parent's objects.
"""

import os

import numpy as np

FRAMES_ENV = "OPENEYE_FAKE_FRAMES"      # frames to deliver before `then`
THEN_ENV = "OPENEYE_FAKE_THEN"          # fail | hang | segfault
SIZE_ENV = "OPENEYE_FAKE_SIZE"          # "HxW"


class FakeCapture:
    """Delivers a set number of frames, then does what it was told."""

    def __init__(self, _source=None):
        self.remaining = int(os.getenv(FRAMES_ENV, "1000"))
        self.then = os.getenv(THEN_ENV, "fail")
        h, _, w = os.getenv(SIZE_ENV, "48x64").partition("x")
        self.h, self.w = int(h), int(w)
        self._n = 0

    def isOpened(self):
        return True

    def read(self):
        if self.remaining > 0:
            self.remaining -= 1
            self._n += 1
            return True, np.full((self.h, self.w, 3), self._n % 256, dtype=np.uint8)

        if self.then == "segfault":
            # Dereference a null pointer from Python. The closest honest stand-in
            # for the AVFoundation use-after-free: the process dies immediately
            # with SIGSEGV, no traceback, nothing catchable.
            import ctypes
            ctypes.string_at(0)

        if self.then == "hang":
            # Deliver nothing without failing — the 22:49 signature, where the
            # capture reported healthy and produced no frames for fourteen hours.
            import time
            time.sleep(3600)

        return False, None

    def release(self):
        pass

    def set(self, *_args):
        return True

    def get(self, *_args):
        return 0


def open_fake(source):
    """Factory the worker calls. Named in OPENEYE_CAPTURE_FACTORY."""
    return FakeCapture(source)
