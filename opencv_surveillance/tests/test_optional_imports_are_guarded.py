# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
A package the diagnostics call optional must not be able to stop the server.

This has now been the same defect twice:

  * face_recognition_models — imported unguarded from a helper main.py calls at
    import time, so a machine without it could not start at all (fixed ec0fcb2).
  * netifaces — imported unguarded at the top of camera_discovery.py, with the
    same effect. Its last release was 2021 and its newest Windows wheel is for
    CPython 3.8, so on 3.12 pip must build it with MSVC. It is the reason the
    application could not be expected to import on Windows.

In both cases `manage.py doctor` already listed the package as optional, so the
code and the diagnostics disagreed and the diagnostics were right.

The check reads doctor's own optional list rather than a list maintained here,
so the two cannot drift: declaring something optional there and importing it
bare here is exactly the contradiction being caught.
"""

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
MANAGE = ROOT / "manage.py"


def _optional_packages() -> set:
    """
    The packages manage.py doctor reports as optional features.

    They appear as ("name", "description") pairs in its optional-feature list.
    """
    text = MANAGE.read_text()
    start = text.index("Optional features")
    window = text[start:start + 2000]
    return {m.group(1) for m in re.finditer(r'\(\s*"([a-zA-Z_][\w]*)"\s*,\s*"', window)}


def _module_level_imports(path: pathlib.Path):
    """Top-level imports only — those inside a try or a function are guarded."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return
    for node in tree.body:                      # body only: not nested in try/def
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module.split(".")[0], node.lineno


def test_doctor_declares_some_optional_packages():
    """Guard the premise: an empty list would make the check below vacuous."""
    optional = _optional_packages()
    assert len(optional) >= 4, f"only found {optional}; the parse looks broken"
    assert "netifaces" in optional
    assert "face_recognition" in optional


def test_no_optional_package_is_imported_unguarded():
    optional = _optional_packages()
    offenders = []

    for path in sorted(BACKEND.rglob("*.py")):
        for name, line in _module_level_imports(path):
            if name in optional:
                offenders.append(
                    f"{path.relative_to(ROOT)}:{line} imports '{name}' at module "
                    "level, but manage.py doctor calls it optional"
                )

    assert not offenders, (
        "optional packages imported unguarded — their absence would stop the "
        "server rather than disable a feature:\n  " + "\n  ".join(offenders)
        + "\n\nWrap the import in try/except ImportError and set an "
          "AVAILABLE flag, as camera_discovery.py and face_recognition.py do."
    )


def test_the_scanner_actually_reads_imports():
    """A scanner finding nothing would pass the test above forever."""
    total = sum(1 for p in BACKEND.rglob("*.py") for _ in _module_level_imports(p))
    assert total > 100, f"only {total} module-level imports found; the scan looks broken"


def test_discovery_still_works_without_netifaces():
    """Absence must degrade the feature, not the process."""
    from backend.core import camera_discovery

    assert hasattr(camera_discovery, "NETIFACES_AVAILABLE")
    if not camera_discovery.NETIFACES_AVAILABLE:
        assert camera_discovery.netifaces is None
