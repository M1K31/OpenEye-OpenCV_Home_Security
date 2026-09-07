# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The server must start on a machine without the face-recognition models.

face_recognition, dlib and face_recognition_models are optional: every feature
that uses them is guarded by FACE_RECOGNITION_AVAILABLE, and the application is
expected to run with face recognition simply switched off.

`patch_face_recognition_models()` did not honour that. It is called
unconditionally from main.py at import time, and its `import
face_recognition_models` sat outside the try/except below it, so on a machine
without the package the very first import raised ModuleNotFoundError and the
server could not start at all.

Why this is load-bearing: neither dlib nor face_recognition publishes a cp312
Windows wheel, so `pip install` on a stock Windows machine fails on them and
takes every other package with it. The fix is to move them to an optional
requirements file — which is only safe once absence cannot crash startup. This
test is what keeps that true.
"""

import builtins
import importlib
import sys

import pytest


@pytest.fixture
def face_models_absent(monkeypatch):
    """Make `import face_recognition_models` fail, as on a machine without it."""
    monkeypatch.delitem(sys.modules, "face_recognition_models", raising=False)
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "face_recognition_models":
            raise ModuleNotFoundError("No module named 'face_recognition_models'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_patch_returns_false_instead_of_raising(face_models_absent):
    """Absence must be reported, not raised — this is the startup path."""
    from backend.core import pkg_resources_patch

    importlib.reload(pkg_resources_patch)
    assert pkg_resources_patch.patch_face_recognition_models() is False


def test_is_patch_needed_reports_false_when_absent(face_models_absent):
    from backend.core import pkg_resources_patch

    assert pkg_resources_patch.is_patch_needed() is False


def test_the_application_imports_without_the_models():
    """
    The end-to-end assertion: backend.main must import.

    This runs in whatever environment the suite is executed in. Where the
    models ARE installed it verifies the patch path still works; where they are
    not, it verifies the degraded path — which is the case that used to abort.
    """
    import backend.main  # noqa: F401
