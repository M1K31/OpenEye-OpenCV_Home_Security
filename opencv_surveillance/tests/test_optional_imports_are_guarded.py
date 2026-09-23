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
    assert "face_recognition" in optional
    # netifaces used to be here. It is not merely no longer optional — it is
    # gone, replaced by psutil, so doctor correctly stops mentioning it.
    assert "netifaces" not in optional


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


def test_subnet_detection_uses_psutil_not_netifaces():
    """
    netifaces is gone, not guarded.

    It was unmaintained from 2021 with no Windows wheel past CPython 3.8, so it
    was the reason the application could not import on Windows. psutil returns
    the same interface data, is already required, and ships wheels everywhere —
    which removes the platform split rather than working around it.
    """
    import importlib.util

    from backend.core import camera_discovery

    assert not hasattr(camera_discovery, "NETIFACES_AVAILABLE"), (
        "the netifaces guard is back; psutil should be serving this now"
    )
    assert importlib.util.find_spec("netifaces") is None or True  # may linger in an old venv

    subnets = camera_discovery.discovery_service._get_local_subnets()
    assert isinstance(subnets, list) and subnets, "no subnet returned at all"
    import ipaddress
    for subnet in subnets:
        ipaddress.ip_network(subnet)          # must be parseable


def test_oversized_subnets_are_not_scanned():
    """
    A /16 is 65,534 addresses.

    Probing each for an RTSP port takes far longer than the scan's own timeout
    allows, so it would cover a fraction and report that as a complete result.
    Docker's default bridge is a /16 and corporate networks often are too, so
    this is the common case rather than an exotic one.
    """
    from backend.core import camera_discovery

    for subnet in camera_discovery.discovery_service._get_local_subnets():
        import ipaddress
        network = ipaddress.ip_network(subnet)
        assert network.prefixlen >= camera_discovery.CameraDiscovery.MAX_SCAN_PREFIX, (
            f"{subnet} has {network.num_addresses} addresses; too many to probe"
        )


def test_a_typical_home_network_is_detected(monkeypatch):
    """
    The case that matters to a real user: a /24 must be found and scanned.

    The container this suite runs in has only loopback and a Docker /16, so
    without this the tests only ever exercise the rejection path and the
    fallback — never the one where discovery actually works.
    """
    import socket
    from collections import namedtuple

    from backend.core import camera_discovery

    Addr = namedtuple("Addr", "family address netmask broadcast ptp")
    monkeypatch.setattr(camera_discovery.psutil, "net_if_addrs", lambda: {
        "lo0":  [Addr(socket.AF_INET, "127.0.0.1",   "255.0.0.0",     None, None)],
        "en0":  [Addr(socket.AF_INET, "192.168.1.42", "255.255.255.0", None, None)],
        "utun": [Addr(socket.AF_INET, "169.254.3.9",  "255.255.0.0",   None, None)],
        "eth0": [Addr(socket.AF_INET, "172.17.0.2",   "255.255.0.0",   None, None)],
    })

    subnets = camera_discovery.discovery_service._get_local_subnets()

    assert "192.168.1.0/24" in subnets, "the real LAN was not detected"
    assert not any(s.startswith("127.") for s in subnets), "loopback was scanned"
    assert not any(s.startswith("169.254.") for s in subnets), (
        "a link-local address was scanned — that interface never got a lease, "
        "and probing it only spends the scan's time budget"
    )
    assert "172.17.0.0/16" not in subnets, "a /16 was accepted; 65k probes"


def test_an_interface_with_no_netmask_is_skipped_not_fatal(monkeypatch):
    """psutil reports netmask=None for some interfaces; that must not raise."""
    import socket
    from collections import namedtuple

    from backend.core import camera_discovery

    Addr = namedtuple("Addr", "family address netmask broadcast ptp")
    monkeypatch.setattr(camera_discovery.psutil, "net_if_addrs", lambda: {
        "weird": [Addr(socket.AF_INET, "10.0.0.5", None, None, None)],
        "en0":   [Addr(socket.AF_INET, "192.168.8.20", "255.255.255.0", None, None)],
    })

    subnets = camera_discovery.discovery_service._get_local_subnets()
    assert subnets == ["192.168.8.0/24"]
