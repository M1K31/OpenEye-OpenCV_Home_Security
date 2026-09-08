# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The Linux lock is what the Docker image installs, so it has to be right.

Until this file existed, the Dockerfile copied it with an optional glob
(`requirements.linux-py312.loc[k]`) that matched nothing, and every image build
fell through to resolving requirements.txt fresh from PyPI. Two builds of the
same commit could ship different software — the problem the lock was introduced
to end, still present for the build path most users consume.

The setuptools assertion below guards a failure that is silent, which is why it
is a test rather than a comment. pip-compile omits setuptools as build tooling
unless `--allow-unsafe` is passed; requirements.txt caps it below 82 because
face_recognition_models imports pkg_resources at module load; and
python:3.12-slim ships no setuptools at all. A lock regenerated without that
flag installs perfectly and leaves face recognition disabled, with the package
present and unable to import.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements.linux-py312.lock"
DOCKERFILE = ROOT / "Dockerfile"


def _pins() -> dict:
    pins = {}
    for line in LOCK.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9._-]+)==([^\s;]+)", line)
        if match:
            pins[match.group(1).lower().replace("_", "-")] = match.group(2)
    return pins


def test_the_lock_exists():
    """Its absence is the whole finding: the Dockerfile now requires it."""
    assert LOCK.is_file(), (
        "requirements.linux-py312.lock is missing. The Dockerfile COPYs it "
        "directly and the build will fail. Regenerate it with the "
        "'Regenerate the Linux lock' workflow."
    )


def test_every_requirement_is_pinned():
    """A lock with a range in it is not a lock."""
    unpinned = [
        line.strip() for line in LOCK.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
        and "==" not in line and not line.startswith(" ")
    ]
    assert not unpinned, f"unpinned entries in the lock: {unpinned}"


def test_setuptools_is_pinned_below_82():
    """
    The silent failure this guards.

    setuptools 82 removed pkg_resources, which face_recognition_models imports
    at module load. The base image ships no setuptools, so if the lock does not
    supply one below 82 the image installs cleanly and face recognition does not
    work.
    """
    pins = _pins()
    assert "setuptools" in pins, (
        "the lock does not pin setuptools — it was probably regenerated without "
        "--allow-unsafe. face recognition will be silently disabled in the image."
    )
    major = int(pins["setuptools"].split(".")[0])
    assert major < 82, (
        f"the lock pins setuptools {pins['setuptools']}, which removed "
        "pkg_resources; face_recognition_models cannot import"
    )


def test_the_optional_sets_are_not_in_the_lock():
    """
    dlib and face_recognition are installed separately, on purpose.

    If they reappear here, the split made in b56d4f1 has been undone and a
    Windows `pip install` is broken again.
    """
    pins = _pins()
    for package in ("dlib", "face-recognition", "face-recognition-models"):
        assert package not in pins, (
            f"{package} is in the Linux lock; it belongs in "
            "requirements-face-recognition.txt"
        )


def test_the_dockerfile_requires_the_lock():
    """
    The optional-glob COPY is what hid the missing lock for so long.

    `COPY requirements.linux-py312.loc[k] ./` matches nothing when the file is
    absent and does not fail, so the fallback ran on every build.
    """
    # Directives only. The comments deliberately mention the old glob form to
    # explain why it went, and a naive substring check flags that prose — which
    # it did on first run.
    directives = "\n".join(
        line for line in DOCKERFILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    assert "requirements.linux-py312.loc[k]" not in directives, (
        "the Dockerfile still uses the optional-glob COPY, which silently "
        "tolerates a missing lock"
    )
    assert "COPY requirements.linux-py312.lock" in directives
    assert "No lock found" not in directives, "the unpinned fallback is still present"


def test_key_pins_match_the_macos_lock():
    """
    The two locks should not disagree about the framework versions.

    They are resolved on different platforms and will differ in places, but a
    split on fastapi or starlette means the suite and the shipped software are
    testing different things — which is exactly what requirements.lock's header
    describes having happened before.
    """
    macos = ROOT / "requirements.lock"
    if not macos.is_file():
        pytest.skip("macOS lock not present")

    mac_pins = {}
    for line in macos.read_text().splitlines():
        match = re.match(r"^([A-Za-z0-9._-]+)==([^\s;]+)", line.strip())
        if match:
            mac_pins[match.group(1).lower().replace("_", "-")] = match.group(2)

    linux_pins = _pins()
    disagreements = [
        f"{name}: linux {linux_pins[name]} vs macOS {mac_pins[name]}"
        for name in ("fastapi", "starlette", "sqlalchemy", "numpy", "pyjwt")
        if name in linux_pins and name in mac_pins
        and linux_pins[name] != mac_pins[name]
    ]
    assert not disagreements, (
        "the two locks disagree on framework versions:\n" + "\n".join(disagreements)
    )
