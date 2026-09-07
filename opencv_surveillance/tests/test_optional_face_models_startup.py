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


class TestTheDependencySplit:
    """
    requirements.txt must agree with the rest of the project about optionality.

    feature_config.py excludes face recognition from HardwareTier.MINIMAL,
    FACE_RECOGNITION_AVAILABLE guards every call site, ENABLE_FACE_RECOGNITION
    gates the feature, and requirements-pi.txt ships dlib commented out. Only
    requirements.txt disagreed, and it did so by accident: commit 0c804a6
    resolved a merge that had been committed with conflict markers in the file
    and kept the "required" side.
    """

    @staticmethod
    def _requirements(name):
        import pathlib

        path = pathlib.Path(__file__).resolve().parents[1] / name
        assert path.exists(), f"{name} is missing"
        return [
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def test_the_base_set_does_not_require_dlib(self):
        """
        dlib has no cp312 Windows wheel; requiring it fails the whole install.

        A source build also costs hours on ARM, for a feature MINIMAL-tier
        hardware never enables.
        """
        base = self._requirements("requirements.txt")
        offenders = [r for r in base if r.lower().startswith(("dlib", "face_recognition", "face-recognition"))]
        assert not offenders, (
            f"requirements.txt requires {offenders}; these belong in "
            "requirements-face-recognition.txt"
        )

    def test_the_optional_set_exists_and_declares_them(self):
        """Making it optional is only safe if there is a documented way back in."""
        optional = self._requirements("requirements-face-recognition.txt")
        joined = " ".join(optional).lower()
        assert "dlib" in joined
        assert "face_recognition" in joined or "face-recognition" in joined

    def test_the_pi_set_still_excludes_them(self):
        """requirements-pi.txt was right all along; it must stay that way."""
        pi = self._requirements("requirements-pi.txt")
        offenders = [r for r in pi if r.lower().startswith(("dlib", "face_recognition"))]
        assert not offenders, f"requirements-pi.txt requires {offenders}"

    def test_the_feature_is_still_excluded_from_minimal_hardware(self):
        """The premise of the split: MINIMAL never enables face recognition."""
        from backend.core.feature_config import HardwareTier, get_features_for_hardware_tier

        minimal = get_features_for_hardware_tier(HardwareTier.MINIMAL)
        assert not [f for f in minimal if "face" in f], (
            "MINIMAL now includes face recognition; the dependency split needs revisiting"
        )
